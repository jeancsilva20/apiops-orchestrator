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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    INTERNAL_ERROR_MESSAGE,
)
from apiops_orchestrator.application.exceptions.validate_exceptions import (
    ArquivoIlegivelError,
    GovernanceBlockedError,
    IdentidadeDivergenteError,
    LayoutInvalidoError,
    PublicacaoDivergenteError,
    PublicacaoRecusadaError,
    RotaDuplicadaError,
    ValidateError,
)
from apiops_orchestrator.application.services.manager_failure_translator import (
    classify_manager_failure,
    manager_failure_message,
)
from apiops_orchestrator.application.services.repo_importer_service import (
    RepoCanonicalReader,
    RepositorioCarregado,
)
from apiops_orchestrator.domain.models.validate_view import PublicacaoResultado
from apiops_orchestrator.domain.ports.local_file_importer_port import (
    LocalFileImporterPort,
)
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiGovernanceBlockedError,
    ManagerApiPort,
    ManagerApiTransportRejectedError,
)
from apiops_orchestrator.domain.services import revision_payload

logger = logging.getLogger(__name__)

# Recusas da gravação cujo motivo da plataforma orienta a correção do repositório.
# As demais (sessão, acesso, tamanho, limite de taxa) usam a mensagem da família.
_STATUS_COM_MOTIVO = frozenset({400, 409, 412, 422})


@dataclass(frozen=True)
class WrittenRevision:
    """Write result and the revision state read back to verify it."""

    result: PublicacaoResultado
    published: Dict[str, Any] = field(default_factory=dict)


