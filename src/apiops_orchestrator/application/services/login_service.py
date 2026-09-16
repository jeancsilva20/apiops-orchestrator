import logging

import typer

from apiops_orchestrator.adapters.outbound.http.orchestrator_auth_api.orchestrator_auth_adapter import (
    build_login_url,
)
from apiops_orchestrator.application.exceptions.login_exceptions import (
    AuthenticationRejectedError,
    AuthenticationUnavailableError,
    CredentialNotFoundError,
    LoginError,
    LoginProtocolError,
    SessionPersistenceError,
)
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.ports.orchestrator_auth_port import OrchestratorAuthPort
from apiops_orchestrator.infrastructure.observability.logging import (
    clear_operation_context,
    log_duration,
    set_span_id,
    set_status,
)
from apiops_orchestrator.infrastructure.secure_storage.session_store import (
    SessionStorageError,
    SessionStore,
)

logger = logging.getLogger(__name__)

REQUIRED_SESSION_FIELDS = (
    "access_token",
    "token_type",
    "expires_in",
    "user_groups",
    "user_email",
    "username",
)


def resolve_credential(settings: Settings) -> str:
    """Single credential source: SEN_CREDENTIALS (Base64 blob passed intact). No fallback."""
    value = (getattr(settings, "SEN_CREDENTIALS", None) or "").strip()
    if not value:
        raise CredentialNotFoundError(
            "Credencial não encontrada: configure a variável SEN_CREDENTIALS "
            "(blob Base64 de client_id:secret) e rode `sen login` novamente."
        )
    return value


class LoginService:
    def __init__(
        self,
        auth_adapter: OrchestratorAuthPort,
        session_store: SessionStore,
        settings: Settings,
    ) -> None:
        self.auth_adapter = auth_adapter
        self.session_store = session_store
        self.settings = settings

    def login(self) -> LoginSession:
        set_span_id()
        set_status("IN PROGRESS")
        logger.info("auth.login.started")
        try:
            credential = self._resolve_inputs()
            raw_response = self._perform_login(credential)
            session = self._parse_response(raw_response)
            self._persist(session)
        except LoginError as exc:
            set_status("FAILURE")
            logger.info("auth.login.failure category=%s", type(exc).__name__)
            clear_operation_context()
            raise
        set_status("SUCCESS")
        logger.info("auth.login.success")
        clear_operation_context()
        return session

    def _resolve_inputs(self) -> str:
        credential = resolve_credential(self.settings)
        logger.info("auth.credentials.source resolved_from=SEN_CREDENTIALS")
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
        return credential

    def _perform_login(self, credential: str) -> dict:
        try:
            with log_duration("auth.login.request"):
                return self.auth_adapter.login(credential)
        except typer.Exit:
            raise AuthenticationRejectedError(
                "Credencial recusada pela API de autenticação (erro HTTP 4xx)."
            )
        except LoginError:
            raise
        except Exception:
            logger.exception("auth.login.network_failure")
            raise AuthenticationUnavailableError(
                "API de autenticação indisponível ou falha de conexão após tentativas."
            )

    def _parse_response(self, raw_response: dict) -> LoginSession:
        missing = [
            field for field in REQUIRED_SESSION_FIELDS if not raw_response.get(field)
        ]
        if missing:
            raise LoginProtocolError(
                "Resposta de login incompleta. Campos obrigatórios ausentes: "
                + ", ".join(missing)
            )
        if str(raw_response.get("token_type")).lower() != "bearer":
            raise LoginProtocolError(
                "token_type retornado não é suportado (esperado: Bearer)."
            )
        try:
            expires_in = int(raw_response["expires_in"])
            session = LoginSession(
                access_token=str(raw_response["access_token"]),
                token_type=str(raw_response["token_type"]),
                expires_in=expires_in,
                user_groups=list(raw_response["user_groups"]),
                user_email=str(raw_response["user_email"]),
                username=str(raw_response["username"]),
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise LoginProtocolError(
                "Resposta de login com campos em formato inválido."
            ) from exc
        return session

    def _persist(self, session: LoginSession) -> None:
        try:
            self.session_store.save(session)
        except SessionStorageError as exc:
            raise SessionPersistenceError(str(exc)) from exc
