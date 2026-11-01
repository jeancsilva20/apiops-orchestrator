"""`sen get ...` e `sen export api`: validação de opções, render e saída máquina."""

import json
from unittest.mock import MagicMock

import yaml
from typer.testing import CliRunner

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from apiops_orchestrator.application.exceptions.navigation_exceptions import (
    NavigationRevisionNotFound,
)
from apiops_orchestrator.domain.services.repo_materializer import (
    MaterializationResult,
    MaterializedFile,
)

runner = CliRunner()

API = {"id": 400, "name": "Orchestrator Auth API", "version": "1.0.1", "basePath": "/orq-auth/v1"}
REVISION = {
    "id": 8948,
    "number": 4,
    "lifeCycle": "DRAFT",
    "workflowId": 139,
    "workflowStageId": 420,
    "deployedIn": ["Default"],
}
COUNTS = {"own": 1, "removes": 0, "inherited": 0, "effective": 1, "preserved": 0}


def _invoke(args, service):
    return runner.invoke(
        app, ["sen", *args], obj={"api_navigation_service_factory": lambda: service}
    )


def _item(id_=19195, kind="Log", content=None):
    return {
        "id": id_,
        "position": 0,
        "executionPoint": "FIRST",
        "type": kind,
        "status": "REFERENCE",
        "customInterceptorId": None,
        "customName": None,
        "summary": "acceptedTerms=True",
        **({"content": content} if content is not None else {}),
    }


# --------------------------------------------------------------------------- get api


def test_get_api_text_and_json():
    service = MagicMock()
    service.api_detail.return_value = {
        **API,
        "description": "Auth API.",
        "apiType": "REST",
        "visibility": {"type": "GROUP", "owner": "paulo", "groupName": "APIOps", "users": ["isaac"]},
        "responsible": {"username": "paulo", "groupName": ""},
        "apiTags": [{"attributeName": "team", "tags": ["apiops"]}],
        "plans": [],
        "lastRevisionNumber": 4,
        "environments": [
            {"id": 1, "name": "Default", "inboundUrl": "https://gw/", "deployedRevision": {"number": 4, "id": 8948}},
            {"id": 7, "name": "DEV", "inboundUrl": "https://gw/dev/", "deployedRevision": None},
        ],
        "revisions": [
            {"number": 4, "id": 8948, "lifeCycle": "DRAFT", "resources": 2, "operations": 4, "rootInterceptors": 4, "deployedIn": ["Default"], "current": True},
        ],
    }

    result = _invoke(["get", "api", "--id", "400"], service)

    assert result.exit_code == 0, result.output
    out = result.output.replace("\n", " ")
    assert "Orchestrator Auth API" in out and "AMBIENTES" in out and "REVISÕES" in out
    assert "grupo APIOps" in out and "team=apiops" in out
    assert "4 *" in out and "revisão corrente" in out
    assert "sen get resources --id 400 --revision 4" in out
    service.api_detail.assert_called_once_with(400)

    result = _invoke(["get", "api", "--id", "400", "-o", "json"], service)
    assert result.exit_code == 0
    assert json.loads(result.output)["lastRevisionNumber"] == 4


def test_get_api_requires_id():
    result = _invoke(["get", "api"], MagicMock())
    assert result.exit_code != 0
    assert "--id" in result.output


def test_navigation_error_is_printed_with_its_exit_code():
    service = MagicMock()
    service.api_detail.side_effect = NavigationRevisionNotFound(400, "de número 9", [1, 4])

    result = _invoke(["get", "api", "--id", "400"], service)

    assert result.exit_code == 1
    assert "não tem a revisão de número 9" in result.output.replace("\n", " ")


def test_unexpected_error_never_leaks_exception_text():
    service = MagicMock()
    service.api_detail.side_effect = RuntimeError("segredo interno")

    result = _invoke(["get", "api", "--id", "400"], service)

    assert result.exit_code == 1
    assert "segredo interno" not in result.output
    assert "erro interno" in result.output.lower()


def test_missing_factory_in_context():
    result = runner.invoke(app, ["sen", "get", "api", "--id", "400"], obj={})
    assert result.exit_code == 1
    assert "indisponível" in result.output


# --------------------------------------------------------------------------- get resources


