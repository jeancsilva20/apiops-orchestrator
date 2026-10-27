"""Escrita de uma revisão no Manager, compartilhada por `validate` e `publish`.

Os dois comandos gravam o repositório numa revisão pela mesma mecânica — o que
muda é a revisão alvo e o que cada um faz em volta. Aqui fica só o que precisa
ser idêntico nos dois:

    carga do repositório              sem rede — erro de layout aborta antes
    guarda de identidade (D-11)       version e basePath
    revisão pelo NÚMERO (V-24)        o id é detalhe de transporte
    Custom referenciados              pares (id, escopo) para a verificação
    PUT único + conferência           W-7 e W-8 — 200 não é prova de sucesso

Recebe **ports**, nunca adapters concretos.
"""

import logging
import posixpath
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    INTERNAL_ERROR_MESSAGE,
)
from apiops_orchestrator.application.exceptions.validate_exceptions import (
    UnreadableFileError,
    EmptyResourceError,
    GovernanceBlockedError,
    IdentityMismatchError,
    InvalidLayoutError,
    NoResourceError,
    PublicationDivergenceError,
    PublicationRejectedError,
    DuplicateRouteError,
    ValidateError,
)
from apiops_orchestrator.application.services.manager_failure_translator import (
    classify_manager_failure,
    manager_failure_message,
)
from apiops_orchestrator.application.services.repo_importer_service import (
    RepoCanonicalReader,
    LoadedRepository,
)
from apiops_orchestrator.domain.models.validate_view import PublicationResult
from apiops_orchestrator.domain.ports.local_file_importer_port import (
    LocalFileImporterPort,
)
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiGovernanceBlockedError,
    ManagerApiPort,
    ManagerApiTransportRejectedError,
)
from apiops_orchestrator.domain.services import revision_payload
from apiops_orchestrator.domain.services.repo_layout import RESOURCES_FOLDER

logger = logging.getLogger(__name__)

# Recusas da gravação cujo motivo da plataforma orienta a correção do repositório.
# As demais (sessão, acesso, tamanho, limite de taxa) usam a mensagem da família.
_STATUS_WITH_REASON = frozenset({400, 409, 412, 422})


def _hidden(file_path: str) -> bool:
    """Path under a dot folder or dot file, such as `.github/` or `.gitlab-ci.yml`."""
    return any(part.startswith(".") for part in file_path.split("/"))


def _unread_reason(file_path: str) -> str:
    """Why a `.yaml` left out by the discovery is not read."""
    parts = file_path.split("/")
    if parts[0] != RESOURCES_FOLDER:
        return "não faz parte da estrutura da API"
    if len(parts) == 2:
        return (
            "está solto em `resources/`, e cada recurso é uma pasta com o "
            "`resource.yaml` e as operações"
        )
    if len(parts) > 3:
        return f"está numa subpasta, e as operações ficam direto em `resources/{parts[1]}/`"
    stem = posixpath.splitext(parts[2])[0]
    return (
        "não é considerado operação, porque o nome não começa com o método HTTP. "
        f"Use `<método>_<path>.yaml`, como `get_{stem}.yaml`"
    )


def _unread_line(file_path: str, shown: str) -> str:
    return f"`{shown}` {_unread_reason(file_path)}."


@dataclass(frozen=True)
class WrittenRevision:
    """Write result and the revision state read back to verify it."""

    result: PublicationResult
    published: Dict[str, Any] = field(default_factory=dict)


