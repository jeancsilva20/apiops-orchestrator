import logging
import os

from pydantic import ValidationError

from apiops_orchestrator.application.exceptions.login_exceptions import (
    AuthenticationRejectedError,
    AuthenticationUnavailableError,
    CredentialNotFoundError,
    LoginError,
    LoginProtocolError,
    SessionPersistenceError,
)
from apiops_orchestrator.config import settings as settings_module
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.login_session_model import (
    LOGIN_PROTOCOL_PROFILE_REQUIRED_KEYS,
    PROFILE_DEVELOPER,
    LoginSession,
)
from apiops_orchestrator.domain.ports.orchestrator_auth_port import (
    AuthEndpointNotConfiguredError,
    AuthTransportRejectedError,
    AuthTransportUnavailableError,
    OrchestratorAuthPort,
)
from apiops_orchestrator.domain.ports.session_store_port import (
    SessionStoreError,
    SessionStorePort,
)
from apiops_orchestrator.infrastructure.observability.logging import (
    clear_operation_context,
    log_duration,
    set_span_id,
    set_status,
)

logger = logging.getLogger(__name__)

REQUIRED_SESSION_FIELDS = (
    "access_token",
    "token_type",
    "expires_in",
    "extra_info",
)

PAYLOAD_INVALID_MESSAGE = "Falha na autenticação. " "Tente efetuar login novamente."


def resolve_credential(settings: Settings) -> str:
    """Single credential source: SEN_CREDENTIALS (Base64 blob passed intact). No fallback."""
    value = (getattr(settings, "SEN_CREDENTIALS", None) or "").strip()
    if not value:
        raise CredentialNotFoundError(
            "Credencial não encontrada: defina SEN_CREDENTIALS no arquivo .sen do diretório do aplicativo "
            "(blob Base64 de client_id:secret) e rode `sen login` novamente."
        )
    return value


class LoginService:
    """Casos de uso do fluxo `sen login`.

    Dependências: SOMENTE ports (`OrchestratorAuthPort`,
    `SessionStorePort`) e configuração. Nenhum import de adapter, infra
    ou framework de inbound chega a este módulo.
    """

    def __init__(
        self,
        auth_adapter: OrchestratorAuthPort,
        session_store: SessionStorePort,
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
        self._log_active_sources()
        credential = resolve_credential(self.settings)
        logger.info("auth.credentials.source resolved_from=SEN_CREDENTIALS")
        return credential

    @staticmethod
    def _log_active_sources() -> None:
        """Reports availability of configuration sources (booleans only, never values)."""
        process_available = any(
            bool(os.getenv(key))
            for key in ("SEN_CREDENTIALS", "AUTH_HOST", "AUTH_LOGIN_PATH")
        )
        logger.info(
            "config.sources.active sen_file=%s env_file=%s process=%s",
            settings_module.sen_path.is_file(),
            settings_module.dotenv_path.is_file(),
            process_available,
        )

    def _perform_login(self, credential: str) -> dict:
        """Chama o port e traduz os sinais de contrato em erros categorizados.

        O guard de endpoint é antecipado aqui (fail-fast observável como
        categoria antes da rede, pois o adapter valida URL pré-request).
        Exceções fora do contrato do port são rede de segurança → unavailable.
        """
        try:
            with log_duration("auth.login.request"):
                return self.auth_adapter.login(credential)
        except AuthEndpointNotConfiguredError as exc:
            raise LoginError(str(exc)) from exc
        except AuthTransportRejectedError:
            raise AuthenticationRejectedError(
                "Credencial recusada."
            )
        except AuthTransportUnavailableError:
            logger.exception("auth.login.network_failure")
            raise AuthenticationUnavailableError(
                "API de autenticação indisponível ou falha de conexão após tentativas."
            )
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
            if profile not in LOGIN_PROTOCOL_PROFILE_REQUIRED_KEYS:
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
                for field in LOGIN_PROTOCOL_PROFILE_REQUIRED_KEYS[profile]
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
        except SessionStoreError as exc:
            raise SessionPersistenceError(str(exc)) from exc
