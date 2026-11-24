from unittest.mock import MagicMock

import pytest

from apiops_orchestrator.adapters.outbound.http.orchestrator_auth_api.orchestrator_auth_adapter import (
    OrchestratorAuthPort,
)
from apiops_orchestrator.application.exceptions.login_exceptions import (
    AuthenticationRejectedError,
)
from apiops_orchestrator.application.services.admin_token_provider import (
    AdminTokenProvider,
)
from apiops_orchestrator.domain.models.login_session_model import LoginSession
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
    """Ponto unico: ninguem monta token admin por fora de `_build_admin_token`.

    A guarda e dinamica de proposito. A versao anterior conferia um nome digitado
    a mao (`resolve_admin_token`) em UM builder; o resolver foi renomeado, o nome
    sumiu de `src/` inteiro e a guarda ficou vermelha sem que nada tivesse
    regredido. Enumerando os builders, um builder novo entra no escopo sozinho.
    """

    def test_todo_builder_que_fala_com_o_manager_passa_pelo_resolver(self):
        import inspect

        from apiops_orchestrator import main as main_mod

        builders = sorted(
            nome
            for nome in dir(main_mod)
            if nome.startswith("build_") and nome.endswith("_factory")
        )
        assert len(builders) == 9, builders

        for nome in builders:
            fonte = inspect.getsource(getattr(main_mod, nome))
            # `login` e o unico que legitimamente nao passa: e ele quem cria a sessao.
            esperado = nome != "build_login_service_factory"
            assert ("_build_admin_token(" in fonte) is esperado, nome