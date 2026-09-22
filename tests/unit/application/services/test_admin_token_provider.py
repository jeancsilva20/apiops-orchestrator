from unittest.mock import MagicMock

import pytest

from apiops_orchestrator.adapters.outbound.http.orchestrator_auth_api.orchestrator_auth_adapter import (
    OrchestratorAuthPort,
)
from apiops_orchestrator.application.exceptions.login_exceptions import (
    AuthenticationRejectedError,
    AuthenticationUnavailableError,
)
from apiops_orchestrator.application.services.admin_token_provider import (
    AdminTokenProvider,
)
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort
from apiops_orchestrator.infrastructure.secure_storage.session_store import (
    SessionStore,
)

SESSION_ADMIN_TOKEN = "sessionadmintoken"
DEV_ACCESS_TOKEN = "devtoken"
VALIDATE_ADMIN_TOKEN = "validateadmintoken"


def _session(profile: str = "developer", with_admin: bool = False, expires_in: int = 3600, with_token: bool = True):
    payload = {
        "accessToken": DEV_ACCESS_TOKEN if with_token else "",
        "tokenType": "Bearer",
        "expiresIn": expires_in,
        "scope": "admin" if profile == "super-admin" else "apis/read",
        "profile": profile,
    }
    if profile == "developer":
        payload.update(
            {
                "userName": "dev.user",
                "userEmail": "dev@company.test",
                "userGroups": ["APIOps"],
            }
        )
    if with_admin:
        payload["adminAccessToken"] = SESSION_ADMIN_TOKEN
    return LoginSession(**payload)


class TestSessionAdminFastLane:
    def test_super_admin_session_token_used_without_validate(self):
        store = MagicMock(spec=SessionStore)
        store.load.return_value = _session(profile="super-admin", with_admin=True)
        adapter = MagicMock(spec=OrchestratorAuthPort)
        provider = AdminTokenProvider(adapter, MagicMock(), store)

        assert provider.obtain() == SESSION_ADMIN_TOKEN
        adapter.validate_access_token.assert_not_called()

    def test_developer_session_goes_through_validate(self):
        store = MagicMock(spec=SessionStore)
        store.load.return_value = _session(profile="developer", with_admin=True)
        adapter = MagicMock(spec=OrchestratorAuthPort)
        adapter.validate_access_token.return_value = {
            "autorizado": True,
            "extra_info": {"admin_access_token": VALIDATE_ADMIN_TOKEN},
        }
        provider = AdminTokenProvider(adapter, MagicMock(), store)

        # contexto GROUP desenvolvedor: fast-lane é ignorada, validate é a via
        assert provider.obtain() == VALIDATE_ADMIN_TOKEN
        adapter.validate_access_token.assert_called_once()


class TestValidateFlow:
    """Fluxo dev: accessToken do `.sen_session` → rota validate → admin token."""

    @pytest.fixture
    def dev_deps(self):
        store = MagicMock(spec=SessionStore)
        store.load.return_value = _session(profile="developer")
        adapter = MagicMock(spec=OrchestratorAuthPort)
        provider = AdminTokenProvider(adapter, MagicMock(), store)
        return provider, adapter

    def test_validate_authorized_returns_inline_admin_token(self, dev_deps):
        provider, adapter = dev_deps
        adapter.validate_access_token.return_value = {
            "autorizado": True,
            "extra_info": {"admin_access_token": VALIDATE_ADMIN_TOKEN},
        }

        assert provider.obtain() == VALIDATE_ADMIN_TOKEN
        adapter.validate_access_token.assert_called_once_with(DEV_ACCESS_TOKEN)

    def test_autorizado_false_is_rejected(self, dev_deps):
        provider, adapter = dev_deps
        adapter.validate_access_token.return_value = {
            "autorizado": False,
            "extra_info": {"admin_access_token": VALIDATE_ADMIN_TOKEN},
        }

        with pytest.raises(AuthenticationRejectedError):
            provider.obtain()

    def test_missing_admin_access_token_is_rejected(self, dev_deps):
        provider, adapter = dev_deps
        adapter.validate_access_token.return_value = {"autorizado": True, "extra_info": {}}

        with pytest.raises(AuthenticationRejectedError):
            provider.obtain()

    def test_validate_refusal_rewrites_message_educationally(self, dev_deps):
        """Recusas de qualquer tipo chegam ao usuário com a mesma orientação."""
        provider, adapter = dev_deps
        adapter.validate_access_token.side_effect = AuthenticationRejectedError("HTTP 401")

        with pytest.raises(AuthenticationRejectedError, match="sen login"):
            provider.obtain()

    def test_network_failure_also_surfaced_as_rejection(self, dev_deps):
        provider, adapter = dev_deps
        adapter.validate_access_token.side_effect = RuntimeError("connection refused")

        with pytest.raises(AuthenticationRejectedError, match="sen login"):
            provider.obtain()

    def test_missing_or_expired_session_is_rejected_before_validate(self, dev_deps):
        provider, adapter = dev_deps
        store = MagicMock(spec=SessionStore)
        store.load.return_value = None
        provider = AdminTokenProvider(adapter, MagicMock(), store)

        with pytest.raises(AuthenticationRejectedError, match="sen login"):
            provider.obtain()

        adapter.validate_access_token.assert_not_called()

    def test_expired_session_is_rejected_before_validate(self, dev_deps):
        provider, adapter = dev_deps
        store = MagicMock(spec=SessionStore)
        store.load.return_value = _session(expires_in=-1)
        provider = AdminTokenProvider(adapter, MagicMock(), store)

        with pytest.raises(AuthenticationRejectedError, match="sen login"):

            provider.obtain()

        adapter.validate_access_token.assert_not_called()


class TestCentralization:
    def test_every_manager_command_goes_through_resolver(self):
        # Ponto único: o builder deve compor exatamente esta função
        import inspect

        from apiops_orchestrator.main import build_listing_service_factory

        source = inspect.getsource(build_listing_service_factory)
        assert "resolve_admin_token" in source