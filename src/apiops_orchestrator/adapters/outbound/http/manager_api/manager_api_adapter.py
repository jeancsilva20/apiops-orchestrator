import requests
import time
from typing import Dict, Any
from apiops_orchestrator.domain.ports.manager_api_port import PublisherPort
from apiops_orchestrator.config.settings import Settings

class ManagerApiAdapter(PublisherPort):
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

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.request(method, url, headers=headers, **kwargs)
                if 500 <= response.status_code < 600:
                    print(f"Error {response.status_code} ({attempt}/{self.max_retries} try)")
                    if attempt < self.max_retries:
                        time.sleep(5)
                        continue
                    else:
                        raise Exception(f"Failed after {self.max_retries} tries")

                response.raise_for_status()

                return response.json()

            except requests.exceptions.RequestException:
                raise

    def get_api_by_id(self) -> Dict[str, Any]:
        """GET to retrieve the API data"""
        endpoint = f"apis/{self.api_id}"
        return self._request("GET", endpoint)