import pytest
from typer.testing import CliRunner

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from apiops_orchestrator.application.exceptions.login_exceptions import (
    AuthenticationRejectedError,
    CredentialNotFoundError,
    LoginError,
    LoginProtocolError,
    SessionPersistenceError,
)
from apiops_orchestrator.domain.models.login_session_model import LoginSession

runner = CliRunner()

CREDENTIAL = "dXNlcm5hbWU6cGFzc3dvcmQ="
TOKEN_DEV = "QUJDREVG"
TOKEN_ADMIN = "REVGQUNC"


def _developer_session() -> LoginSession:
    return LoginSession(
        accessToken=TOKEN_DEV,
        tokenType="Bearer",
        expiresIn=43200,
        scope="apis/read",
        profile="developer",
        userName="ci.runner",
        userEmail="runner@company.test",
        userGroups=["APIOps", "Lab-tech"],
    )


def _super_admin_session() -> LoginSession:
    return LoginSession(
        accessToken=TOKEN_ADMIN,
        tokenType="Bearer",
        expiresIn=7200,
        scope="admin",
        profile="super-admin",
        adminAccessToken=TOKEN_ADMIN,
    )


def _obj_with(failing_exc=None, session=None):
    class FakeService:
        def login(self):
            if failing_exc is not None:
                raise failing_exc
            return session or _developer_session()

    return {"login_service_factory": lambda: FakeService()}


def test_login_success_prints_developer_summary_without_secrets():
    result = runner.invoke(app, ["sen", "login"], obj=_obj_with())
    assert result.exit_code == 0
    assert "Login realizado com sucesso." in result.output
    assert "ci.runner" in result.output
    assert "runner@company.test" in result.output
    assert "Sessão Válida até" not in result.output
    assert "válida até" in result.output
    assert "usuário:" in result.output
    assert ">_  APIOps CLI" in result.output
    assert "APIOps, Lab-tech" not in result.output
    assert "Grupos" not in result.output
    assert TOKEN_DEV not in result.output
    assert CREDENTIAL not in result.output


def test_login_success_prints_super_admin_summary_only_profile_and_scope():
    result = runner.invoke(
        app, ["sen", "login"], obj=_obj_with(session=_super_admin_session())
    )
    assert result.exit_code == 0
    assert "Login realizado com sucesso." in result.output
    assert "super-admin" in result.output
    assert "admin" in result.output
    assert "perfil:" in result.output
    assert "escopo:" in result.output
    assert "ci.runner" not in result.output
    assert "Sessão expira em" not in result.output
    assert TOKEN_ADMIN not in result.output
    assert TOKEN_DEV not in result.output
    assert CREDENTIAL not in result.output


def test_login_success_session_still_carries_groups():
    captured = {}

    class RecordingService:
        def login(self):
            session = _developer_session()
            captured["session"] = session
            return session

    result = runner.invoke(
        app, ["sen", "login"], obj={"login_service_factory": lambda: RecordingService()}
    )
    assert result.exit_code == 0
    assert captured["session"].userGroups == ["APIOps", "Lab-tech"]


def test_login_service_missing_from_context_exits_one():
    result = runner.invoke(app, ["sen", "login"], obj={})
    assert result.exit_code == 1
    assert "LoginService not found in context." in result.output


@pytest.mark.parametrize(
    "exc, expected_code, expected_fragment",
    [
        (
            CredentialNotFoundError("Credencial não encontrada"),
            2,
            "Credencial não encontrada",
        ),
        (AuthenticationRejectedError("Credencial recusada"), 3, "Credencial recusada"),
        (LoginError("Falha genérica", exit_code=1), 1, "Falha genérica"),
        (LoginProtocolError("Falha na autenticação."), 4, "Falha na autenticação."),
        (SessionPersistenceError("Falha de persistência"), 5, "Falha de persistência"),
    ],
)
def test_login_categories_map_to_exit_codes(exc, expected_code, expected_fragment):
    result = runner.invoke(app, ["sen", "login"], obj=_obj_with(failing_exc=exc))
    assert result.exit_code == expected_code
    assert expected_fragment in result.output