def test_get_resources_renders_tree_and_passes_revision():
    service = MagicMock()
    service.structure.return_value = {
        "api": API,
        "revision": REVISION,
        "root": {"scope": "all", "destination": {"url": None, "timeout": None}, "interceptors": COUNTS},
        "resources": [
            {
                "id": 10,
                "name": "Token",
                "slug": "token",
                "description": None,
                "destination": {"url": None, "timeout": None},
                "inherits": False,
                "interceptors": {**COUNTS, "removes": 1},
                "operations": [
                    {
                        "id": 11,
                        "method": "POST",
                        "path": "/oauth2/token",
                        "description": None,
                        "destination": {"url": "https://backend/token", "timeout": "30000"},
                        "inherits": True,
                        "interceptors": COUNTS,
                    }
                ],
            }
        ],
        "totals": {"resources": 1, "operations": 1},
    }

    result = _invoke(["get", "resources", "--id", "400", "--revision", "4"], service)

    assert result.exit_code == 0, result.output
    out = result.output.replace("\n", " ")
    assert "revisão #4 (id 8948, DRAFT)" in out and "no ar em Default" in out
    assert "quebra herança (remove 1)" in out
    assert "POST" in out and "/oauth2/token" in out
    assert "destino: https://backend/token" in out and "timeout 30000" in out
    service.structure.assert_called_once_with(400, 4, None)


def test_revision_and_revision_id_are_exclusive():
    result = _invoke(
        ["get", "resources", "--id", "400", "--revision", "4", "--revision-id", "8948"],
        MagicMock(),
    )
    assert result.exit_code == 1
    assert "--revision" in result.output and "--revision-id" in result.output


# --------------------------------------------------------------------------- get interceptors


def _scope(kind="root", key="all", label="all", own=None, effective=None, removes=None):
    scope = {
        "scope": key,
        "kind": kind,
        "label": label,
        "id": 8948,
        "destination": {"url": None, "timeout": None},
        "inherits": None if kind == "root" else not removes,
        "counts": COUNTS,
        "removes": removes or [],
        "own": own or {"request": [_item()], "response": []},
    }
    if effective is not None:
        scope["effective"] = effective
    return scope


def test_get_interceptors_own_mode_and_selectors():
    service = MagicMock()
    service.interceptors.return_value = {
        "api": API,
        "revision": REVISION,
        "mode": "own",
        "scopes": [
            _scope(),
            _scope(
                "resource",
                "token",
                "Token",
                own={"request": [], "response": []},
                removes=[{"targetId": 19191, "type": "OAuth", "executionPoint": "FIRST", "resolved": True}],
            ),
        ],
    }

    result = _invoke(
        ["get", "interceptors", "--id", "400", "--resource", "Token", "--operation", "POST /x"],
        service,
    )

    assert result.exit_code == 0, result.output
    out = result.output.replace("\n", " ")
    assert "PRÓPRIOS" in out and "[19195]" in out and "Log" in out
    assert "remove" in out and "[19191]" in out and "OAuth" in out
    assert "(nenhum interceptor próprio)" in out
    service.interceptors.assert_called_once_with(
        400, None, None, resource="Token", operation="POST /x", effective=False, include_content=False
    )


def test_get_interceptors_effective_marks_origin_and_prints_content():
    service = MagicMock()
    inherited = _item(1, content={"acceptedTerms": True})
    own = _item(2, kind="OAuth", content={"grantTypes": ["CLIENT_CREDENTIALS"]})
    service.interceptors.return_value = {
        "api": API,
        "revision": REVISION,
        "mode": "effective",
        "scopes": [
            _scope(
                "operation",
                "POST /x",
                "POST /x",
                own={"request": [own], "response": []},
                effective={"request": [inherited, own], "response": []},
            )
        ],
    }

    result = _invoke(
        ["get", "interceptors", "--id", "400", "--effective", "--content", "-o", "text"],
        service,
    )

    assert result.exit_code == 0, result.output
    out = result.output.replace("\n", " ")
    assert "EXECUTA" in out and "herdado" in out and "próprio" in out
    assert '"grantTypes"' in out  # --content imprime a configuração
    service.interceptors.assert_called_once_with(
        400, None, None, resource=None, operation=None, effective=True, include_content=True
    )


