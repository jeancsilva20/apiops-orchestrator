import logging
from typing import Dict, Any, List, Optional

from apiops_orchestrator.domain.ports.manager_api_port import ApiCatalogPage, ManagerApiPort
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.infrastructure.utils.http_client import HttpClient

logger = logging.getLogger(__name__)

GOVERNANCE_BASE_PATH = "/api-governance/api/v3/"
FINDER_BASE_PATH = "/api-finder/api/v3/"
# Rotas derivadas do catalogo sao insumo ( nao endpoint ): lista de revisoes por
# API vem do propio payload da API (sondas r4: revisions[] completa em /apis/{id}).


class ManagerApiAdapter(ManagerApiPort):
    def __init__(self, token: str, base_path: str, max_retries: int, api_id: int, settings: Settings):
        self.host = settings.HOST
        self.token = token
        self.api_id = api_id
        self.base_path = base_path
        self.max_retries = max_retries
        # Cache por EXECUCAO (processo morre junto): 1 chamada por workflow
        # distinto, nunca por linha de revisao (regra selada na spec).
        self._stages_cache: Dict[int, List[Dict[str, Any]]] = {}

    def _get_headers(self) -> Dict[str, str]:
        """Standard headers for all calls."""
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
        """GET to retrieve all APIs"""
        endpoint = "apis"
        return self._request("GET", endpoint)

    def list_api_detail(self, api_id: int) -> Optional[Dict[str, Any]]:
        """Detalhe da API no catálogo (api-finder); None quando 0 rows."""
        url = f"{self.host}{FINDER_BASE_PATH}apis"
        payload, _ = HttpClient.request(
            method="GET",
            url=url,
            headers=self._get_headers(),
            max_retries=self.max_retries,
            report_client_errors=False,
            return_headers=True,
            params={"customSearch": f"(apiId:{api_id})"},
        )

        rows = payload if isinstance(payload, list) else []
        return rows[0] if rows and isinstance(rows[0], dict) else None

    def list_catalog_apis(
        self,
        limit: int,
        order_by: str = "apiId",
        sort: str = "asc",
    ) -> ApiCatalogPage:
        """Catalogo api-finder (fonte da listagem) — `count` no header = total.

        Params medidos (sondas r5): `_limit` truncante; skip/offset/page inertes;
        orderBy/sort validos (determinismo: apiId asc). onlyMyContextApi=false:
        visibilidade = conta do cliente.
        """
        url = f"{self.host}{FINDER_BASE_PATH}apis"
        payload, response_headers = HttpClient.request(
            method="GET",
            url=url,
            headers=self._get_headers(),
            max_retries=self.max_retries,
            report_client_errors=False,  # UX própria do `sen list` (E1/D1-b)
            return_headers=True,
            params={
                "_limit": str(limit),
                "orderBy": order_by,
                "sort": sort,
                "onlyMyContextApi": "false",
            },
        )

        rows = payload if isinstance(payload, list) else []
        return ApiCatalogPage(rows=rows, total=self._parse_total(response_headers))

    @staticmethod
    def _parse_total(headers: Dict[str, str]) -> int:
        """Header `count` = tamanho do universo; degrada sem o metadado."""
        raw = headers.get("count")
        try:
            return int(raw) if raw is not None else -1
        except (TypeError, ValueError):
            logger.warning("api-finder count header missing; degrading total")
            return -1

    def get_api_by_id(self, api_id: int | None = None) -> Dict[str, Any]:
        """GET to retrieve the API data"""
        target_id = api_id if api_id is not None else self.api_id
        endpoint = f"apis/{target_id}"
        return self._request("GET", endpoint)

    def get_revisions_basic(self) -> list[Dict[str, Any]]:
        """GET the basic revisions catalog (single call covering all APIs)."""
        endpoint = "revisions/basic"
        return self._request("GET", endpoint)

    def get_revision_completeness(self, revision_id: int) -> Dict[str, Any]:
        """GET completeness; backend delega ao Adaptive Governance. Degrada silenciosamente para {}:
        a grade exibe '-' e a execucao continua (nunca quebra o drill-down).
        """
        try:
            return self._request("GET", f"revisions/{revision_id}/completeness")
        except Exception:
            # Sem eco de ids/valores (ADR 0005): evento booleano basta.
            logger.warning("revision completeness unavailable; degrading to empty")
            return {}

    def get_workflow_stages(self, workflow_id: int) -> list[Dict[str, Any]]:
        """GET stages catalog com cache por workflow (hit = zero rede).

        Falha -> lista vazia (CLI degrada mostrando o id do workflow);
        somente SUCESSO entra no cache (retry natural na proxima chamada).
        """
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

        normalized: List[Dict[str, Any]] = stages if isinstance(stages, list) else []
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