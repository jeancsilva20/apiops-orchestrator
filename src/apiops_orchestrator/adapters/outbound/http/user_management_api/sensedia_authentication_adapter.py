from requests.auth import HTTPBasicAuth
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.ports.authentication_port import AuthenticationPort
from apiops_orchestrator.infrastructure.utils.http_client import HttpClient


class SensediaAuthenticationAdapter(AuthenticationPort):
    def __init__(self, base_path: str, max_retries: int, settings: Settings) -> None:
        self.base_path = base_path
        self.max_retries = max_retries
        self.settings = settings

    def authenticate(self) -> str | None:
        user = self.settings.OAUTH_CLIENT_ID
        password = self.settings.OAUTH_CLIENT_SECRET
        host = self.settings.HOST
        basic = HTTPBasicAuth(user, password)

        headers = {}
        payload = {"grantType": "client_credentials", "scope": "apis/all"}
        url = f"{host}/{self.base_path}/oauth2/token"

        response_data = HttpClient.request(
            method="POST",
            url=url,
            headers=headers,
            max_retries=self.max_retries,
            auth=basic,
            json=payload
        )

        return response_data["access_token"]