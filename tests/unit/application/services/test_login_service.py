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
    PAYLOAD_INVALID_MESSAGE,
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
ADMIN_TOKEN = "REVMRUVURUhVVUxRT0UtVE9LRU4="


def developer_raw() -> dict:
    return {
        "access_token": ACCESS_TOKEN,
        "token_type": "Bearer",
        "expires_in": 43200,
        "extra_info": {
            "profile": "developer",
            "scope": "apis/read",
            "user_name": "ci.runner",
            "user_email": "runner@company.test",
            "user_groups": ["APIOps"],
        },
    }


def super_admin_raw() -> dict:
    return {
        "access_token": ADMIN_TOKEN,
        "token_type": "Bearer",
        "expires_in": 7200,
        "extra_info": {
            "profile": "super-admin",
            "scope": "admin",
            "admin_access_token": ADMIN_TOKEN,
        },
    }


def _settings(
    credential: str | None = CREDENTIAL,
    auth_host: str | None = "https://auth.example.com",
):
    settings = Settings.__new__(Settings)
    object.__setattr__(settings, "SEN_CREDENTIALS", credential)
    object.__setattr__(settings, "AUTH_HOST", auth_host)
    object.__setattr__(settings, "AUTH_LOGIN_PATH", "/cli-2/orq-auth/v1/oauth2/token")
    return settings


@pytest.fixture
def deps():
    auth_adapter = MagicMock()
    auth_adapter.login.return_value = developer_raw()
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


def test_login_success_parses_developer_envelope(deps, caplog):
    service, auth_adapter, store = deps
    caplog.set_level(logging.INFO)

    session = service.login()

    assert isinstance(session, LoginSession)
    assert session.accessToken == ACCESS_TOKEN
    assert session.tokenType == "Bearer"
    assert session.profile == "developer"
    assert session.is_super_admin is False
    assert session.scope == "apis/read"
    assert session.userName == "ci.runner"
    assert session.userGroups == ["APIOps"]
    auth_adapter.login.assert_called_once_with(CREDENTIAL)
    store.save.assert_called_once()
    assert "auth.login.started" in caplog.text
    assert "auth.login.success" in caplog.text


def test_login_success_parses_super_admin_envelope(deps):
    service, auth_adapter, _ = deps
    auth_adapter.login.return_value = super_admin_raw()

    session = service.login()

    assert session.is_super_admin is True
    assert session.scope == "admin"
    assert session.adminAccessToken == ADMIN_TOKEN
    assert session.userName is None
    assert session.userGroups is None


def test_login_success_does_not_log_secrets(deps, caplog):
    service, _, _ = deps
    caplog.set_level(logging.DEBUG)
    service.login()
    assert CREDENTIAL not in caplog.text
    assert ACCESS_TOKEN not in caplog.text
    assert ADMIN_TOKEN not in caplog.text


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


def _violate(action):
    """Apply the mutation on the payload and return the mutated payload itself."""

    def runner(payload: dict) -> dict:
        action(payload)
        return payload

    return runner


CORE_VIOLATIONS = [
    ("missing_access_token", _violate(lambda p: p.pop("access_token"))),
    ("missing_expires_in", _violate(lambda p: p.pop("expires_in"))),
    ("extra_info_absent", _violate(lambda p: p.pop("extra_info"))),
    ("extra_info_wrong_shape", _violate(lambda p: p.update(extra_info="oops"))),
    (
        "unsupported_profile",
        _violate(lambda p: p["extra_info"].update(profile="nomad")),
    ),
    ("unsupported_token_type", _violate(lambda p: p.update(token_type="MAC"))),
    ("non_integer_expires_in", _violate(lambda p: p.update(expires_in="soon"))),
]


@pytest.mark.parametrize("label,violation", CORE_VIOLATIONS)
def test_login_protocol_violations_raise_generic_error(deps, label, violation):
    service, auth_adapter, _ = deps
    auth_adapter.login.return_value = violation(developer_raw())

    with pytest.raises(LoginProtocolError) as excinfo:
        service.login()

    assert excinfo.value.exit_code == 4
    assert excinfo.value.message == PAYLOAD_INVALID_MESSAGE


PROFILE_VIOLATIONS = [
    (
        "dev_missing_user_name",
        developer_raw,
        _violate(lambda p: p["extra_info"].pop("user_name")),
    ),
    (
        "dev_empty_user_groups",
        developer_raw,
        _violate(lambda p: p["extra_info"].update(user_groups=[])),
    ),
    (
        "dev_missing_scope",
        developer_raw,
        _violate(lambda p: p["extra_info"].pop("scope")),
    ),
    (
        "super_missing_admin_access_token",
        super_admin_raw,
        _violate(lambda p: p["extra_info"].pop("admin_access_token")),
    ),
]


@pytest.mark.parametrize("label,builder,violation", PROFILE_VIOLATIONS)
def test_login_matrix_violations_raise_generic_error(deps, label, builder, violation):
    service, auth_adapter, _ = deps
    auth_adapter.login.return_value = violation(builder())

    with pytest.raises(LoginProtocolError) as excinfo:
        service.login()

    assert excinfo.value.exit_code == 4
    assert excinfo.value.message == PAYLOAD_INVALID_MESSAGE


def test_login_protocol_details_logged_but_never_returned(deps, caplog):
    service, auth_adapter, _ = deps
    raw = developer_raw()
    raw["extra_info"].pop("user_email")
    auth_adapter.login.return_value = raw
    caplog.set_level(logging.ERROR)

    with pytest.raises(LoginProtocolError) as excinfo:
        service.login()

    assert "user_email" not in excinfo.value.message
    assert "auth.login.payload_invalid" in caplog.text
    assert "user_email" in caplog.text
    assert ACCESS_TOKEN not in caplog.text


def test_login_persistence_failure_maps_to_category_5(deps):
    service, _, store = deps
    store.save.side_effect = SessionStorageError(
        "Não foi possível gravar a sessão local."
    )

    with pytest.raises(SessionPersistenceError) as excinfo:
        service.login()

    assert excinfo.value.exit_code == 5
