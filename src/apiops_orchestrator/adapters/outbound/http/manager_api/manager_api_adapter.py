import logging
import re
from typing import Dict, Any, List, Optional

from apiops_orchestrator.adapters.outbound.http.common.platform_request import (
    bearer_headers,
    platform_error_items,
    platform_request,
    rejection_signal,
)
from apiops_orchestrator.domain.ports.manager_api_port import (
    ApiCatalogPage,
    ManagerApiGovernanceBlockedError,
    ManagerApiPort,
    ManagerApiTransportRejectedError,
    ManagerApiUnexpectedResponseError,
)
from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from apiops_orchestrator.domain.models.api_visibility_model import OwnershipContext
from apiops_orchestrator.domain.models.catalog_revision_model import (
    CatalogRevision,
    CatalogRevisionCompleteness,
)
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.infrastructure.exceptions.http_client_exceptions import (
    HttpClient4xxError,
)

logger = logging.getLogger(__name__)

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


_GOVERNANCE_VALIDATE_PATH = re.compile(r"/api-governance/.*/workflows/(\d+)/validate")


def _governance_workflow_id(body: Any) -> Optional[int]:
    """Workflow that blocked the write, from the error `path` — None if not governance."""
    for item in platform_error_items(body):
        path = item.get("path") if isinstance(item, dict) else None
        match = _GOVERNANCE_VALIDATE_PATH.search(path) if isinstance(path, str) else None
        if match:
            return int(match.group(1))
    return None


def _manager_rejection(
    exc: HttpClient4xxError, fields: Dict[str, Any]
) -> ManagerApiTransportRejectedError:
    """Signal of a Manager 4xx: a 412 from the Adaptive Governance blocks the write."""
    workflow_id = _governance_workflow_id(exc.body) if exc.status_code == 412 else None
    if workflow_id is not None:
        logger.info("manager_api.governance.blocked workflow_id=%s", workflow_id)
        return ManagerApiGovernanceBlockedError(
            workflow_id=workflow_id,
            raw=exc.body if isinstance(exc.body, dict) else None,
            **fields,
        )
    return rejection_signal(exc, fields)


def _build_custom_search(query: str) -> str:
    sanitized = "".join(ch for ch in query if ch not in '"()')
    return f'(apiName:"{sanitized}" OR description:"{sanitized}")'


def _translate_completeness(raw: Any) -> CatalogRevisionCompleteness:
    """Traduz o CompletenessBean do Manager para a leitura tipada de domínio."""
    payload = raw if isinstance(raw, dict) else {}
    texts = (
        item if isinstance(item, str) else str(item)
        for item in (payload.get("suggestions") or [])
        if item is not None
    )
    suggestions = [stripped for stripped in (text.strip() for text in texts) if stripped]
    score = _wire_float(payload.get("completenessScore"))
    return CatalogRevisionCompleteness(
        score=score if score is not None else 0.0,
        suggestions=suggestions,
    )


class ManagerApiAdapter(ManagerApiPort):
    def __init__(self, token: str, base_path: str, max_retries: int, api_id: Optional[int] = None, settings: Optional[Settings] = None):
        self.host = settings.HOST if settings is not None else None
        self.token = token
        # LEGADO: id fixo, fallback de `get_api_by_id` usado pelo `VersionerService`;
        # os comandos sempre passam o id.
        self.api_id = api_id
        self.base_path = base_path
        self.max_retries = max_retries

    def _get_headers(self) -> Dict[str, str]:
        return bearer_headers(self.token)

    def _request(
        self,
        method: str,
        endpoint: str,
        base_path: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Executa a chamada e traduz transporte → sinais do port."""
        path_prefix = base_path if base_path is not None else self.base_path
        return platform_request(
            method,
            f"{self.host or ''}{path_prefix}{endpoint}",
            headers=self._get_headers(),
            max_retries=self.max_retries,
            log_prefix="manager_api",
            rejection=_manager_rejection,
            **kwargs,
        )

    def get_apis(self) -> list[Dict[str, Any]]:
        endpoint = "apis"
        return self._request("GET", endpoint)

    def list_api_detail(self, api_id: int) -> Optional[ApiCatalogEntry]:
        payload, _ = self._request(
            "GET",
            "apis",
            base_path=FINDER_BASE_PATH,
            return_headers=True,
            params={"customSearch": f"(apiId:{api_id})"},
        )

        rows = payload if isinstance(payload, list) else []
        if rows and isinstance(rows[0], dict):
            return _translate_row(rows[0])
        return None

    def get_revision_completeness(self, revision_id: int) -> CatalogRevisionCompleteness:
        endpoint = f"revisions/{revision_id}/completeness"
        payload = self._request("GET", endpoint)
        return _translate_completeness(payload)

    def list_catalog_apis(
        self,
        limit: int,
        offset: int = 0,
        query: Optional[str] = None,
    ) -> ApiCatalogPage:
        params: Dict[str, str] = {
            "_limit": str(limit),
            "_offset": str(offset),
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

    def get_custom_interceptor_by_id(self, custom_interceptor_id: int) -> Dict[str, str] | None:
        """Custom do catálogo, ou `None` quando o id não existe mais.

        O `404` é desfecho **esperado**: ids de Custom são estáveis dentro de um
        ambiente, mas um repositório que mudou de ambiente pode referenciar id
        inexistente. Deixar o `ManagerApiTransportRejectedError` subir faria isso
        virar falha de transporte, quando é informação de negócio — quem decide o
        que fazer com a ausência é a camada de aplicação.
        """
        endpoint = f"custom-interceptors/{custom_interceptor_id}"

        try:
            json_response = self._request("GET", endpoint)
        except ManagerApiTransportRejectedError as exc:
            if exc.status_code == 404:
                logger.info(
                    "manager_api.custom_interceptor.ausente id=%s", custom_interceptor_id
                )
                return None
            raise

        return {
            "id": json_response.get("id"),
            "name": json_response.get("name"),
            "script": json_response.get("script"),
        }

    def publish_api_changes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """LEGADO: cria revisão (`POST /revisions`). Nenhum comando usa; mantido para o versionamento futuro."""
        endpoint = "revisions"
        return self._request("POST", endpoint=endpoint, json=data)

    def get_revision(self, revision_id: int) -> Dict[str, Any]:
        return self._request("GET", f"revisions/{revision_id}")

    def update_revision(
        self, revision_id: int, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """PUT denso na revisão — atualiza a existente, nunca cria (D-005 §9)."""
        return self._request("PUT", f"revisions/{revision_id}", json=payload)

    def get_revision_swagger(self, revision_id: int) -> Dict[str, Any]:
        document = self._request("GET", f"revisions/{revision_id}/swagger")
        if not isinstance(document, dict):
            logger.info("manager_api.swagger.unexpected_body revision_id=%s", revision_id)
            raise ManagerApiUnexpectedResponseError(
                "Manager API returned a non-JSON swagger document"
            )
        return document

    def update_revision_swagger(
        self, revision_id: int, document: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self._request("PUT", f"revisions/{revision_id}/swagger", json=document)

    def deploy_revision(self, environment_id: int, revision_id: int) -> Optional[int]:
        response = self._request(
            "POST",
            "deployments",
            json={
                "environmentId": environment_id,
                "revisionId": revision_id,
                "status": "DEPLOYED",
            },
        )
        return _wire_int(response.get("id")) if isinstance(response, dict) else None
