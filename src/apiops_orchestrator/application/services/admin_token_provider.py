import logging

from apiops_orchestrator.application.exceptions.login_exceptions import (
    AuthenticationRejectedError,
)
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.ports.orchestrator_auth_port import (
    AuthEndpointNotConfiguredError,
    AuthTransportRejectedError,
    AuthTransportUnavailableError,
    OrchestratorAuthPort,
)
from apiops_orchestrator.domain.ports.session_store_port import SessionStorePort
from apiops_orchestrator.infrastructure.observability.logging import log_duration

logger = logging.getLogger(__name__)


class AdminTokenProvider:
    """Resolve o token administrativo via sessão e rota validate.

    1. Sessão super-admin válida com `adminAccessToken` → usa pronto;
    2. Sessão válida (perfil dev) → POST validate com o `accessToken`;
    3. Qualquer outro retorno (não-200, autorizado!=true, admin token
       ausente) → 401 educativo: refaça `sen login`.

    Depende APENAS de ports (`OrchestratorAuthPort`, `SessionStorePort`);
    a montagem concreta é responsabilidade do composition root.
    """

    def __init__(
        self,
        auth_adapter: OrchestratorAuthPort,
        settings: Settings,
        session_store: SessionStorePort,
    ) -> None:
        self.auth_adapter = auth_adapter
        self.settings = settings
        self.session_store = session_store

    def obtain(self) -> str:
        from_session = self._admin_token_from_session()
        if from_session:
            logger.info("auth.admin_token.source resolved_from=session")
            return from_session

        logger.info("auth.admin_token.source resolved_from=validate_route")
        dev_token = self._dev_access_token()
        raw_response = self._perform_validate(dev_token)
        return self._extract_admin_token(raw_response)

    def _admin_token_from_session(self) -> str | None:
        session = self.session_store.load()
        if session is None or not session.is_super_admin or session.is_expired():
            return None
        return session.adminAccessToken or None

    def _dev_access_token(self) -> str:
        """accessToken do dev; sessão ausente/expirada/sem token → 401 educativo."""
        session = self.session_store.load()
        if session is None or session.is_expired() or not (session.accessToken or "").strip():
            raise AuthenticationRejectedError(
                "Sessão inválida ou ausente: faça `sen login` e rode o comando novamente."
            )
        return session.accessToken

    @staticmethod
    def _extract_admin_token(raw_response: dict) -> str:
        """(200, autorizado=true, admin_access_token presente) → token; resto → 401."""
        raw = dict(raw_response or {})
        authorized = raw.get("autorizado")
        extra_info = raw.get("extra_info") if isinstance(raw.get("extra_info"), dict) else {}
        token = extra_info.get("admin_access_token") if extra_info else None

        if authorized is not True:
            logger.info("auth.admin_token.authorized=false")
            raise AuthenticationRejectedError(
                "Erro na validação: faça `sen login` e tente novamente."
            )
        if not token:
            logger.error("auth.admin_token.payload_invalid reason=missing_admin_access_token")
            raise AuthenticationRejectedError(
                "Erro na validação: faça `sen login` e tente novamente."
            )
        return str(token)

    def _perform_validate(self, dev_token: str) -> dict:
        """Traduz os sinais do port em 401 educativo (contrato documentado).

        (200, autorizado=true, admin token presente) → payload; QUALQUER
        outra coisa — 4xx, 5xx/rede, config ausente, autorizado=false,
        token ausente — vira `AuthenticationRejectedError`: oriente re-login.
        """
        try:
            with log_duration("auth.admin_token.validate"):
                return self.auth_adapter.validate_access_token(dev_token)
        except AuthEndpointNotConfiguredError as exc:
            logger.info("auth.admin_token.validate.refused reason=endpoint_not_configured")
            raise AuthenticationRejectedError(
                "Erro na validação: faça `sen login` e tente novamente."
            ) from exc
        except AuthTransportRejectedError:
            logger.info("auth.admin_token.validate.refused reason=rejected")
            raise AuthenticationRejectedError(
                "Erro na validação: faça `sen login` e tente novamente."
            )
        except AuthTransportUnavailableError:
            logger.info("auth.admin_token.validate.refused reason=unavailable")
            raise AuthenticationRejectedError(
                "Erro na validação: faça `sen login` e tente novamente."
            )
        except Exception:
            logger.info("auth.admin_token.validate.refused reason=unexpected")
            raise AuthenticationRejectedError(
                "Erro na validação: faça `sen login` e tente novamente."
            )
