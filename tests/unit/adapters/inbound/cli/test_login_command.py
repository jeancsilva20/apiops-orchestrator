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
TOKEN = "U1VDQ0VTU09fVE9LRU4="


def _session():
    return LoginSession(
        access_token=TOKEN,
        token_type="Bearer",
        expires_in=43200,
        user_groups=["APIOps", "Lab-tech"],
        user_email="isaac.machado@sensedia.com",
        username="isaac.machado",
    )


def _obj_with(failing_exc=None, session=None):
    class FakeService:
        def login(self):
            if failing_exc is not None:
                raise failing_exc
            return session or _session()

    return {"login_service_factory": lambda: FakeService()}


def test_login_success_prints_summary_without_secrets():
    result = runner.invoke(app, ["sen", "login"], obj=_obj_with())
    assert result.exit_code == 0
    assert "Login realizado com sucesso." in result.output
    assert "isaac.machado" in result.output
    assert "isaac.machado@sensedia.com" in result.output
    assert "APIOps, Lab-tech" in result.output
    assert "Sessão expira em" in result.output
    assert TOKEN not in result.output
    assert CREDENTIAL not in result.output


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
        (LoginProtocolError("Resposta incompleta"), 4, "Resposta incompleta"),
        (SessionPersistenceError("Falha de persistência"), 5, "Falha de persistência"),
    ],
)
def test_login_categories_map_to_exit_codes(exc, expected_code, expected_fragment):
    result = runner.invoke(app, ["sen", "login"], obj=_obj_with(failing_exc=exc))
    assert result.exit_code == expected_code
    assert expected_fragment in result.output
