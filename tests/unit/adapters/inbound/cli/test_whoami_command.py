import json
import re
from datetime import datetime, timezone

import pytest
import yaml
from typer.testing import CliRunner

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.infrastructure.secure_storage.session_store import SessionStore

runner = CliRunner()

TOKEN_DEV = "QUJDREVG"
TOKEN_ADMIN = "REVGQUNC"
TOKEN_PRIVILEGED = "WFlaV1ZV"
EXPIRES_AT = datetime(2026, 11, 9, 21, 30, tzinfo=timezone.utc)
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _developer_session() -> LoginSession:
    return LoginSession(
        accessToken=TOKEN_DEV,
        tokenType="Bearer",
        expiresIn=43200,
        scope="read",
        profile="developer",
        expiresAt=EXPIRES_AT,
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
        expiresAt=EXPIRES_AT,
        adminAccessToken=TOKEN_PRIVILEGED,
    )


class _FakeStore:
    def __init__(self, session=None, error=None):
        self.session = session
        self.error = error

    def load(self):
        if self.error is not None:
            raise self.error
        return self.session


def _obj_with(session=None, error=None):
    return {"session_store_factory": lambda: _FakeStore(session, error)}


def test_developer_panel_shows_identity_groups_scope_and_expiry():
    result = runner.invoke(app, ["sen", "whoami"], obj=_obj_with(_developer_session()))

    assert result.exit_code == 0
    for expected in (
        "usuário:",
        "ci.runner (runner@company.test)",
        "perfil:",
        "developer",
        "grupos:",
        "APIOps, Lab-tech",
        "escopo:",
        "read",
        "válida até 09/11/2026 21:30 UTC",
    ):
        assert expected in result.output
    assert "Login realizado" not in result.output
    assert "sen --help" not in result.output


def test_super_admin_panel_shows_only_profile_scope_and_expiry():
    result = runner.invoke(app, ["sen", "whoami"], obj=_obj_with(_super_admin_session()))

    assert result.exit_code == 0
    assert "super-admin" in result.output
    assert "escopo:" in result.output and "admin" in result.output
    assert "válida até 09/11/2026 21:30 UTC" in result.output
    assert "usuário:" not in result.output
    assert "grupos:" not in result.output


def test_without_session_guides_login_and_exits_one():
    result = runner.invoke(app, ["sen", "whoami"], obj=_obj_with(None))

    assert result.exit_code == 1
    assert "Nenhuma sessão válida: faça `sen login`." in result.output


def test_developer_json_document():
    result = runner.invoke(
        app, ["sen", "whoami", "-o", "json"], obj=_obj_with(_developer_session())
    )

    assert result.exit_code == 0
    doc = json.loads(result.output)
    assert list(doc) == [
        "schema",
        "authenticated",
        "profile",
        "user",
        "groups",
        "scope",
        "expiresAt",
    ]
    assert doc["schema"] == "apiops.sen-whoami/v1"
    assert doc["authenticated"] is True
    assert doc["profile"] == "developer"
    assert doc["user"] == {"name": "ci.runner", "email": "runner@company.test"}
    assert doc["groups"] == ["APIOps", "Lab-tech"]
    assert doc["scope"] == "read"
    assert doc["expiresAt"] == "2026-11-09T21:30:00Z"


def test_super_admin_yaml_document_without_identity():
    result = runner.invoke(
        app, ["sen", "whoami", "-o", "yaml"], obj=_obj_with(_super_admin_session())
    )

    assert result.exit_code == 0
    doc = yaml.safe_load(result.output)
    assert list(doc) == ["schema", "authenticated", "profile", "scope", "expiresAt"]
    assert doc["profile"] == "super-admin" and doc["scope"] == "admin"
    assert ISO_UTC.match(doc["expiresAt"])


@pytest.mark.parametrize("output_format", ["json", "yaml"])
def test_structured_without_session_is_unauthenticated_document(output_format):
    result = runner.invoke(
        app, ["sen", "whoami", "-o", output_format], obj=_obj_with(None)
    )

    assert result.exit_code == 1
    doc = yaml.safe_load(result.output)  # YAML also parses the JSON document
    assert doc == {"schema": "apiops.sen-whoami/v1", "authenticated": False}


@pytest.mark.parametrize("output_format", ["text", "json", "yaml"])
@pytest.mark.parametrize("session", [_developer_session, _super_admin_session])
def test_no_token_in_any_output(output_format, session):
    result = runner.invoke(
        app, ["sen", "whoami", "-o", output_format], obj=_obj_with(session())
    )

    assert result.exit_code == 0
    for forbidden in (TOKEN_DEV, TOKEN_ADMIN, TOKEN_PRIVILEGED, "Bearer", "43200", "7200"):
        assert forbidden not in result.output


def test_reads_session_persisted_by_the_real_store(tmp_path):
    SessionStore(directory=tmp_path).save(_developer_session())

    result = runner.invoke(
        app,
        ["sen", "whoami", "-o", "json"],
        obj={"session_store_factory": lambda: SessionStore(directory=tmp_path)},
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["user"]["name"] == "ci.runner"


def test_unexpected_failure_shows_generic_message_without_details():
    result = runner.invoke(
        app, ["sen", "whoami"], obj=_obj_with(error=RuntimeError("detalhe interno"))
    )

    assert result.exit_code == 1
    assert "detalhe interno" not in result.output
    assert "Erro:" in result.output


def test_store_missing_from_context_exits_one():
    result = runner.invoke(app, ["sen", "whoami"], obj={})

    assert result.exit_code == 1
    assert "Leitura da sessão indisponível no contexto." in result.output
