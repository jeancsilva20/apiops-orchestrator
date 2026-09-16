import logging
from unittest.mock import MagicMock

import pytest
import typer

from apiops_orchestrator.application.exceptions.login_exceptions import (
    AuthenticationRejectedError,
    AuthenticationUnavailableError,
    CredentialNotFoundError,
    LoginError,
    LoginProtocolError,
    SessionPersistenceError,
)
from apiops_orchestrator.application.services.login_service import (
    LoginService,
    resolve_credential,
)
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.infrastructure.secure_storage.session_store import (
    SessionStorageError,
)

CREDENTIAL = "dXNlcm5hbWU6cGFzc3dvcmQ="
ACCESS_TOKEN = "RUxNVUxTiVBVTkVMUlVUQS1UT0tFTg=="

RAW_RESPONSE = {
    "access_token": ACCESS_TOKEN,
    "token_type": "Bearer",
    "expires_in": 43200,
    "user_groups": ["APIOps", "Lab-tech"],
    "user_email": "isaac.machado@sensedia.com",
    "username": "isaac.machado",
}


def _settings(
    credential: str | None = CREDENTIAL, auth_host: str | None = "https://auth.example.com"
):
    settings = Settings.__new__(Settings)
    object.__setattr__(settings, "SEN_CREDENTIALS", credential)
    object.__setattr__(settings, "AUTH_HOST", auth_host)
    object.__setattr__(settings, "AUTH_LOGIN_PATH", "/cli-2/orq-auth/v1/oauth2/token")
    return settings


@pytest.fixture
def deps():
    auth_adapter = MagicMock()
    auth_adapter.login.return_value = dict(RAW_RESPONSE)
    store = MagicMock()
    service = LoginService(
        auth_adapter=auth_adapter, session_store=store, settings=_settings()
    )
    return service, auth_adapter, store


def test_resolve_credential_primary_source_used_intact():
    assert resolve_credential(_settings(credential=f" {CREDENTIAL} ")) == CREDENTIAL


def test_resolve_credential_missing_raises_before_network(caplog):
    with pytest.raises(CredentialNotFoundError):
        resolve_credential(_settings(credential=None))
    with pytest.raises(CredentialNotFoundError):
        resolve_credential(_settings(credential="   "))


def test_resolve_credential_ignores_legacy_oauth_pair(monkeypatch):
    settings = _settings(credential=None)
    object.__setattr__(settings, "OAUTH_CLIENT_ID", "some-client")
    object.__setattr__(settings, "OAUTH_CLIENT_SECRET", "some-secret")
    with pytest.raises(CredentialNotFoundError):
        resolve_credential(settings)


def test_login_success_returns_session_and_persists(deps, caplog):
    service, auth_adapter, store = deps
    caplog.set_level(logging.INFO)

    session = service.login()

    assert isinstance(session, LoginSession)
    assert session.access_token == ACCESS_TOKEN
    auth_adapter.login.assert_called_once_with(CREDENTIAL)
    store.save.assert_called_once()
    assert "auth.login.started" in caplog.text
    assert "auth.login.success" in caplog.text


def test_login_success_does_not_log_secrets(deps, caplog):
    service, _, _ = deps
    caplog.set_level(logging.INFO)
    service.login()
    assert CREDENTIAL not in caplog.text
    assert ACCESS_TOKEN not in caplog.text


def test_login_credential_missing_fails_before_network(deps, caplog):
    service, auth_adapter, _ = deps
    object.__setattr__(service.settings, "SEN_CREDENTIALS", None)
    caplog.set_level(logging.INFO)

    with pytest.raises(CredentialNotFoundError) as excinfo:
        service.login()

    assert excinfo.value.exit_code == 2
    auth_adapter.login.assert_not_called()
    assert "auth.login.failure" in caplog.text


def test_login_missing_auth_host_fails_before_network(deps):
    service, auth_adapter, _ = deps
    object.__setattr__(service.settings, "AUTH_HOST", None)
    object.__setattr__(service.settings, "HOST", None)

    with pytest.raises(LoginError) as excinfo:
        service.login()

    assert excinfo.value.exit_code == 1
    auth_adapter.login.assert_not_called()


def test_login_blank_auth_login_path_fails_before_network(deps):
    service, auth_adapter, _ = deps
    object.__setattr__(service.settings, "AUTH_LOGIN_PATH", "   ")

    with pytest.raises(LoginError) as excinfo:
        service.login()

    assert excinfo.value.exit_code == 1
    assert "AUTH_LOGIN_PATH" in excinfo.value.message
    auth_adapter.login.assert_not_called()


def test_login_4xx_maps_to_rejected_category(deps):
    service, auth_adapter, _ = deps
    auth_adapter.login.side_effect = typer.Exit(code=1)

    with pytest.raises(AuthenticationRejectedError) as excinfo:
        service.login()

    assert excinfo.value.exit_code == 3


def test_login_unreachable_maps_to_unavailable_category(deps):
    service, auth_adapter, _ = deps
    auth_adapter.login.side_effect = ConnectionError("boom")

    with pytest.raises(AuthenticationUnavailableError) as excinfo:
        service.login()

    assert excinfo.value.exit_code == 1


def test_login_response_missing_field_names_it(deps):
    service, auth_adapter, _ = deps
    incomplete = dict(RAW_RESPONSE)
    incomplete.pop("user_groups")
    auth_adapter.login.return_value = incomplete

    with pytest.raises(LoginProtocolError) as excinfo:
        service.login()

    assert excinfo.value.exit_code == 4
    assert "user_groups" in excinfo.value.message


def test_login_response_wrong_token_type_rejected(deps):
    service, auth_adapter, _ = deps
    raw = dict(RAW_RESPONSE)
    raw["token_type"] = "MAC"
    auth_adapter.login.return_value = raw

    with pytest.raises(LoginProtocolError):
        service.login()


def test_login_persistence_failure_maps_to_category_5(deps):
    service, _, store = deps
    store.save.side_effect = SessionStorageError(
        "Não foi possível gravar a sessão local."
    )

    with pytest.raises(SessionPersistenceError) as excinfo:
        service.login()

    assert excinfo.value.exit_code == 5
