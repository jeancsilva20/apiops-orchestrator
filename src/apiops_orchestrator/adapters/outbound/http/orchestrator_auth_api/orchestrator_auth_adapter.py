import logging
from typing import cast

from requests.exceptions import RequestException

from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.ports.orchestrator_auth_port import (
    AuthEndpointNotConfiguredError,
    AuthTransportRejectedError,
    AuthTransportUnavailableError,
    OrchestratorAuthPort,
)
from apiops_orchestrator.infrastructure.exceptions.http_client_exceptions import (
    HttpClient4xxError,
    HttpClientServerError,
)
from apiops_orchestrator.infrastructure.observability.logging import log_duration
from apiops_orchestrator.infrastructure.utils.http_client import HttpClient

logger = logging.getLogger(__name__)

DEFAULT_VALIDATE_SUFFIX = "/validation"


def build_login_url(settings: Settings) -> str:
    """Builds the login URL exclusively from AUTH_HOST and AUTH_LOGIN_PATH (no fallback, no default).

    Falha de configuração é parte do contrato do port: sinais tipados, nunca
    RuntimeError cru.
    """
    host = settings.AUTH_HOST
    path = settings.AUTH_LOGIN_PATH
    if not host:
        raise AuthEndpointNotConfiguredError(
            missing_keys=["AUTH_HOST"],
            message="Endpoint de autenticação não configurado: defina AUTH_HOST.",
        )
    if not (path and path.strip()):
        raise AuthEndpointNotConfiguredError(
            missing_keys=["AUTH_LOGIN_PATH"],
            message="Path de autenticação não configurado: defina AUTH_LOGIN_PATH.",
        )
    return f"{host.rstrip('/')}/{path.strip().lstrip('/')}"


def build_validate_url(settings: Settings) -> str:
    """Builds the validate URL from AUTH_HOST; default = AUTH_LOGIN_PATH + `/validation`."""
    host = settings.AUTH_HOST
    if not host:
        raise AuthEndpointNotConfiguredError(
            missing_keys=["AUTH_HOST"],
            message="Endpoint de autenticação não configurado: defina AUTH_HOST.",
        )
    suffix = settings.AUTH_VALIDATE_PATH or f"{settings.AUTH_LOGIN_PATH.rstrip('/')}{DEFAULT_VALIDATE_SUFFIX}"
    return f"{host.rstrip('/')}/{suffix.strip().lstrip('/')}"


class OrchestratorAuthAdapter(OrchestratorAuthPort):
    """Adapter HTTP do port `OrchestratorAuthPort`.

    Fronteira de tradução transporte → sinais do port:
    - guard de configuração (fail-fast, pré-rede) → `AuthEndpointNotConfiguredError`;
    - HttpClient 4xx → `AuthTransportRejectedError`;
    - 5xx pós-retries / falhas de rede → `AuthTransportUnavailableError`.
    """

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
        return cast(
            dict,
            self._send(
                method="POST",
                url=url,
                headers=headers,
                json=payload,
            ),
        )

    def validate_access_token(self, access_token: str) -> dict:
        url = build_validate_url(self.settings)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        logger.info("Requesting access token validation")
        return cast(
            dict,
            self._send(
                method="POST",
                url=url,
                headers=headers,
                json={},
            ),
        )

    def _send(self, *, method: str, url: str, headers: dict, json: dict) -> dict:
        """Executa a requisição e traduz transport → sinais do port.

        Qualquer sinal do port re-levantado aqui passa direto; as exceções
        tipadas do HttpClient compartilhado (4xx/5xx-tipado) e exceções de
        rede requests tornam-se os DOIS resultados de falha do port.
        Demais exceções inesperadas atravessam (rede de segurança no caller).
        """
        try:
            with log_duration(f"{__name__}.{method.lower()}"):
                return cast(
                    dict,
                    HttpClient.request(
                        method=method,
                        url=url,
                        headers=headers,
                        max_retries=self.max_retries,
                        json=json,
                    ),
                )
        except HttpClient4xxError as exc:
            logger.info("auth.transport.rejected status_code=%s", exc.status_code)
            raise AuthTransportRejectedError(
                f"Auth API rejected the request (HTTP {exc.status_code})"
            ) from exc
        except HttpClientServerError as exc:
            logger.info("auth.transport.unavailable reason=server_error")
            raise AuthTransportUnavailableError(str(exc)) from exc
        except RequestException as exc:
            logger.info("auth.transport.unavailable reason=connection_failure")
            raise AuthTransportUnavailableError(
                "Auth API connection failed or timed out"
            ) from exc