def test_get_interceptors_item_zoom():
    service = MagicMock()
    service.interceptor.return_value = {
        "api": API,
        "revision": REVISION,
        "scope": {"scope": "POST /x", "kind": "operation", "label": "POST /x", "id": 11, "resource": "token"},
        "interceptor": {
            "id": 19220,
            "position": 2,
            "executionPoint": "FIRST",
            "type": "Custom",
            "status": "REFERENCE",
            "customInterceptorId": 1,
            "customName": "Oauth - RFC",
            "content": {"id": 1, "name": "Oauth - RFC", "script": "var x = 1;"},
            "parentType": "REVISION",
            "parentId": None,
            "governed": True,
        },
    }

    result = _invoke(["get", "interceptors", "--id", "400", "--item", "19220"], service)

    assert result.exit_code == 0, result.output
    out = result.output.replace("\n", " ")
    assert "do recurso token" in out
    assert "sen get custom --custom-id 1" in out
    assert "var x = 1;" in out
    service.interceptor.assert_called_once_with(400, 19220, None, None)

    result = _invoke(["get", "interceptors", "--id", "400", "--item", "1", "--effective"], service)
    assert result.exit_code == 1
    assert "--item não combina" in result.output


def test_get_interceptors_yaml_output_is_the_document():
    service = MagicMock()
    service.interceptors.return_value = {"api": API, "revision": REVISION, "mode": "own", "scopes": []}

    result = _invoke(["get", "interceptors", "--id", "400", "-o", "yaml"], service)

    assert result.exit_code == 0
    assert yaml.safe_load(result.output)["revision"]["id"] == 8948


# --------------------------------------------------------------------------- get custom / swagger


def test_get_custom_text_and_script_only():
    service = MagicMock()
    service.custom_interceptor.return_value = {"id": 31, "name": "Super", "script": "line1\nline2"}

    result = _invoke(["get", "custom", "--custom-id", "31"], service)
    assert result.exit_code == 0, result.output
    assert "Super" in result.output and "line2" in result.output

    result = _invoke(["get", "custom", "--custom-id", "31", "--script-only"], service)
    assert result.exit_code == 0
    assert result.output == "line1\nline2\n"


def test_get_swagger_defaults_to_yaml_and_accepts_json():
    service = MagicMock()
    service.swagger.return_value = {"openapi": "3.0.0", "info": {"title": "X"}}

    result = _invoke(["get", "swagger", "--id", "400", "--revision-id", "8948"], service)
    assert result.exit_code == 0, result.output
    assert yaml.safe_load(result.output)["openapi"] == "3.0.0"
    service.swagger.assert_called_once_with(400, None, 8948)

    result = _invoke(["get", "swagger", "--id", "400", "-o", "json"], service)
    assert json.loads(result.output)["info"]["title"] == "X"


# --------------------------------------------------------------------------- export api


def _export_result():
    return (
        {"id": 400, "name": "Orchestrator Auth API", "version": "1.0.1", "basePath": "/orq-auth/v1",
         "revisions": [], "environments": []},
        {"id": 8948, "revisionNumber": 4, "lifeCycle": "DRAFT"},
        MaterializationResult(
            files=[
                MaterializedFile("api-basic-info.yaml", "kind: ApiBasicInfo\n"),
                MaterializedFile("resources/token/resource.yaml", "name: Token\n"),
            ],
            warnings=["um aviso"],
        ),
    )


def test_export_prints_files_to_stdout_without_dir():
    service = MagicMock()
    service.export.return_value = _export_result()

    result = _invoke(["export", "api", "--id", "400"], service)

    assert result.exit_code == 0, result.output
    out = result.output
    assert "# ==> api-basic-info.yaml" in out and "kind: ApiBasicInfo" in out
    assert "# ==> resources/token/resource.yaml" in out
    assert "AVISO" in out and "um aviso" in out

    result = _invoke(["export", "api", "--id", "400", "-o", "json"], service)
    document = json.loads(result.output)
    assert document["files"][1] == {"path": "resources/token/resource.yaml", "text": "name: Token\n"}
    assert document["revision"]["number"] == 4


def test_export_writes_tree_into_dir_and_refuses_overwrite(tmp_path):
    service = MagicMock()
    service.export.return_value = _export_result()
    target = tmp_path / "repo"

    result = _invoke(["export", "api", "--id", "400", "--dir", str(target)], service)

    assert result.exit_code == 0, result.output
    assert (target / "api-basic-info.yaml").read_text(encoding="utf-8") == "kind: ApiBasicInfo\n"
    assert (target / "resources" / "token" / "resource.yaml").exists()

    result = _invoke(["export", "api", "--id", "400", "--dir", str(target)], service)
    assert result.exit_code == 1
    assert "--force" in result.output

    result = _invoke(["export", "api", "--id", "400", "--dir", str(target), "--force", "-o", "json"], service)
    assert result.exit_code == 0
    assert [f["path"] for f in json.loads(result.output)["files"]] == [
        "api-basic-info.yaml",
        "resources/token/resource.yaml",
    ]
