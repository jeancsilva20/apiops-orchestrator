import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Set

from apiops_orchestrator.application.enums.manager_failure_kind_enum import (
    ManagerFailureKind,
)
from apiops_orchestrator.application.exceptions.listing_exceptions import (
    ApiCollectionError,
    ApiNotFound,
    InsufficientSessionError,
    InvalidWindow,
)
from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    INTERNAL_ERROR_MESSAGE,
)
from apiops_orchestrator.application.services.manager_failure_translator import (
    classify_manager_failure,
    manager_failure_message,
)
from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from apiops_orchestrator.domain.models.catalog_revision_model import CatalogRevisionInfo
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.services.catalog_visibility import finder_rows_visible_to
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiPort,
    ManagerApiResponseTooLargeError,
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)

logger = logging.getLogger(__name__)

# Páginas de 25 entre 8 KB e 2,7 MB são aceitas; a resposta única de 127 APIs
# (~7,9 MB) é recusada com 413. O peso por API varia muito (revisões inline),
# por isso a redução adaptativa em `_scan_catalog`.
_CATALOG_PAGE_SIZE = 25

# Leituras simultâneas de `/revisions/{id}/completeness` no drill-down.
_COMPLETENESS_WORKERS = 8


def _catalog_access_error(
    exc: ManagerApiTransportRejectedError | ManagerApiTransportUnavailableError,
    api_id: Optional[int] = None,
) -> ApiCollectionError:
    """Sinais do port → erro categorizado, pela classificação compartilhada.

    Só o drill-down sabe o que um 404 significa (a API pedida); na listagem,
    um 404 do catálogo não tem leitura de negócio e vira erro interno.
    """
    kind = classify_manager_failure(exc)
    if kind is ManagerFailureKind.NOT_FOUND:
        if api_id is not None:
            return ApiNotFound(api_id)
        kind = ManagerFailureKind.INTERNAL
    return ApiCollectionError(manager_failure_message(kind))


