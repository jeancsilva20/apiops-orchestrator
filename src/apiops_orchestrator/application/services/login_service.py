import logging

import typer
from pydantic import ValidationError

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
from apiops_orchestrator.domain.models.login_session_model import (
    PROFILE_DEVELOPER,
    PROFILE_SUPER_ADMIN,
    LoginSession,
)
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
    "extra_info",
)

PROFILE_REQUIRED_FIELDS = {
    PROFILE_DEVELOPER: ("scope", "user_name", "user_email", "user_groups"),
    PROFILE_SUPER_ADMIN: ("scope", "admin_access_token"),
}

PAYLOAD_INVALID_MESSAGE = "Falha na autenticação. " "Tente efetuar login novamente."


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
        """Translate the wire payload (snake_case with `extra_info` envelope) into
        a LoginSession (camelCase). Protocol violations raise a single generic
        message; supporting details (field names only) go to the internal log."""
        raw = dict(raw_response or {})
        candidate = raw.get("extra_info")
        extra_info = candidate if isinstance(candidate, dict) else None
        missing = [field for field in REQUIRED_SESSION_FIELDS if not raw.get(field)]
        if extra_info is None or missing:
            self._log_payload_invalid(
                missing or ["extra_info"], reason="missing_core_fields"
            )
            raise LoginProtocolError(PAYLOAD_INVALID_MESSAGE)
        try:
            profile = str(extra_info.get("profile") or "")
            if profile not in PROFILE_REQUIRED_FIELDS:
                self._log_payload_invalid(
                    ["profile"], reason=f"unsupported_profile={profile}"
                )
                raise LoginProtocolError(PAYLOAD_INVALID_MESSAGE)
            if str(raw.get("token_type") or "").lower() != "bearer":
                self._log_payload_invalid(
                    ["token_type"], reason="unsupported_token_type"
                )
                raise LoginProtocolError(PAYLOAD_INVALID_MESSAGE)
            missing_by_profile = [
                field
                for field in PROFILE_REQUIRED_FIELDS[profile]
                if not extra_info.get(field)
            ]
            if missing_by_profile:
                self._log_payload_invalid(
                    missing_by_profile, reason=f"missing_{profile}_fields"
                )
                raise LoginProtocolError(PAYLOAD_INVALID_MESSAGE)
            return self._build_session(profile, extra_info, raw)
        except (TypeError, ValueError, KeyError, ValidationError) as exc:
            self._log_payload_invalid(
                [type(exc).__name__], reason="session_construction_failed"
            )
            raise LoginProtocolError(PAYLOAD_INVALID_MESSAGE) from exc

    @staticmethod
    def _build_session(profile: str, extra_info: dict, raw: dict) -> LoginSession:
        """Map wire keys (route contract, snake_case) to model fields (camelCase)."""
        session_input = {
            "accessToken": str(raw["access_token"]),
            "tokenType": str(raw["token_type"]),
            "expiresIn": int(raw["expires_in"]),
            "scope": str(extra_info["scope"]),
            "profile": profile,
        }
        if profile == PROFILE_DEVELOPER:
            session_input.update(
                {
                    "userName": str(extra_info["user_name"]),
                    "userEmail": str(extra_info["user_email"]),
                    "userGroups": [str(group) for group in extra_info["user_groups"]],
                }
            )
        else:
            session_input.update(
                {"adminAccessToken": str(extra_info["admin_access_token"])}
            )
        return LoginSession(**session_input)

    @staticmethod
    def _log_payload_invalid(fields, reason: str) -> None:
        """Details are restricted to field names/shape labels, never payload values."""
        logger.error(
            "auth.login.payload_invalid reason=%s fields=%s", reason, ",".join(fields)
        )

    def _persist(self, session: LoginSession) -> None:
        try:
            self.session_store.save(session)
        except SessionStorageError as exc:
            raise SessionPersistenceError(str(exc)) from exc