class RevisionWriter:
    def __init__(
        self,
        manager_api: ManagerApiPort,
        importer: LocalFileImporterPort,
        comando: str,
    ):
        self._manager_api = manager_api
        self._importer = importer
        # Prefixo dos eventos de log: `validate.publicacao.*`, `publish.publicacao.*`.
        self._comando = comando
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

    def carregar(self, repo_path: Path) -> RepositorioCarregado:
        """Carrega o repositório. Sem rede — é o que permite abortar antes."""
        lido = RepoCanonicalReader(self._importer).carregar(str(repo_path))
        if lido.faltando:
            ausente = lido.faltando[0]
            pista = ""
            if lido.ignorados:
                pista = f"Arquivos não reconhecidos na mesma árvore: {', '.join(lido.ignorados[:3])}."
            raise LayoutInvalidoError(ausente, pista or None)
        if lido.ilegiveis:
            caminho, _, motivo = lido.ilegiveis[0].partition(": ")
            raise ArquivoIlegivelError(caminho, motivo)
        self._sem_rota_duplicada(lido)
        return lido

    @staticmethod
    def _sem_rota_duplicada(lido: RepositorioCarregado) -> None:
        """I-6: cada rota em um só arquivo, mesmo em pastas diferentes.

        A montagem liga as pastas aos recursos do Manager pelas rotas (V-12a);
        só funciona se cada rota tiver um único dono no repositório, como já
        tem na plataforma (W-6).
        """
        arquivos_por_rota: Dict[str, List[str]] = {}
        for recurso in lido.recursos:
            for op in recurso.operacoes:
                if not op.path:
                    continue
                rota = f"{str(op.metodo or '').upper()} {op.path}"
                arquivos_por_rota.setdefault(rota, []).append(op.caminho)
        repetidas = {r: a for r, a in arquivos_por_rota.items() if len(a) > 1}
        if repetidas:
            raise RotaDuplicadaError(repetidas)

    @staticmethod
    def guarda_identidade(spec: Dict[str, Any], api: Dict[str, Any]) -> None:
        """Guarda 1 (D-11): `version` e `basePath` definem a identidade da API.

        `spec.id` NÃO aborta — é o endereço do GET, não a identidade funcional.
        """
        for campo in ("version", "basePath"):
            no_repo = spec.get(campo)
            no_manager = api.get(campo)
            if no_repo is not None and str(no_repo) != str(no_manager):
                raise IdentidadeDivergenteError(
                    campo, str(no_repo), str(no_manager), spec.get("id")
                )

    @staticmethod
    def revisao_por_numero(api: Dict[str, Any], numero: int) -> Dict[str, Any]:
        """Resolve a revisão pelo NÚMERO (V-24). Criar revisão é ato humano."""
        revisoes = api.get("revisions") or []
        if not revisoes:
            raise ValidateError(
                f"A API {api.get('id')} não tem nenhuma revisão no Manager. Criar "
                "revisão é ato humano: crie a revisão pela interface do Manager e "
                "rode o comando novamente."
            )
        for revisao in revisoes:
            if revisao.get("revisionNumber") == numero:
                return revisao
        raise ValidateError(
            f"A API não tem revisão de número {numero}. Disponíveis: "
            + ", ".join(str(r.get("revisionNumber")) for r in revisoes)
        )

    @staticmethod
    def customs_referenciados(lido: RepositorioCarregado) -> Iterator[Tuple[Any, str]]:
        """Pares `(id, escopo)` de todo `Custom` que o repositório declara."""
        def do_bloco(bloco: Dict[str, Any], escopo: str):
            for chave in ("interceptors_request", "interceptors_response"):
                for item in bloco.get(chave) or []:
                    if item.get("type") == "Custom" and item.get("id") is not None:
                        yield (item["id"], escopo)

        yield from do_bloco(lido.raiz, "all.yaml")
        for recurso in lido.recursos:
            yield from do_bloco(recurso.dados or {}, recurso.caminho)
            for op in recurso.operacoes:
                yield from do_bloco(op.dados or {}, op.caminho)

    @staticmethod
    def texto_de_confirmacao(base: str, avisos: Sequence[str]) -> str:
        """Pergunta da confirmação local, com o que vai sair do Manager.

        Os avisos da montagem dizem o que a gravação apaga. Em modo local eles
        vão AQUI, antes do s/n — exibidos só depois, o dev confirmaria sem saber
        —, e não se repetem no resultado.
        """
        if not avisos:
            return base
        return base + "\n\nAtenção:\n\n" + "\n\n".join(avisos)

    # --- escrita -------------------------------------------------------------

    def gravar_e_conferir(
        self,
        revisao: Dict[str, Any],
        montado: "revision_payload.PayloadMontado",
        *,
        etapa: Callable[[str], None] = lambda _: None,
        rotulo_gravacao: str,
        alvo_recusa: str,
    ) -> WrittenRevision:
        """E3 + E3.1: um único PUT na revisão e a releitura que o confere.

        `workflowId`/`workflowStageId` viajam na cópia profunda do estado remoto
        que está em `montado.corpo` — nada aqui os reescreve (D-020).
        """
        etapa(rotulo_gravacao)
        try:
            self._manager_api.update_revision(revisao["id"], montado.corpo)
        except ManagerApiGovernanceBlockedError as exc:
            # O pré-check liberou, mas a plataforma bloqueou: o workflow que
            # valida não é o gravado na revisão (V-23 §3). O faltante não é
            # calculável sem o stage efetivo — degrada para o motivo literal.
            logger.info(
                "%s.publicacao.governanca_recusou workflow_erro=%s workflow_revisao=%s",
                self._comando,
                exc.workflow_id,
                revisao.get("workflowId"),
            )
            raise GovernanceBlockedError(
                workflow_id=exc.workflow_id,
                stage_id=None,
                missing=[],
                raw=exc.raw,
                motivos=exc.messages,
            ) from exc
        except ManagerApiTransportRejectedError as exc:
            raise self._recusa_da_gravacao(exc, alvo_recusa) from exc

        # E3.1: HTTP 200 não é prova de sucesso (W-8).
        etapa("Conferindo o que foi gravado")
        publicado = self._manager_api.get_revision(revisao["id"]) or {}
        divergencias = revision_payload.conferir(
            montado.corpo, publicado, esperado=montado.esperado
        )
        if divergencias:
            raise PublicacaoDivergenteError(divergencias)

        return WrittenRevision(
            result=PublicacaoResultado(attempted=True, accepted=True, verified=True),
            published=publicado,
        )

    def _recusa_da_gravacao(
        self, exc: ManagerApiTransportRejectedError, alvo: str
    ) -> PublicacaoRecusadaError:
        """Recusa do `PUT` fora da governança: motivo da plataforma ou mensagem da família."""
        motivos = exc.messages if exc.status_code in _STATUS_COM_MOTIVO else []
        logger.info(
            "%s.publicacao.recusada status_code=%s motivos=%d",
            self._comando,
            exc.status_code,
            len(motivos),
        )
        padrao = manager_failure_message(classify_manager_failure(exc))
        return PublicacaoRecusadaError(
            padrao or INTERNAL_ERROR_MESSAGE, motivos, alvo=alvo
        )