class ApiListingService:
    def __init__(
        self,
        manager_api: ManagerApiPort,
        session: Optional[LoginSession] = None,
    ):
        self.manager_api = manager_api
        self.session = session

    def list_apis(
        self,
        api_id: Optional[int] = None,
        query: Optional[str] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[ApiCatalogEntry]:
        try:
            return self._list_apis_internal(
                api_id=api_id, query=query, offset=offset, limit=limit
            )
        except (ManagerApiTransportRejectedError, ManagerApiTransportUnavailableError) as exc:
            # Sinais do port → erro categorizado (a CLI só conhece esta hierarquia).
            raise _catalog_access_error(exc, api_id) from exc

    def _list_apis_internal(
        self,
        api_id: Optional[int],
        query: Optional[str],
        offset: Optional[int],
        limit: Optional[int],
    ) -> List[ApiCatalogEntry]:
        if api_id is not None:
            entry = self.manager_api.list_api_detail(api_id)
            if not entry:
                raise ApiNotFound(api_id)
            return [entry]

        if self.session is not None:
            super_admin = self.session.is_super_admin
            groups = list(self.session.userGroups or [])
            if not super_admin and not groups:
                raise InsufficientSessionError()

        self._validate_window(offset, limit)

        start = int(offset) if offset is not None else 0
        size = int(limit) if limit is not None else None

        if self._sees_everything():
            # Visibilidade total: a janela do usuário é a do servidor, sem varrer
            # o que vem antes do offset.
            rows = self._scan_catalog(query, server_offset=start, needed=size)
            return rows[:size] if size is not None else rows

        needed = start + size if size is not None else None
        rows = self._scan_catalog(query, server_offset=0, needed=needed)
        return self._slice_window(rows, offset, limit)

    def api_revisions(self, api_id: int) -> List[CatalogRevisionInfo]:
        try:
            return self._api_revisions_internal(api_id)
        except (ManagerApiTransportRejectedError, ManagerApiTransportUnavailableError) as exc:
            raise _catalog_access_error(exc, api_id) from exc

    def _api_revisions_internal(self, api_id: int) -> List[CatalogRevisionInfo]:
        entry = self.manager_api.list_api_detail(api_id)
        if not entry:
            raise ApiNotFound(api_id)

        workflow_ids = sorted(
            {rev.workflowId for rev in entry.revisions if rev.workflowId is not None}
        )
        stage_names = self._resolve_stage_names(workflow_ids)

        listed = [
            revision
            for revision in entry.revisions
            if revision.id is not None and revision.revisionNumber
        ]
        scores = self._read_completeness_scores([revision.id for revision in listed])

        rows: List[CatalogRevisionInfo] = []
        for revision in listed:
            stage_name = (
                stage_names.get(revision.workflowStageId)
                if revision.workflowStageId is not None
                else None
            )
            rows.append(
                CatalogRevisionInfo(
                    revision_id=revision.id,
                    revision_number=int(revision.revisionNumber),
                    stage_name=(
                        stage_name if stage_name else revision.workflowId
                    ),
                    environments=", ".join(revision.environments),
                    completeness_score=scores.get(revision.id),
                )
            )
        rows.sort(key=lambda row: row.revision_number)
        return rows

    def _read_completeness_scores(
        self, revision_ids: List[int]
    ) -> Dict[int, Optional[float]]:
        """Lê no Manager o completeness de cada revisão, em paralelo; falha vira None."""
        with ThreadPoolExecutor(max_workers=_COMPLETENESS_WORKERS) as pool:
            scores = pool.map(self._read_completeness_score, revision_ids)
            return dict(zip(revision_ids, scores))

    def _read_completeness_score(self, revision_id: int) -> Optional[float]:
        try:
            return self.manager_api.get_revision_completeness(revision_id).score
        except (ManagerApiTransportRejectedError, ManagerApiTransportUnavailableError) as exc:
            logger.info(
                "catalog.revisions.completeness_unavailable revision_id=%s type=%s",
                revision_id,
                type(exc).__name__,
            )
            return None

    @staticmethod
    def _validate_window(
        offset: Optional[int],
        limit: Optional[int],
    ) -> None:
        if offset is not None and int(offset) < 0:
            raise InvalidWindow("--offset", "ge_zero")
        if limit is not None and int(limit) <= 0:
            raise InvalidWindow("--limit", "gt_zero")

    def _slice_window(
        self,
        rows: List[ApiCatalogEntry],
        offset: Optional[int],
        limit: Optional[int],
    ) -> List[ApiCatalogEntry]:
        start = int(offset) if offset is not None else 0
        if limit is not None:
            return rows[start : start + int(limit)]
        return rows[start:] if start > 0 else rows

    def _sees_everything(self) -> bool:
        """Sem sessão (fluxo legado) ou super admin: nenhuma linha é filtrada."""
        return self.session is None or self.session.is_super_admin

    def _scan_catalog(
        self,
        query: Optional[str],
        server_offset: int,
        needed: Optional[int],
    ) -> List[ApiCatalogEntry]:
        """Lê o catálogo em páginas até reunir `needed` linhas visíveis (ou o fim).

        Nunca pede o catálogo inteiro de uma vez: a plataforma recusa respostas
        grandes (413). Se recusar uma página, repete a mesma posição com metade
        do tamanho, e o tamanho reduzido vale até o fim da leitura. A
        visibilidade é aplicada a cada página, no cliente. `needed=None` lê até
        o fim (`--all`).
        """
        page_size = _CATALOG_PAGE_SIZE
        position = server_offset
        seen: Set[int] = set()
        visible: List[ApiCatalogEntry] = []

        while True:
            try:
                page = self.manager_api.list_catalog_apis(
                    limit=page_size, offset=position, query=query
                )
            except ManagerApiResponseTooLargeError:
                if page_size == 1:
                    logger.info("catalog.scan.too_large_single_row offset=%s", position)
                    raise
                page_size = max(1, page_size // 2)
                logger.info(
                    "catalog.scan.page_shrunk offset=%s page_size=%s", position, page_size
                )
                continue

            rows = list(page.rows)
            fresh = [row for row in rows if row.id not in seen]
            if rows and not fresh:
                # Página só com ids já vistos: a plataforma não avançou. Seguir
                # lendo seria loop infinito.
                logger.info("catalog.scan.no_progress offset=%s", position)
                raise ApiCollectionError(INTERNAL_ERROR_MESSAGE)

            seen.update(row.id for row in fresh)
            visible.extend(self._filter_visibility(fresh))
            position += len(rows)

            if needed is not None and len(visible) >= needed:
                break
            if len(rows) < page_size:
                break
            if 0 <= page.total <= position:
                break

        return visible

    def _resolve_stage_names(self, workflow_ids: List[int]) -> Dict[int, Optional[str]]:
        resolved: Dict[int, Optional[str]] = {}
        for workflow_id in workflow_ids:
            for stage in self.manager_api.get_workflow_stages(workflow_id):
                resolved[stage.workflowStageId] = stage.workflowStageName
        return resolved

    def _filter_visibility(
        self, rows: List[ApiCatalogEntry]
    ) -> List[ApiCatalogEntry]:
        if self.session is None:
            return rows
        return finder_rows_visible_to(
            rows,
            self.session.userName,
            list(self.session.userGroups or []),
            self.session.is_super_admin,
        )
