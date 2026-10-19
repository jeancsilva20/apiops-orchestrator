import json
import re

import pytest
import yaml
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
    assert "Serviço de login indisponível no contexto." in result.output


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


# --- saída estruturada (-o json | yaml) --------------------------------------



ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_flag_output_aparece_no_help():
    resultado = runner.invoke(app, ["sen", "login", "--help"])
    assert resultado.exit_code == 0
    assert "--output" in resultado.output


def test_json_developer_traz_so_o_documento_do_contrato():
    resultado = runner.invoke(app, ["sen", "login", "-o", "json"], obj=_obj_with())

    assert resultado.exit_code == 0
    doc = json.loads(resultado.output)  # stdout é só o documento
    assert list(doc) == ["schema", "authenticated", "user", "expiresAt"]
    assert doc["schema"] == "apiops.sen-login/v1"
    assert doc["authenticated"] is True
    assert doc["user"] == {"name": "ci.runner", "email": "runner@company.test"}
    assert ISO_UTC.match(doc["expiresAt"])


def test_yaml_super_admin_sem_identidade_pessoal():
    resultado = runner.invoke(
        app, ["sen", "login", "-o", "yaml"], obj=_obj_with(session=_super_admin_session())
    )

    assert resultado.exit_code == 0
    doc = yaml.safe_load(resultado.output)
    assert list(doc) == ["schema", "authenticated", "profile", "scope", "expiresAt"]
    assert doc["profile"] == "super-admin" and doc["scope"] == "admin"
    assert "user" not in doc


@pytest.mark.parametrize("formato", ["json", "yaml"])
@pytest.mark.parametrize("sessao", [_developer_session, _super_admin_session])
def test_modo_estruturado_sem_token_e_sem_elementos_visuais(formato, sessao):
    resultado = runner.invoke(
        app, ["sen", "login", "-o", formato], obj=_obj_with(session=sessao())
    )

    assert resultado.exit_code == 0
    for proibido in (TOKEN_DEV, TOKEN_ADMIN, "Bearer", "Autenticando", "Login realizado"):
        assert proibido not in resultado.output
    assert "groups" not in resultado.output.lower()


def test_erro_de_login_em_json_mantem_mensagem_e_exit_code():
    resultado = runner.invoke(
        app, ["sen", "login", "-o", "json"],
        obj=_obj_with(failing_exc=AuthenticationRejectedError("Credencial recusada")),
    )
    assert resultado.exit_code == 3
    assert "Credencial recusada" in resultado.output
