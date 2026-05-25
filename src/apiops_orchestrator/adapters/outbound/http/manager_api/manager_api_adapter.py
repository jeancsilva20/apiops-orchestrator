import typer
from typing import Dict, Any
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.adapters.outbound.http.common.http_error_mapper import HttpErrorMapper
from apiops_orchestrator.infrastructure.utils.http_client import HttpClient

class ManagerApiAdapter(ManagerApiPort):
    def __init__(self, token: str, base_path: str, max_retries: int, api_id: int, settings: Settings):
        self.host = settings.HOST
        self.token = token
        self.api_id = api_id
        self.base_path = base_path
        self.max_retries = max_retries

    def _get_headers(self) -> Dict[str, str]:
        """Standard headers for all calls."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = f"{self.host}{self.base_path}{endpoint}"
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

    def get_api_by_id(self, api_id: int | None = None) -> Dict[str, Any]:
        """GET to retrieve the API data"""
        target_id = api_id if api_id is not None else self.api_id
        endpoint = f"apis/{target_id}"
        return self._request("GET", endpoint)

    def get_custom_interceptor_by_id(self, custom_interceptor_id: int) -> Dict[str, str] | None:
        endpoint = f"custom-interceptors/{custom_interceptor_id}"

        json_response = self._request("GET", endpoint)
        formatted_content = {"id": json_response["id"], "name": json_response["name"],
                             "script": json_response["script"]}

        return formatted_content

    def publish_api_changes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        endpoint = f"revisions"

        return self._request("POST", endpoint=endpoint, json=data)