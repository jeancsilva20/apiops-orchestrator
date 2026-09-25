from typing import Any, Dict, List, Optional

from apiops_orchestrator.application.exceptions.listing_exceptions import (
    ApiNotFound,
    InsufficientSessionError,
    InvalidWindow,
)
from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from apiops_orchestrator.domain.models.catalog_revision_model import CatalogRevisionInfo
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.services.catalog_visibility import finder_rows_visible_to
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort

_FETCH_GROW_CAP = 2000


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

        rows = self._fetch_catalog(int(offset or 0) + int(limit or 0), query)
        rows = self._filter_visibility(rows)
        return self._slice_window(rows, offset, limit)

    def api_revisions(self, api_id: int) -> List[CatalogRevisionInfo]:
        entry = self.manager_api.list_api_detail(api_id)
        if not entry:
            raise ApiNotFound(api_id)

        workflow_ids = sorted(
            {rev.workflowId for rev in entry.revisions if rev.workflowId is not None}
        )
        stage_names = self._resolve_stage_names(workflow_ids)

        rows: List[CatalogRevisionInfo] = []
        for revision in entry.revisions:
            revision_id = revision.id
            if revision_id is None or not revision.revisionNumber:
                continue
            stage_name = (
                stage_names.get(revision.workflowStageId)
                if revision.workflowStageId is not None
                else None
            )
            rows.append(
                CatalogRevisionInfo(
                    revision_id=revision_id,
                    revision_number=int(revision.revisionNumber),
                    stage_name=(
                        stage_name if stage_name else revision.workflowId
                    ),
                    environments=", ".join(revision.environments),
                    completeness_score=revision.completenessScore,
                )
            )
        rows.sort(key=lambda row: row.revision_number)
        return rows

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

    def _fetch_catalog(self, needed: int, query: Optional[str]) -> List[ApiCatalogEntry]:
        first = max(needed, 1)
        page = self.manager_api.list_catalog_apis(limit=first, query=query)
        rows, total = list(page.rows), page.total

        if total > len(rows) and total <= _FETCH_GROW_CAP and needed < total:
            page = self.manager_api.list_catalog_apis(limit=total, query=query)
            rows, total = list(page.rows), page.total
        return rows

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
