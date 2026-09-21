import logging

from apiops_orchestrator.adapters.outbound.http.orchestrator_auth_api.orchestrator_auth_adapter import (
    OrchestratorAuthAdapter,
    build_login_url,
)
from apiops_orchestrator.application.exceptions.login_exceptions import (
    AuthenticationUnavailableError,
    CredentialNotFoundError,
    LoginError,
    LoginProtocolError,
)
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.ports.orchestrator_auth_port import OrchestratorAuthPort
from apiops_orchestrator.infrastructure.observability.logging import log_duration
from apiops_orchestrator.infrastructure.secure_storage.session_store import SessionStore

logger = logging.getLogger(__name__)

RESOLUTION_MAX_RETRIES = 3


def resolve_admin_token(settings: Settings) -> str:
    """Ponto único de obtenção do token super admin para comandos do manager.

    Compõe (OrchestratorAuthAdapter + AdminTokenProvider + SessionStore) e
    devolve o token pronto para uso como Bearer — sessão `.sen_session`
    válida primeiro, rota de login com `ADMIN_LOGIN_CREDENTIALS` em seguida.
    Todo comando que tocar APIs administrativas DEVE passar por aqui; ponto
    futuro de validação de token (ex.: perfis não super admin obtidos via
    OAuth) entra na mesma função, não nos chamadores.
    """
    return AdminTokenProvider(
        auth_adapter=OrchestratorAuthAdapter(settings=settings, max_retries=RESOLUTION_MAX_RETRIES),
        settings=settings,
        session_store=SessionStore(directory=settings.PACKAGE_ROOT),
    ).obtain()


class AdminTokenProvider:
    """Resolve o token super admin para comandos administrativos.

    Ordem de precedência (ADR 0002 rev., openspec add-sen-list):

    1. Sessão super-admin válida em `.sen_session` com `adminAccessToken`
       presente → usa o token pronto (zero rede de autenticação);
    2. Caso contrário (dev ou sessão inutilizável) → loga como super admin na
       MESMA rota de login (`AUTH_HOST`/`AUTH_LOGIN_PATH`) usando a credencial
       dedicada `ADMIN_LOGIN_CREDENTIALS` e usa o `admin_access_token`
       retornado em memória (nada persistido, nada logado — ADR 0005).
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
        from_session = self._token_from_session()
        if from_session:
            logger.info("auth.admin_token.source resolved_from=session")
            return from_session
        logger.info("auth.admin_token.source resolved_from=login_route")
        credential = self._resolve_admin_login_credential()
        self._guard_endpoint_configured()
        raw_response = self._perform_login(credential)
        return self._extract_admin_token(raw_response)

    def _token_from_session(self) -> str | None:
        """Sessão super-admin não expirada com token privilegiado → usa pronto.

        Sessão expirada, ausente, de perfil developer (sem admin token) ou
        legada sem token devolvem None e caem no caminho de obtenção por
        credencial. Qualquer falha de leitura é silenciosa aqui (o store já
        trata corrupta/expirada como ausente).
        """
        try:
            session = self.session_store.load()
        except Exception:
            logger.info("auth.admin_token.session_read_failed")
            return None
        if session is None or not session.is_super_admin or session.is_expired():
            return None
        return session.adminAccessToken or None

    def _resolve_admin_login_credential(self) -> str:
        value = (self.settings.ADMIN_LOGIN_CREDENTIALS or "").strip()
        if not value:
            raise CredentialNotFoundError(
                "Credencial de administração não encontrada: defina ADMIN_LOGIN_CREDENTIALS no "
                "arquivo .env (blob Base64 de client_id:secret do perfil super admin) e rode "
                "`sen list api` novamente."
            )
        return value

    def _guard_endpoint_configured(self) -> None:
        try:
            build_login_url(self.settings)
        except RuntimeError as exc:
            detail = str(exc)
            if "AUTH_LOGIN_PATH" in detail:
                raise LoginError(
                    "Path de autenticação não configurado: defina AUTH_LOGIN_PATH."
                ) from exc
            raise LoginError(
                "Endpoint de autenticação não configurado: defina AUTH_HOST."
            ) from exc

    def _perform_login(self, credential: str) -> dict:
        try:
            with log_duration("auth.admin_token.request"):
                return self.auth_adapter.login(credential)
        except LoginError:
            raise
        except Exception:
            logger.exception("auth.admin_token.network_failure")
            raise AuthenticationUnavailableError(
                "API de autenticação indisponível ou falha de conexão após tentativas."
            )

    @staticmethod
    def _extract_admin_token(raw_response: dict) -> str:
        raw = dict(raw_response or {})
        extra_info = raw.get("extra_info") if isinstance(raw.get("extra_info"), dict) else {}
        token = extra_info.get("admin_access_token") if extra_info else None
        if not token:
            logger.error(
                "auth.admin_token.payload_invalid reason=missing_admin_access_token"
            )
            raise LoginProtocolError(
                "Resposta da autenticação sem token administrativo. "
                "Tente efetuar login novamente ou verifique a credencial de administração."
            )
        return str(token)
