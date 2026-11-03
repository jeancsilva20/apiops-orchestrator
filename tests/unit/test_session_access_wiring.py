"""Session access checks in the command factories and their refusal in the CLI."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import apiops_orchestrator.main as main_mod
from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from apiops_orchestrator.application.exceptions.access_exceptions import (
    AccessDeniedError,
)
from apiops_orchestrator.application.exceptions.deploy_exceptions import NO_DEPLOYMENT
from apiops_orchestrator.domain.models.login_session_model import LoginSession

runner = CliRunner()

IN_PIPELINE = SimpleNamespace(pipeline_mode=True)
LOCAL = SimpleNamespace(pipeline_mode=False)


class _Authenticating(Exception):
    """Raised by the stubbed token resolution: the access check let the command through."""


def _developer(scope="write", groups=("APIOps",)) -> LoginSession:
    return LoginSession(
        accessToken="dev",
        tokenType="Bearer",
        expiresIn=3600,
        scope=scope,
        profile="developer",
        userName="dev.user",
        userEmail="dev@company.test",
        userGroups=list(groups),
    )


def _super_admin() -> LoginSession:
    return LoginSession(
        accessToken="admin",
        tokenType="Bearer",
        expiresIn=3600,
        scope="admin",
        profile="super-admin",
        adminAccessToken="admin",
    )


def _wire(monkeypatch, settings, session) -> None:
    monkeypatch.setattr(main_mod, "_load_settings", MagicMock(return_value=settings))
    store = MagicMock()
    store.load.return_value = session
    monkeypatch.setattr(main_mod, "_build_session_store", MagicMock(return_value=store))
    monkeypatch.setattr(main_mod, "_build_admin_token", MagicMock(side_effect=_Authenticating))


# --- validate -----------------------------------------------------------------


@pytest.mark.parametrize("settings", [LOCAL, IN_PIPELINE])
def test_validate_refuses_read_scope_before_authenticating(monkeypatch, settings):
    _wire(monkeypatch, settings, _developer(scope="read"))

    with pytest.raises(AccessDeniedError) as caught:
        main_mod.build_validate_service_factory()()

    assert "`sen validate`" in caught.value.message
    assert caught.value.message.endswith("Nada foi publicado.")


def test_validate_refuses_developer_outside_the_team_before_authenticating(monkeypatch):
    _wire(monkeypatch, LOCAL, _developer(groups=("Lab-tech",)))

    with pytest.raises(AccessDeniedError, match="time APIOps"):
        main_mod.build_validate_service_factory()()


@pytest.mark.parametrize(
    "session", [_developer(scope="write"), _super_admin(), None], ids=["write", "super-admin", "sem-sessao"]
)
def test_validate_goes_on_to_authenticate(monkeypatch, session):
    _wire(monkeypatch, LOCAL, session)

    with pytest.raises(_Authenticating):
        main_mod.build_validate_service_factory()()


# --- publish e deploy -----------------------------------------------------------


@pytest.mark.parametrize(
    "builder,command,outcome",
    [
        ("build_publish_service_factory", "publish", "Nada foi publicado."),
        ("build_deploy_service_factory", "deploy", NO_DEPLOYMENT),
    ],
)
def test_developer_in_pipeline_mode_is_refused_before_authenticating(
    monkeypatch, builder, command, outcome
):
    _wire(monkeypatch, IN_PIPELINE, _developer(scope="write"))

    with pytest.raises(AccessDeniedError) as caught:
        getattr(main_mod, builder)()()

    assert f"`sen {command}`" in caught.value.message
    assert "credencial da esteira" in caught.value.message
    assert caught.value.message.endswith(outcome)


@pytest.mark.parametrize("builder", ["build_publish_service_factory", "build_deploy_service_factory"])
def test_pipeline_credential_goes_on_to_authenticate(monkeypatch, builder):
    _wire(monkeypatch, IN_PIPELINE, _super_admin())

    with pytest.raises(_Authenticating):
        getattr(main_mod, builder)()()


# --- recusa no CLI --------------------------------------------------------------


@pytest.mark.parametrize(
    "argv,factory_key",
    [
        (["sen", "list", "api"], "api_listing_service_factory"),
        (["sen", "validate"], "validate_service_factory"),
        (["sen", "publish"], "publish_service_factory"),
        (["sen", "deploy"], "deploy_service_factory"),
    ],
)
def test_cli_prints_the_refusal_and_exits_1(argv, factory_key):
    factory = MagicMock(side_effect=AccessDeniedError("Sem acesso."))

    result = runner.invoke(app, argv, obj={factory_key: factory})

    assert result.exit_code == 1
    assert "Sem acesso." in result.output
