import logging

from apiops_orchestrator.adapters.outbound.http.orchestrator_auth_api.orchestrator_auth_adapter import (
    OrchestratorAuthAdapter,
    build_validate_url,
)
from apiops_orchestrator.application.exceptions.login_exceptions import (
    AuthenticationRejectedError,
    LoginError,
)
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.ports.orchestrator_auth_port import OrchestratorAuthPort
from apiops_orchestrator.infrastructure.observability.logging import log_duration
from apiops_orchestrator.infrastructure.secure_storage.session_store import SessionStore

logger = logging.getLogger(__name__)

RESOLUTION_MAX_RETRIES = 3


def resolve_admin_token(settings: Settings) -> str:
    """Compõe adapter + provider + store e devolve o admin token (Bearer pronto).

    Precedência: sessão super-admin com `adminAccessToken` no `.sen_session`
    → accessToken devorial validado na rota validate. Único ponto para todo
    comando que tocar APIs administrativas.
    """
    return AdminTokenProvider(
        auth_adapter=OrchestratorAuthAdapter(settings=settings, max_retries=RESOLUTION_MAX_RETRIES),
        settings=settings,
        session_store=SessionStore(directory=settings.PACKAGE_ROOT),
    ).obtain()


class AdminTokenProvider:
    """Resolve o token administrativo via sessão e rota validate.

    1. Sessão super-admin válida com `adminAccessToken` → usa pronto;
    2. Sessão válida (perfil dev) → POST validate com o `accessToken`;
    3. Qualquer outro retorno (não-200, autorizado!=true, admin token
       ausente) → 401 educativo: refaça `sen login`.
    """

    def __init__(
        self,
        auth_adapter: OrchestratorAuthPort,
        settings: Settings,
        session_store: SessionStore,
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
        self._guard_endpoint_configured()
        raw_response = self._perform_validate(dev_token)
        return self._extract_admin_token(raw_response)

    def _admin_token_from_session(self) -> str | None:
        try:
            session = self.session_store.load()
        except Exception:
            logger.info("auth.admin_token.session_read_failed")
            return None
        if session is None or not session.is_super_admin or session.is_expired():
            return None
        return session.adminAccessToken or None

    def _dev_access_token(self) -> str:
        """accessToken do dev; sessão ausente/expirada/sem token → 401 educativo."""
        try:
            session = self.session_store.load()
        except Exception:
            session = None
        if session is None or session.is_expired() or not (session.accessToken or "").strip():
            raise AuthenticationRejectedError(
                "Sessão inválida ou ausente: faça `sen login` e rode o comando novamente."
            )
        return session.accessToken

    def _guard_endpoint_configured(self) -> None:
        try:
            build_validate_url(self.settings)
        except RuntimeError:
            raise LoginError("Endpoint de validação não configurado: defina AUTH_HOST.")

    def _perform_validate(self, dev_token: str) -> dict:
        try:
            with log_duration("auth.admin_token.validate"):
                return self.auth_adapter.validate_access_token(dev_token)
        except Exception:
            # Qualquer coisa que não seja (200, autorizado=true, token) → 401 educativo.
            logger.info("auth.admin_token.validate.refused")
            raise AuthenticationRejectedError(
                "Validação não autorizou o acesso: faça `sen login` e tente novamente."
            )

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
