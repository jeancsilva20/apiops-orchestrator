import time

import requests
import typer
from requests.auth import HTTPBasicAuth

from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.ports.authentication_port import AuthenticationPort
from apiops_orchestrator.infrastructure.utils.retry_util import RetryUtil
from rich import print as rprint


class SensediaAuthenticationAdapter(AuthenticationPort):
    def __init__(self, base_path: str, max_retries: int, settings: Settings) -> None:
        self.base_path = base_path
        self.max_retries = max_retries
        self.settings = settings

    def authenticate(self) -> str | None:
        try:
            user = self.settings.OAUTH_CLIENT_ID
            password = self.settings.OAUTH_CLIENT_SECRET
            host = self.settings.HOST
            basic = HTTPBasicAuth(user, password)
            headers = {} # Add additional headers
            payload = {"grantType": "client_credentials", "scope": "apis/all"}
            url = f"{host}/{self.base_path}/oauth2/token"

            response_data = RetryUtil.http_request(
                method="POST",
                url=url,
                headers=headers,
                auth=basic,
                json=payload,
                max_retries=self.max_retries
            )

            return response_data["access_token"]
        except Exception as error:
            rprint({"error": str(error)})
            raise typer.Exit(code=1)