class RevisionWriter:
    def __init__(
        self,
        manager_api: ManagerApiPort,
        importer: LocalFileImporterPort,
        command: str,
    ):
        self._manager_api = manager_api
        self._importer = importer
        # Prefixo dos eventos de log: `validate.publication.*`, `publish.publication.*`.
        self._command = command
        self._cache_custom: Dict[int, Optional[Dict[str, Any]]] = {}

    def resolver_custom(self, custom_id: int) -> Optional[Dict[str, Any]]:
        """`{id, name, script}` do catálogo, para o `content` de um `Custom` novo.

        A existência é verificada antes, e aborta lá se faltar; aqui o objetivo
        é só o conteúdo. O cache evita repetir o GET quando o mesmo `Custom`
        aparece em vários escopos.
        """
        if custom_id not in self._cache_custom:
            self._cache_custom[custom_id] = self._manager_api.get_custom_interceptor_by_id(
                custom_id
            )
        return self._cache_custom[custom_id]

    # --- antes da escrita ----------------------------------------------------

    def load(self, repo_path: Path) -> LoadedRepository:
        """Carrega o repositório. Sem rede — é o que permite abortar antes."""
        loaded = RepoCanonicalReader(self._importer).load(str(repo_path))
        if loaded.missing:
            missing = loaded.missing[0]
            hint = ""
            if loaded.ignored:
                hint = f"Arquivos não reconhecidos na mesma árvore: {', '.join(loaded.ignored[:3])}."
            raise InvalidLayoutError(missing, hint or None)
        if loaded.unreadable:
            file_path, _, reason = loaded.unreadable[0].partition(": ")
            raise UnreadableFileError(file_path, reason)
        self._ensure_operations(loaded)
        self._ensure_no_duplicate_route(loaded)
        return loaded

    @staticmethod
    def _ensure_operations(loaded: LoadedRepository) -> None:
        """I-2 and I-4: the API and each resource need at least one operation."""
        if not loaded.resources:
            raise NoResourceError(
                [
                    _unread_line(p, p)
                    for p in loaded.ignored
                    if p.startswith(RESOURCES_FOLDER + "/")
                ]
            )
        empty: Dict[str, List[str]] = {}
        for resource in loaded.resources:
            if resource.operations:
                continue
            folder = posixpath.dirname(resource.file_path)
            empty[folder] = [
                _unread_line(p, p[len(folder) + 1 :])
                for p in loaded.ignored
                if p.startswith(folder + "/")
            ]
        if empty:
            raise EmptyResourceError(empty)

    @staticmethod
    def unread_files_warnings(loaded: LoadedRepository) -> List[str]:
        """Warning listing the `.yaml` files the command does not read, hidden ones aside."""
        unread = [p for p in loaded.ignored if not _hidden(p)]
        if not unread:
            return []
        opening = (
            "O comando não lê o arquivo abaixo, e ele fica fora da gravação:"
            if len(unread) == 1
            else "O comando não lê os arquivos abaixo, e eles ficam fora da gravação:"
        )
        return [opening + "\n" + "\n".join(f"  - {_unread_line(p, p)}" for p in unread)]

    @staticmethod
    def _ensure_no_duplicate_route(loaded: LoadedRepository) -> None:
        """I-6: cada rota em um só arquivo, mesmo em pastas diferentes.

        A montagem liga as pastas aos recursos do Manager pelas rotas (V-12a);
        só funciona se cada rota tiver um único dono no repositório, como já
        tem na plataforma (W-6).
        """
        files_by_route: Dict[str, List[str]] = {}
        for resource in loaded.resources:
            for op in resource.operations:
                if not op.path:
                    continue
                route = f"{str(op.method or '').upper()} {op.path}"
                files_by_route.setdefault(route, []).append(op.file_path)
        repeated = {r: a for r, a in files_by_route.items() if len(a) > 1}
        if repeated:
            raise DuplicateRouteError(repeated)

    @staticmethod
    def guard_identity(spec: Dict[str, Any], api: Dict[str, Any]) -> None:
        """Guarda 1 (D-11): `version` e `basePath` definem a identidade da API.

        `spec.id` NÃO aborta — é o endereço do GET, não a identidade funcional.
        """
        for field_name in ("version", "basePath"):
            no_repo = spec.get(field_name)
            no_manager = api.get(field_name)
            if no_repo is not None and str(no_repo) != str(no_manager):
                raise IdentityMismatchError(
                    field_name, str(no_repo), str(no_manager), spec.get("id")
                )

    @staticmethod
    def revision_by_number(api: Dict[str, Any], number: int) -> Dict[str, Any]:
        """Resolve a revisão pelo NÚMERO (V-24). Criar revisão é ato humano."""
        revisions = api.get("revisions") or []
        if not revisions:
            raise ValidateError(
                f"A API {api.get('id')} não tem nenhuma revisão no Manager. Criar "
                "revisão é ato humano: crie a revisão pela interface do Manager e "
                "rode o comando novamente."
            )
        for revision in revisions:
            if revision.get("revisionNumber") == number:
                return revision
        raise ValidateError(
            f"A API não tem revisão de número {number}. Disponíveis: "
            + ", ".join(str(r.get("revisionNumber")) for r in revisions)
        )

    @staticmethod
    def referenced_customs(loaded: LoadedRepository) -> Iterator[Tuple[Any, str]]:
        """Pares `(id, scope)` de todo `Custom` que o repositório declara."""
        def from_block(block: Dict[str, Any], scope: str):
            for key in ("interceptors_request", "interceptors_response"):
                for item in block.get(key) or []:
                    if item.get("type") == "Custom" and item.get("id") is not None:
                        yield (item["id"], scope)

        yield from from_block(loaded.root, "all.yaml")
        for resource in loaded.resources:
            yield from from_block(resource.data or {}, resource.file_path)
            for op in resource.operations:
                yield from from_block(op.data or {}, op.file_path)

    @staticmethod
    def confirmation_text(base: str, warnings: Sequence[str]) -> str:
        """Pergunta da confirmação local, com o que vai sair do Manager.

        Os avisos da montagem dizem o que a gravação apaga. Em modo local eles
        vão AQUI, antes do s/n — exibidos só depois, o dev confirmaria sem saber
        —, e não se repetem no resultado.
        """
        if not warnings:
            return base
        return base + "\n\nAtenção:\n\n" + "\n\n".join(warnings)

    # --- escrita -------------------------------------------------------------

    def write_and_verify(
        self,
        revision: Dict[str, Any],
        assembled: "revision_payload.AssembledPayload",
        *,
        step: Callable[[str], None] = lambda _: None,
        write_label: str,
        rejection_target: str,
    ) -> WrittenRevision:
        """E3 + E3.1: um único PUT na revisão e a releitura que o confere.

        `workflowId`/`workflowStageId` viajam na cópia profunda do estado remoto
        que está em `assembled.body` — nada aqui os reescreve (D-020).
        """
        step(write_label)
        try:
            self._manager_api.update_revision(revision["id"], assembled.body)
        except ManagerApiGovernanceBlockedError as exc:
            # O pré-check liberou, mas a plataforma bloqueou: o workflow que
            # valida não é o gravado na revisão (V-23 §3). O faltante não é
            # calculável sem o stage efetivo — degrada para o motivo literal.
            logger.info(
                "%s.publicacao.governanca_recusou workflow_erro=%s workflow_revisao=%s",
                self._command,
                exc.workflow_id,
                revision.get("workflowId"),
            )
            raise GovernanceBlockedError(
                workflow_id=exc.workflow_id,
                stage_id=None,
                missing=[],
                raw=exc.raw,
                reasons=exc.messages,
            ) from exc
        except ManagerApiTransportRejectedError as exc:
            raise self._write_rejection(exc, rejection_target) from exc

        # E3.1: HTTP 200 não é prova de sucesso (W-8).
        step("Conferindo o que foi gravado")
        published = self._manager_api.get_revision(revision["id"]) or {}
        divergences = revision_payload.verify(
            assembled.body, published, expected=assembled.expected
        )
        if divergences:
            raise PublicationDivergenceError(divergences)

        return WrittenRevision(
            result=PublicationResult(attempted=True, accepted=True, verified=True),
            published=published,
        )

    def _write_rejection(
        self, exc: ManagerApiTransportRejectedError, target: str
    ) -> PublicationRejectedError:
        """Recusa do `PUT` fora da governança: motivo da plataforma ou mensagem da família."""
        reasons = exc.messages if exc.status_code in _STATUS_WITH_REASON else []
        logger.info(
            "%s.publicacao.recusada status_code=%s motivos=%d",
            self._command,
            exc.status_code,
            len(reasons),
        )
        default = manager_failure_message(classify_manager_failure(exc))
        return PublicationRejectedError(
            default or INTERNAL_ERROR_MESSAGE, reasons, target=target
        )
