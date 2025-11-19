import time

import requests
import typer
from requests.auth import HTTPBasicAuth

from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.ports.authentication_port import AuthenticationPort
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

            for attempt in range(1, self.max_retries + 1):
                r = requests.post(f"{host}/{self.base_path}/oauth2/token", auth=basic, headers=headers, json=payload)
                if 500 <= r.status_code < 600:
                    print(f"Error {r.status_code} ({attempt}/{self.max_retries} try)")
                    if attempt < self.max_retries:
                        time.sleep(5)
                        continue
                    else:
                        raise Exception(f"failed after {self.max_retries} tries")
                return r.json()["access_token"]
        except Exception as error:
            rprint({"error": str(error)})
            raise typer.Exit(code=1)

