import logging
from typing import cast

from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.ports.orchestrator_auth_port import OrchestratorAuthPort
from apiops_orchestrator.infrastructure.utils.http_client import HttpClient

logger = logging.getLogger(__name__)


def build_login_url(settings: Settings) -> str:
    """Builds the login URL exclusively from AUTH_HOST and AUTH_LOGIN_PATH (no fallback, no default)."""
    host = settings.AUTH_HOST
    path = settings.AUTH_LOGIN_PATH
    if not host:
        raise RuntimeError("Auth endpoint is not configured (AUTH_HOST)")
    if not (path and path.strip()):
        raise RuntimeError("Auth login path is not configured (AUTH_LOGIN_PATH)")
    return f"{host.rstrip('/')}/{path.strip().lstrip('/')}"


class OrchestratorAuthAdapter(OrchestratorAuthPort):
    def __init__(self, settings: Settings, max_retries: int = 3) -> None:
        self.settings = settings
        self.max_retries = max_retries

    def login(self, credential_b64: str) -> dict:
        url = build_login_url(self.settings)
        headers = {
            "Authorization": f"Basic {credential_b64}",
            "Content-Type": "application/json",
        }
        payload = {"grantType": "client_credentials", "scope": "apis/all"}

        logger.info("Requesting auth login to configured endpoint")
        response_data = HttpClient.request(
            method="POST",
            url=url,
            headers=headers,
            max_retries=self.max_retries,
            report_client_errors=False,
            json=payload,
        )
        return cast(dict, response_data)
