from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from apiops_orchestrator.adapters.outbound.http.orchestrator_auth_api.orchestrator_auth_adapter import (
    OrchestratorAuthPort,
)
from apiops_orchestrator.application.exceptions.login_exceptions import (
    AuthenticationUnavailableError,
    CredentialNotFoundError,
    LoginProtocolError,
)
from apiops_orchestrator.application.services.admin_token_provider import (
    AdminTokenProvider,
)
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.infrastructure.secure_storage.session_store import (
    SessionStore,
)

CREDENTIAL = "QUJDREVG"
ADMIN_FROM_ROUTE = "adminfromroute"
SESSION_ADMIN_TOKEN = "sessionadmintoken"

RAW_OK_PAYLOAD = {
    "access_token": "fakesessiontoken",
    "token_type": "bearer",
    "expires_in": 3600,
    "extra_info": {
        "scope": "admin",
        "profile": "super-admin",
        "admin_access_token": ADMIN_FROM_ROUTE,
    },
}


def _super_admin_session(with_token: bool = True, expires_in: int = 3600):
    payload = {
        "accessToken": "fakesessiontoken",
        "tokenType": "Bearer",
        "expiresIn": expires_in,
        "scope": "admin",
        "profile": "super-admin",
    }
    if with_token:
        payload["adminAccessToken"] = SESSION_ADMIN_TOKEN
    return LoginSession(**payload)


def _developer_session():
    return LoginSession(
        accessToken="devtoken",
        tokenType="Bearer",
        expiresIn=3600,
        scope="apis/read",
        profile="developer",
        userName="dev.user",
        userEmail="dev@company.test",
        userGroups=["APIOps"],
    )


def _make_provider(
    admin_cred: str | None = CREDENTIAL,
    store: MagicMock | None = None,
) -> tuple[AdminTokenProvider, MagicMock]:
    auth_adapter = MagicMock(spec=OrchestratorAuthPort)
    settings = MagicMock()
    settings.ADMIN_LOGIN_CREDENTIALS = admin_cred
    settings.AUTH_HOST = "https://auth.example.com"
    settings.AUTH_LOGIN_PATH = "/orq-auth/v1/oauth2/token"
    if store is None:
        store = MagicMock(spec=SessionStore)
        store.load.return_value = None
    provider = AdminTokenProvider(
        auth_adapter=auth_adapter, settings=settings, session_store=store
    )
    return provider, auth_adapter


class TestSessionHasPrecedence:
    def test_super_admin_session_with_token_used_without_network(self):
        provider, auth_adapter = _make_provider(
            store=MagicMock(
                spec=SessionStore, load=MagicMock(return_value=_super_admin_session())
            )
        )

        token = provider.obtain()

        assert token == SESSION_ADMIN_TOKEN
        auth_adapter.login.assert_not_called()

    def test_expired_super_admin_session_falls_back_to_login_route(self):
        store = MagicMock(
            spec=SessionStore,
            load=MagicMock(
                return_value=_super_admin_session(expires_in=-1)
            ),
        )
        provider, auth_adapter = _make_provider(store=store)
        auth_adapter.login.return_value = RAW_OK_PAYLOAD

        token = provider.obtain()

        assert token == ADMIN_FROM_ROUTE
        auth_adapter.login.assert_called_once_with(CREDENTIAL)

    def test_developer_session_is_ignored_for_admin_actions(self):
        store = MagicMock(
            spec=SessionStore,
            load=MagicMock(return_value=_developer_session()),
        )
        provider, auth_adapter = _make_provider(store=store)
        auth_adapter.login.return_value = RAW_OK_PAYLOAD

        token = provider.obtain()

        assert token == ADMIN_FROM_ROUTE
        auth_adapter.login.assert_called_once_with(CREDENTIAL)

    def test_legacy_super_admin_session_without_token_falls_back(self):
        store = MagicMock(
            spec=SessionStore,
            load=MagicMock(return_value=_super_admin_session(with_token=False)),
        )
        provider, auth_adapter = _make_provider(store=store)
        auth_adapter.login.return_value = RAW_OK_PAYLOAD

        assert provider.obtain() == ADMIN_FROM_ROUTE
        auth_adapter.login.assert_called_once_with(CREDENTIAL)

    def test_session_read_failure_falls_back_silently(self):
        store = MagicMock(spec=SessionStore, load=MagicMock(side_effect=RuntimeError))
        provider, auth_adapter = _make_provider(store=store)
        auth_adapter.login.return_value = RAW_OK_PAYLOAD

        assert provider.obtain() == ADMIN_FROM_ROUTE
        auth_adapter.login.assert_called_once()


class TestObtainViaLoginRoute:
    def test_returns_admin_access_token_from_extra_info(self):
        provider, auth_adapter = _make_provider()
        auth_adapter.login.return_value = RAW_OK_PAYLOAD

        token = provider.obtain()

        assert token == ADMIN_FROM_ROUTE
        auth_adapter.login.assert_called_once_with(CREDENTIAL)

    def test_missing_admin_credential_fails_before_network(self):
        provider, auth_adapter = _make_provider(admin_cred=None)

        with pytest.raises(CredentialNotFoundError):
            provider.obtain()

        auth_adapter.login.assert_not_called()

    def test_blank_admin_credential_fails_before_network(self):
        provider, auth_adapter = _make_provider(admin_cred="   ")

        with pytest.raises(CredentialNotFoundError):
            provider.obtain()

        auth_adapter.login.assert_not_called()

    def test_missing_admin_access_token_raises_protocol_error(self):
        provider, auth_adapter = _make_provider()
        auth_adapter.login.return_value = {
            "access_token": "x",
            "token_type": "bearer",
            "expires_in": 1,
            "extra_info": {"scope": "admin", "profile": "super-admin"},
        }

        with pytest.raises(LoginProtocolError):
            provider.obtain()

    def test_no_extra_info_raises_protocol_error(self):
        provider, auth_adapter = _make_provider()
        auth_adapter.login.return_value = {"access_token": "x"}

        with pytest.raises(LoginProtocolError):
            provider.obtain()

    def test_generic_exception_maps_to_unavailable(self):
        provider, auth_adapter = _make_provider()
        auth_adapter.login.side_effect = ConnectionError("boom")

        with pytest.raises(AuthenticationUnavailableError):
            provider.obtain()


class TestTokenHygiene:
    def test_session_token_and_route_token_are_plain_strings(self):
        from_session_store = MagicMock(
            spec=SessionStore,
            load=MagicMock(return_value=_super_admin_session()),
        )
        provider_session, _ = _make_provider(store=from_session_store)
        assert isinstance(provider_session.obtain(), str)

        provider_route, adapter_route = _make_provider()
        adapter_route.login.return_value = RAW_OK_PAYLOAD
        assert isinstance(provider_route.obtain(), str) and not isinstance(
            provider_route.obtain(), LoginSession
        )

    def test_expiry_reference_is_a_real_datetime(self):
        session = _super_admin_session()

        assert isinstance(session.expiresAt, datetime)
        assert session.expiresAt.tzinfo is not None
        assert session.expiresAt > datetime.now(timezone.utc)
