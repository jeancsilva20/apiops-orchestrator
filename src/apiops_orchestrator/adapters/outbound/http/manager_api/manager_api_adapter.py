import logging
from typing import Dict, Any, List, Optional

from apiops_orchestrator.domain.ports.manager_api_port import ApiCatalogPage, ManagerApiPort
from apiops_orchestrator.domain.models.api_catalog_model import (
    ApiCatalogEntry,
    OwnershipContext,
)
from apiops_orchestrator.domain.models.catalog_revision_model import CatalogRevision
from apiops_orchestrator.domain.models.workflow_stage_model import WorkflowStage
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.infrastructure.utils.http_client import HttpClient

logger = logging.getLogger(__name__)

GOVERNANCE_BASE_PATH = "/api-governance/api/v3/"
FINDER_BASE_PATH = "/api-finder/api/v3/"


def _wire_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _wire_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _wire_str(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _parse_environments(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    return [name for name in (_wire_str(item) for item in raw) if name is not None]


def _merge_wire_blocks(raw: Dict[str, Any]) -> List[CatalogRevision]:
    revisions: List[CatalogRevision] = []
    for item in raw.get("revisions") or []:
        if not isinstance(item, dict):
            continue
        revisions.append(
            CatalogRevision(
                id=_wire_int(item.get("id")),
                revisionNumber=_wire_int(item.get("revisionNumber")),
                creationDate=item.get("creationDate"),
            )
        )

    by_id: Dict[Optional[int], CatalogRevision] = {
        rev.id: rev for rev in revisions if rev.id is not None
    }

    for env in raw.get("environments") or []:
        if not isinstance(env, dict):
            continue
        rev = by_id.get(_wire_int(env.get("apiRevision")))
        name = _wire_str(env.get("name"))
        if rev is not None and name is not None:
            rev.environments.append(name)

    for scored in raw.get("completeness") or []:
        if not isinstance(scored, dict):
            continue
        rev = by_id.get(_wire_int(scored.get("apiRevision")))
        score = _wire_float(scored.get("score"))
        if rev is not None and rev.completenessScore is None and score is not None:
            rev.completenessScore = score

    for wf in raw.get("wokflow") or raw.get("workflow") or []:
        if not isinstance(wf, dict):
            continue
        rev = by_id.get(_wire_int(wf.get("apiRevision")))
        if rev is None:
            continue
        rev.workflowId = _wire_int(wf.get("workflowId"))
        rev.workflowStageId = _wire_int(wf.get("workflowStageId"))

    return revisions


def _resolve_last_revision_number(
    raw: Dict[str, Any], revisions: List[CatalogRevision]
) -> Optional[int]:
    last_revision = raw.get("lastRevision")
    if last_revision is None:
        return None

    if isinstance(last_revision, dict):
        number = _wire_int(last_revision.get("revisionNumber"))
        if number is not None:
            return number
        target_id = _wire_int(last_revision.get("id"))
    else:
        target_id = _wire_int(last_revision)

    if target_id is None:
        return None
    for revision in revisions:
        if revision.id == target_id:
            return revision.revisionNumber
    return None


def _translate_row(raw: Any) -> Optional[ApiCatalogEntry]:
    if not isinstance(raw, dict):
        return None

    api_id = _wire_int(raw.get("apiId", raw.get("id")))
    if api_id is None:
        return None

    revisions = _merge_wire_blocks(raw)
    last_number = _resolve_last_revision_number(raw, revisions)

    context_type: Optional[OwnershipContext] = None
    if raw.get("contextType") is not None:
        try:
            context_type = OwnershipContext(str(raw["contextType"]).strip().lower())
        except ValueError:
            context_type = None

    logins_raw = raw.get("contextUserLogins")
    logins = [str(x) for x in (logins_raw if isinstance(logins_raw, list) else [])]

    return ApiCatalogEntry(
        id=api_id,
        name=_wire_str(raw.get("apiName", raw.get("name"))),
        description=_wire_str(raw.get("description")),
        version=_wire_str(raw.get("version")),
        basePath=_wire_str(raw.get("basePath")),
        lifeCycle=_wire_str(raw.get("apiLifeCycle", raw.get("lifeCycle"))),
        owner=_wire_str(raw.get("owner")),
        updateDate=raw.get("updateDate"),
        contextType=context_type,
        contextGroupName=_wire_str(raw.get("contextGroupName")),
        contextUserLogins=logins if isinstance(logins_raw, list) else [],
        lastRevisionNumber=last_number,
        revisions=revisions,
    )


def _build_custom_search(query: str) -> str:
    sanitized = "".join(ch for ch in query if ch not in '"()')
    return f'(apiName:"{sanitized}" OR description:"{sanitized}")'


class ManagerApiAdapter(ManagerApiPort):
    def __init__(self, token: str, base_path: str, max_retries: int, api_id: int, settings: Settings):
        self.host = settings.HOST
        self.token = token
        self.api_id = api_id
        self.base_path = base_path
        self.max_retries = max_retries
        self._stages_cache: Dict[int, List[Dict[str, Any]]] = {}

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        base_path: Optional[str] = None,
        **kwargs,
    ) -> Any:
        path_prefix = base_path if base_path is not None else self.base_path
        url = f"{self.host}{path_prefix}{endpoint}"
        headers = self._get_headers()

        return HttpClient.request(
            method=method,
            url=url,
            headers=headers,
            max_retries=self.max_retries,
            **kwargs
        )

    def get_apis(self) -> list[Dict[str, Any]]:
        endpoint = "apis"
        return self._request("GET", endpoint)

    def list_api_detail(self, api_id: int) -> Optional[ApiCatalogEntry]:
        payload, _ = self._request(
            "GET",
            "apis",
            base_path=FINDER_BASE_PATH,
            report_client_errors=False,
            return_headers=True,
            params={"customSearch": f"(apiId:{api_id})"},
        )

        rows = payload if isinstance(payload, list) else []
        if rows and isinstance(rows[0], dict):
            return _translate_row(rows[0])
        return None

    def list_catalog_apis(
        self,
        limit: int,
        query: Optional[str] = None,
    ) -> ApiCatalogPage:
        params: Dict[str, str] = {
            "_limit": str(limit),
            "orderBy": "apiId",
            "sort": "asc",
            "onlyMyContextApi": "false",
        }
        if query:
            params["customSearch"] = _build_custom_search(query)

        payload, response_headers = self._request(
            "GET",
            "apis",
            base_path=FINDER_BASE_PATH,
            report_client_errors=False,
            return_headers=True,
            params=params,
        )

        rows = payload if isinstance(payload, list) else []
        entries = [
            entry
            for entry in (_translate_row(row) for row in rows if isinstance(row, dict))
            if entry is not None
        ]
        return ApiCatalogPage(rows=entries, total=self._parse_total(response_headers))

    @staticmethod
    def _parse_total(headers: Dict[str, str]) -> int:
        raw = headers.get("count")
        try:
            return int(raw) if raw is not None else -1
        except (TypeError, ValueError):
            logger.warning("api-finder count header missing; degrading total")
            return -1

    def get_api_by_id(self, api_id: int | None = None) -> Dict[str, Any]:
        target_id = api_id if api_id is not None else self.api_id
        endpoint = f"apis/{target_id}"
        return self._request("GET", endpoint)

    def get_workflow_stages(self, workflow_id: int) -> List[WorkflowStage]:
        if workflow_id in self._stages_cache:
            return self._stages_cache[workflow_id]

        endpoint = f"workflows/{workflow_id}/stages"
        try:
            stages = self._request("GET", endpoint, base_path=GOVERNANCE_BASE_PATH)
        except Exception as exc:
            logger.warning(
                "workflow stages unavailable; degrading to empty catalog (%s)",
                type(exc).__name__,
            )
            return []

        rows = stages if isinstance(stages, list) else []
        normalized: List[WorkflowStage] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            stage_id = _wire_int(row.get("workflowStageId"))
            if stage_id is None:
                continue
            normalized.append(
                WorkflowStage(
                    workflowStageId=stage_id,
                    workflowStageName=_wire_str(row.get("workflowStageName")),
                )
            )
        self._stages_cache[workflow_id] = normalized
        return normalized

    def get_custom_interceptor_by_id(self, custom_interceptor_id: int) -> Dict[str, str] | None:
        endpoint = f"custom-interceptors/{custom_interceptor_id}"

        json_response = self._request("GET", endpoint)
        formatted_content = {"id": json_response["id"], "name": json_response["name"],
                             "script": json_response["script"]}

        return formatted_content

    def publish_api_changes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        endpoint = "revisions"
        return self._request("POST", endpoint=endpoint, json=data)
