"""Use-case do `sen sync` — carga e verificação de uma API do Manager no repositório.

    argumentos   api-id × spec.id existente                          sem rede
    API          GET /apis/{id} + visibilidade                       GET
    revisão      revisionNumber em revisions[], GET /revisions/{id}  GET
    contrato     GET /revisions/{id}/swagger, só OpenAPI 3           GET
    carga        materialize(api, revisão, template, swagger) → escrita atômica
    verificação  materialize(remoto) × materialize(assemble(remoto, repositório))

Só `GET` no Manager. Recebe **ports**, nunca adapters concretos, e lê os modelos
`Api` e `Revision` que o port devolve.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from apiops_orchestrator.application.enums.manager_failure_kind_enum import (
    ManagerFailureKind,
)
from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    INTERNAL_ERROR_MESSAGE,
)
from apiops_orchestrator.application.exceptions.sync_exceptions import (
    ApiIdMismatchError,
    ApiNotFoundError,
    EmptyRevisionError,
    InvalidRepositoryError,
    ManagerUnavailableError,
    MissingApiIdError,
    RevisionNotFoundError,
    SessionRejectedError,
    SyncError,
    UnsupportedSwaggerError,
    WriteFailedError,
)
from apiops_orchestrator.application.services.api_access_guard import ApiAccessGuard
from apiops_orchestrator.application.services.manager_failure_translator import (
    classify_manager_failure,
    manager_failure_message,
)
from apiops_orchestrator.application.services.repo_importer_service import (
    RepoCanonicalReader,
)
from apiops_orchestrator.domain.models.api_model import Api, Revision
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.models.sync_view import (
    MODE_CHECK,
    MODE_LOAD,
    SCHEMA_SEN_SYNC_V1,
    SyncView,
)
from apiops_orchestrator.domain.models.validate_view import ValidateApi, ValidateRevision
from apiops_orchestrator.domain.ports.local_file_importer_port import (
    LocalFileImporterPort,
)
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiError,
    ManagerApiPort,
    ManagerApiTransportRejectedError,
)
from apiops_orchestrator.domain.ports.repo_writer_port import RepoWriteError, RepoWriterPort
from apiops_orchestrator.domain.services import openapi_contract
from apiops_orchestrator.domain.services import repo_layout as layout
from apiops_orchestrator.domain.services import revision_diff, revision_payload
from apiops_orchestrator.domain.services.api_visibility import from_api
from apiops_orchestrator.domain.services.repo_materializer import (
    MaterializationResult,
    materialize,
)

logger = logging.getLogger(__name__)

Progress = Callable[[str], None]

# Fields of `api-basic-info.yaml` that the repository is authoritative for in the
# check: the local side of the comparison takes them from `spec`.
_SPEC_FIELDS = ("name", "version", "basePath", "description", "apiResponsible", "apiTags")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class _Target:
    api_id: int
    spec: Dict[str, Any]


@dataclass(frozen=True)
class _Remote:
    api: Api
    revision: Revision
    swagger: Dict[str, Any]


class SyncService:
    def __init__(
        self,
        manager_api: ManagerApiPort,
        importer: LocalFileImporterPort,
        writer: RepoWriterPort,
        session: Optional[LoginSession] = None,
    ):
        self._manager_api = manager_api
        self._importer = importer
        self._writer = writer
        self._access = ApiAccessGuard(session)

    # --- casos de uso ---------------------------------------------------------

    def sync(
        self,
        repo_path: Path,
        *,
        api_id: Optional[int],
        revision_number: int,
        template: Optional[int] = None,
        progress: Optional[Progress] = None,
    ) -> SyncView:
        """Carga: grava no repositório a revisão informada.

        `template` goes to `spec.template` after being checked in the Manager;
        without it, the value already in the file is kept.
        """
        step = progress or (lambda _: None)
        target = self._target(repo_path, api_id)
        remote = self._read_remote(target.api_id, revision_number, step)
        if template is not None:
            self._check_template(template, step)

        step("Montando a estrutura")
        result = materialize(
            remote.api,
            remote.revision,
            template=template if template is not None else target.spec.get("template", ""),
            swagger=remote.swagger,
        )

        step("Gravando os arquivos")
        try:
            self._writer.write_managed_area(Path(repo_path), result.files)
        except RepoWriteError as exc:
            raise WriteFailedError(exc.reason, exc.path) from exc
        logger.info(
            "sync.load.done api_id=%s revision=%s files=%d",
            target.api_id,
            revision_number,
            len(result.files),
        )
        return self._view(MODE_LOAD, remote, result, repository=str(Path(repo_path).resolve()))

    def check(
        self,
        repo_path: Path,
        *,
        api_id: Optional[int],
        revision_number: int,
        progress: Optional[Progress] = None,
    ) -> SyncView:
        """Verificação: compara o repositório com a revisão informada, sem gravar."""
        step = progress or (lambda _: None)
        target = self._target(repo_path, api_id)
        remote = self._read_remote(target.api_id, revision_number, step)

        step("Lendo o repositório")
        loaded = RepoCanonicalReader(self._importer).load(str(repo_path))
        problems = [f"falta `{m}`" for m in loaded.missing] + [
            f"`{u}` não pôde ser lido" for u in loaded.unreadable
        ]
        if problems:
            raise InvalidRepositoryError(problems)

        step("Comparando com o Manager")
        template = target.spec.get("template", "")
        manager_side = materialize(
            remote.api, remote.revision, template=template, swagger=remote.swagger
        )
        # `assemble` still speaks the raw payload (it moves to the models with the
        # publish); the wire of the remote revision feeds it and its body comes back
        # as a model for the materializer.
        assembled = revision_payload.assemble(
            draft=remote.revision.to_wire(),
            basic_info=loaded.basic_info,
            root=loaded.root,
            resources=loaded.resources,
        )
        declared = openapi_contract.extract_contract(
            basic_info=loaded.basic_info,
            components=loaded.components,
            resources=loaded.resources,
        )
        local_swagger = openapi_contract.apply_contract(remote.swagger, declared)
        local_api = Api.model_validate(
            {**remote.api.to_wire(), **{k: target.spec[k] for k in _SPEC_FIELDS if k in target.spec}}
        )
        repository_side = materialize(
            local_api,
            Revision.model_validate(assembled.body),
            template=template,
            swagger=local_swagger,
        )
        differences = revision_diff.compare(repository_side.files, manager_side.files)
        logger.info(
            "sync.check.done api_id=%s revision=%s differences=%d",
            target.api_id,
            revision_number,
            len(differences),
        )
        view = self._view(MODE_CHECK, remote, manager_side)
        return SyncView(
            schema=view.schema,
            generated_at=view.generated_at,
            mode=MODE_CHECK,
            api=view.api,
            revision=view.revision,
            warnings=view.warnings,
            differences=differences,
        )

    # --- etapas compartilhadas -------------------------------------------------

    def _target(self, repo_path: Path, api_id: Optional[int]) -> _Target:
        """Resolve o id da API entre o argumento e o `spec.id` existente, sem rede."""
        spec = self._existing_spec(repo_path)
        in_repo = spec.get("id")
        if api_id is not None and in_repo is not None and str(in_repo) != str(api_id):
            raise ApiIdMismatchError(in_repo, api_id)
        resolved = api_id if api_id is not None else in_repo
        if resolved is None:
            raise MissingApiIdError()
        return _Target(api_id=int(resolved), spec=spec)

    def _existing_spec(self, repo_path: Path) -> Dict[str, Any]:
        path = str(Path(repo_path) / layout.BASIC_INFO_FILE)
        if not self._importer.exists(path):
            return {}
        try:
            data = self._importer.read(path) or {}
        except Exception as exc:  # YAML malformado, permissão, encoding
            raise SyncError(
                f"O arquivo `{layout.BASIC_INFO_FILE}` existe mas não pôde ser lido. "
                "Corrija o arquivo e rode o comando novamente.\n\nNada foi gravado."
            ) from exc
        spec = data.get("spec") if isinstance(data, dict) else None
        return dict(spec) if isinstance(spec, dict) else {}

    def _check_template(self, template: int, step: Progress) -> None:
        """The template API must exist and be visible, like the API itself."""
        step("Consultando a API template no Manager")
        api: Optional[Api] = self._call(lambda: self._manager_api.get_api_by_id(template), template)
        if api is None or not self._access.can_see(from_api(api)):
            raise ApiNotFoundError(template)

    def _read_remote(self, api_id: int, number: int, step: Progress) -> _Remote:
        step("Consultando a API no Manager")
        api: Optional[Api] = self._call(lambda: self._manager_api.get_api_by_id(api_id), api_id)
        if api is None or not self._access.can_see(from_api(api)):
            raise ApiNotFoundError(api_id)

        summary = api.revision_by_number(number)
        if summary is None:
            raise RevisionNotFoundError(api_id, number, api.revision_numbers)

        step(f"Lendo a revisão {number}")
        revision: Optional[Revision] = self._call(
            lambda: self._manager_api.get_revision(summary.id), api_id
        )
        if revision is None or not revision.resources:
            raise EmptyRevisionError(number, summary.id)

        step("Lendo o contrato OpenAPI")
        swagger = self._call(
            lambda: self._manager_api.get_revision_swagger(summary.id), api_id
        ) or {}
        if not openapi_contract.is_openapi_3(swagger):
            raise UnsupportedSwaggerError(number, openapi_contract.document_format(swagger))
        return _Remote(api=api, revision=revision, swagger=swagger)

    def _call(self, request: Callable[[], Any], api_id: int) -> Any:
        """Traduz os sinais do port para os erros do sync; `404` vira `None`."""
        try:
            return request()
        except ManagerApiError as exc:
            kind = classify_manager_failure(exc)
            if kind is ManagerFailureKind.NOT_FOUND:
                return None
            if kind in (ManagerFailureKind.UNAUTHORIZED, ManagerFailureKind.FORBIDDEN):
                raise SessionRejectedError(manager_failure_message(kind) or "") from exc
            if kind is ManagerFailureKind.UNAVAILABLE:
                raise ManagerUnavailableError() from exc
            status = exc.status_code if isinstance(exc, ManagerApiTransportRejectedError) else None
            logger.info("sync.manager.rejected api_id=%s status=%s", api_id, status)
            raise SyncError(f"{INTERNAL_ERROR_MESSAGE}\n\nNada foi gravado.") from exc

    @staticmethod
    def _view(
        mode: str, remote: _Remote, result: MaterializationResult, repository: Optional[str] = None
    ) -> SyncView:
        api, revision = remote.api, remote.revision
        return SyncView(
            schema=SCHEMA_SEN_SYNC_V1,
            generated_at=_now(),
            mode=mode,
            api=ValidateApi(
                manager_id=api.id, name=api.name, version=api.version, base_path=api.base_path
            ),
            revision=ValidateRevision(
                manager_id=revision.id, revision_number=revision.revision_number
            ),
            repository=repository,
            files=sorted(result.paths),
            resources=len(revision.resources),
            operations=revision.total_operations,
            warnings=sorted(set(result.warnings)),
        )
