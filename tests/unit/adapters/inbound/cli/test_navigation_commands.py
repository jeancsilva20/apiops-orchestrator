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


# --------------------------------------------------------------------------- catálogos (sen list ...)


def test_list_without_subcommand_names_the_catalogs():
    result = runner.invoke(app, ["sen", "list"])
    assert result.exit_code == 2
    out = result.output.replace("\n", " ")
    assert "sen list api" in out and "environments" in out and "workflows" in out


def test_list_environments_table_and_json():
    service = MagicMock()
    service.environments.return_value = [
        {"id": 1, "name": "Default", "description": None, "inboundUrl": "https://gw/", "isDeployable": True, "tlsType": "TLS"},
        {"id": 9, "name": "HMG", "description": "Homolog", "inboundUrl": "https://gw/cli-2/", "isDeployable": False, "tlsType": None},
    ]
    result = _invoke(["list", "environments"], service)
    assert result.exit_code == 0, result.output
    out = result.output.replace("\n", " ")
    assert "ENV ID" in out and "Default" in out and "HMG" in out and "Homolog" in out

    result = _invoke(["list", "environments", "-o", "json"], service)
    assert json.loads(result.output)[1]["id"] == 9


def test_list_workflows_text():
    service = MagicMock()
    service.workflows.return_value = [
        {
            "id": 327, "name": "Sura", "description": None, "category": "TEAM", "group": "Lab-tech",
            "stages": [
                {"id": 783, "name": "Sandbox", "position": 1, "maturityRequired": 60.0, "interceptors": 4, "attributes": 0, "deployableEnvironments": [1]},
                {"id": 784, "name": "Prod", "position": 2, "maturityRequired": 0.0, "interceptors": 0, "attributes": 0, "deployableEnvironments": []},
            ],
        }
    ]
    result = _invoke(["list", "workflows"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "Sura" in out and "grupo Lab-tech" in out
    assert "maturidade ≥ 60%" in out and "4 interceptor(es)" in out and "deploy em 1" in out
    assert "sem requisitos" in out and "sen get workflow --id" in out


def test_list_attributes_and_interceptors_pass_filters():
    service = MagicMock()
    service.attributes.return_value = [{"id": 149, "name": "My new", "tags": ["Tag1", "Tag2"], "inUse": True}]
    service.interceptor_catalog.return_value = [
        {"name": "Oauth - RFC", "kind": "custom", "category": "JAVASCRIPT", "id": 1, "executionPoints": ["request", "response"], "flowType": "ANY", "tags": ["Oauth"]}
    ]

    result = _invoke(["list", "attributes"], service)
    assert result.exit_code == 0, result.output
    assert "My new" in result.output and "Tag1, Tag2" in result.output

    result = _invoke(["list", "interceptors", "--custom", "--tag", "Oauth"], service)
    assert result.exit_code == 0, result.output
    out = result.output.replace("\n", " ")
    assert "Oauth - RFC" in out and "request+response" in out and "sen get custom --custom-id" in out
    service.interceptor_catalog.assert_called_once_with(custom_only=True, tag="Oauth")

    service.interceptor_catalog.return_value = []
    result = _invoke(["list", "interceptors", "--tag", "nada"], service)
    assert result.exit_code == 0 and "Nenhum interceptor" in result.output


# --------------------------------------------------------------------------- governança (sen get workflow|governance|impact)


def _stage_doc(**overrides):
    stage = {
        "id": 783, "name": "Sandbox", "position": 1, "maturityRequired": 60.0,
        "interceptors": [{"type": "OAuth", "mustHave": True, "executionPoint": "FIRST", "positionType": "ANY", "flowType": "API", "resourceId": None, "operationId": None, "description": "deve ter OAuth no request na raiz da API"}],
        "attributes": [{"attributeId": 149, "name": "My new", "tagId": None, "mustHave": True}],
        "deployableEnvironments": [{"id": 1, "name": "Default"}],
        "environments": [{"id": 1, "name": "Default", "mandatoryDeployment": "MUST_HAVE", "deployableApiManager": True}],
    }
    stage.update(overrides)
    return stage


def test_get_workflow_prints_requirements():
    service = MagicMock()
    service.workflow.return_value = {
        "id": 327, "name": "Sura", "description": "Demo", "category": "TEAM", "group": "Lab-tech",
        "stages": [_stage_doc(), _stage_doc(id=784, name="Prod", position=2, maturityRequired=0.0, interceptors=[], attributes=[], deployableEnvironments=[], environments=[])],
    }
    result = _invoke(["get", "workflow", "--id", "327"], service)
    assert result.exit_code == 0, result.output
    out = result.output.replace("\n", " ")
    assert "maturidade ≥ 60%" in out
    assert "deve ter OAuth no request na raiz da API" in out
    assert "deve declarar o atributo My new" in out
    assert "deploy MUST_HAVE em Default" in out
    assert "deploy permitido em: Default (1)" in out
    assert "sem requisitos · sem ambiente de deploy" in out
    service.workflow.assert_called_once_with(327)


def test_get_governance_renders_verdicts():
    service = MagicMock()
    service.governance.return_value = {
        "api": API,
        "revision": REVISION,
        "workflow": {"id": 327, "name": "Sura", "category": "TEAM", "group": "Lab-tech", "description": None},
        "stage": {"id": 783, "name": "Sandbox", "position": 1},
        "maturity": {"score": 77.5, "suggestions": 13},
        "deployedIn": [{"id": 1, "name": "Default"}],
        "current": {
            "stage": _stage_doc(),
            "verdicts": [
                {"kind": "maturity", "status": "ok", "requirement": "maturidade (completeness) ≥ 60%", "detail": "revisão está em 77.5%", "failingScopes": []},
                {"kind": "interceptor", "status": "fail", "requirement": "deve ter OAuth no request na raiz da API", "detail": "não atendido em 1 de 1 escopo(s)", "failingScopes": ["all"]},
            ],
            "summary": {"overall": "fail", "ok": 1, "fail": 1, "unknown": 0, "total": 2},
        },
        "next": None,
        "warnings": ["um aviso"],
    }
    result = _invoke(["get", "governance", "--id", "400", "--revision", "4"], service)
    assert result.exit_code == 0, result.output
    out = result.output.replace("\n", " ")
    assert "stage atual Sandbox (783)" in out
    assert "maturidade (completeness): 77.5%" in out
    assert "não atende" in out and "FALHA" in out and "OK" in out
    assert "↳ all" in out
    assert "último stage do workflow" in out
    assert "AVISO" in out and "um aviso" in out
    service.governance.assert_called_once_with(400, 4, None)

    result = _invoke(["get", "governance", "--id", "400", "-o", "json"], service)
    assert json.loads(result.output)["current"]["summary"]["overall"] == "fail"


def test_get_impact_renders_routes_and_consumers():
    service = MagicMock()
    service.impact.return_value = {
        "api": API,
        "environment": {"id": 1, "name": "Default"},
        "revisionNumber": "4",
        "basePath": "/orq-auth/v1",
        "routes": [{"path": "/users/{username}", "methods": [{"method": "GET", "operationId": 9121, "destination": "https://backend/users"}]}],
        "plans": [{"name": "Plan A", "apps": [{"name": "App 1", "status": "APPROVED", "appId": "42"}]}, {"name": "Plan B", "apps": []}],
        "totals": {"routes": 1, "operations": 1, "plans": 2, "apps": 1},
    }
    result = _invoke(["get", "impact", "--id", "400", "--env", "1"], service)
    assert result.exit_code == 0, result.output
    out = result.output.replace("\n", " ")
    assert "ambiente Default (1)" in out and "/users/{username}" in out and "https://backend/users" in out
    assert "plano Plan A" in out and "app App 1" in out and "appId 42" in out and "sem apps" in out
    service.impact.assert_called_once_with(400, 1)

    result = _invoke(["get", "impact", "--id", "400"], service)
    assert service.impact.call_args.args == (400, None)


# --------------------------------------------------------------------------- consumo e infra (sen list apps|plans|tokens|variables|…)


def test_list_apps_filters_and_renders_subscriptions():
    service = MagicMock()
    service.apps.return_value = [
        {"id": 42, "name": "Super Admin", "status": "APPROVED", "developer": "a@x", "description": None, "creationDate": "d",
         "apis": [{"id": 400, "name": "Orchestrator Auth API", "version": "1.0.1", "plans": [{"id": 66, "name": "P", "defaultPlan": True}]}], "accessTokens": 2}
    ]
    result = _invoke(["list", "apps", "--api", "400", "--query", "super"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "Super Admin" in out and "Orchestrator Auth API [P]" in out and "sen get app --id" in out
    service.apps.assert_called_once_with(api_id=400, query="super")

    service.apps.return_value = []
    assert "Nenhum app" in _invoke(["list", "apps"], service).output


def test_get_app_and_get_plan_render():
    service = MagicMock()
    service.app.return_value = {
        "id": 42, "name": "Super Admin", "status": "APPROVED", "developer": "a@x", "description": "desc", "creationDate": "d",
        "apis": [{"id": 400, "name": "Orchestrator Auth API", "version": "1.0.1", "plans": [{"id": 66, "name": "P", "defaultPlan": True}]}],
        "accessTokens": 1, "extraInfo": {}, "inboundAddresses": [],
    }
    result = _invoke(["get", "app", "--id", "42"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "app 42" in out and "ASSINATURAS" in out and "P (default)" in out and "sen list tokens --app 42" in out

    service.plan.return_value = {
        "id": 66, "name": "P", "description": None, "defaultPlan": True, "api": {"id": 400, "name": "Orchestrator Auth API", "version": "1.0.1"}, "interceptors": 1,
        "flow": {"request": [_item(9, kind="Rate limit", content={"quota": "100"})], "response": []},
    }
    result = _invoke(["get", "plan", "--id", "66"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "plano 66 · default" in out and "Rate limit" in out and '"quota": "100"' in out
    service.plan.assert_called_once_with(66)

    service.plan.return_value["flow"] = {"request": [], "response": []}
    assert "não acrescenta interceptors" in _invoke(["get", "plan", "--id", "66"], service).output


def test_list_plans_and_tokens_tables():
    service = MagicMock()
    service.plans.return_value = [{"id": 66, "name": "P", "description": None, "defaultPlan": True, "api": {"id": 400, "name": "Orchestrator Auth API", "version": "1.0.1"}, "interceptors": 0}]
    result = _invoke(["list", "plans", "--api", "400"], service)
    assert result.exit_code == 0, result.output
    assert "PLAN ID" in result.output and "sim" in result.output
    service.plans.assert_called_once_with(api_id=400, query=None)

    service.tokens.return_value = [{"id": "t1", "owner": "o@x", "app": {"id": 45, "name": "CI"}, "status": "ACTIVE", "refreshStatus": "ACTIVE", "expiresIn": 1, "creationDate": "c", "expiredDate": "2026-11-02", "apis": [{"id": 400, "name": "Orchestrator Auth API", "version": "1"}], "planIds": [], "generatedBy": None}]
    result = _invoke(["list", "tokens", "--app", "45", "--api", "400"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "TOKEN ID" in out and "CI (45)" in out and "2026-11-02" in out
    service.tokens.assert_called_once_with(app_id=45, api_id=400)


def test_list_variables_and_get_environment_show_masking():
    service = MagicMock()
    service.variables.return_value = [
        {"environmentId": 1, "environmentName": "Default", "map": "M", "mapId": 1, "key": "backendUrl", "value": "http://b", "variableType": "DEFAULT", "masked": False},
        {"environmentId": 1, "environmentName": "Default", "map": "M", "mapId": 1, "key": "basicAuth", "value": "•••••", "variableType": "DEFAULT", "masked": True},
    ]
    result = _invoke(["list", "variables", "--env", "1", "--key", "a"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "backendUrl" in out and "•••••" in out and "sen reveal variable" in out
    service.variables.assert_called_once_with(1, key="a")

    result = _invoke(["list", "variables", "--show-values"], service)
    assert result.exit_code != 0  # a listagem não tem como revelar

    service.environment.return_value = {
        "id": 7, "name": "DEV", "description": None, "inboundUrl": "https://gw/cli/", "visibility": "ORGANIZATION",
        "gateway": {"pool": "default", "type": "CLOUD", "host": "gw", "protocol": "HTTPS", "tls": "TLS"},
        "variableMaps": [{"id": 1, "name": "M", "description": None, "variables": 1}],
        "variables": [{"environmentId": 7, "environmentName": "DEV", "map": "M", "mapId": 1, "key": "k", "value": "v", "variableType": "DEFAULT", "masked": False}],
        "deployed": [{"apiId": 400, "apiName": "Orchestrator Auth API", "apiVersion": "1.0.1", "revisionId": 8948, "revisionNumber": 4}],
        "totals": {"deployed": 1},
    }
    result = _invoke(["get", "environment", "--id", "7"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "ambiente 7" in out and "M / k = v" in out and "NO AR" in out and "revisão #4" in out
    service.environment.assert_called_once_with(7)


def test_list_users_teams_inbounds_pools():
    service = MagicMock()
    service.users.return_value = [{"username": "paulo.silva", "name": "Paulo", "email": "p@x", "status": "CREATED", "providerType": "LOCAL", "isFederated": False, "createdAt": None}]
    service.teams.return_value = [{"name": "APIOps", "description": "d"}]
    service.inbounds.return_value = [{"id": 1, "name": "Default", "host": "h", "protocol": "HTTPS", "tls": "TLS", "minTlsVersion": "TLS_1_2", "maxTlsVersion": "TLS_1_3", "gatewayType": "SAAS", "dataPlane": "x", "hasApps": True, "hasEnvironments": True}]
    service.gateway_pools.return_value = [{"id": 1, "name": "default", "description": None, "type": "CLOUD", "routes": 396}]

    assert "paulo.silva" in _invoke(["list", "users", "--query", "paulo"], service).output
    service.users.assert_called_once_with("paulo")
    assert "APIOps" in _invoke(["list", "teams"], service).output
    out = " ".join(_invoke(["list", "inbounds"], service).output.split())
    assert "HTTPS/TLS" in out and "TLS_1_2…TLS_1_3" in out
    out = " ".join(_invoke(["list", "gateway-pools"], service).output.split())
    assert "default" in out and "396" in out
    assert json.loads(_invoke(["list", "gateway-pools", "-o", "json"], service).output)[0]["routes"] == 396


# --------------------------------------------------------------------------- sen reveal variable


def test_reveal_variable_text_raw_and_errors():
    service = MagicMock()
    service.reveal_variable.return_value = {
        "environmentId": 7, "environmentName": "DEV", "map": "Proxy", "mapId": 1,
        "key": "basicAuthManager", "value": "Basic abc", "variableType": "DEFAULT", "sensitive": True,
    }
    result = _invoke(["reveal", "variable", "--env", "7", "--key", "basicAuthManager", "--map", "Proxy"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "basicAuthManager" in out and "Basic abc" in out and "sensível" in out
    service.reveal_variable.assert_called_once_with(7, "basicAuthManager", "Proxy")

    result = _invoke(["reveal", "variable", "--env", "7", "--key", "basicAuthManager", "--raw"], service)
    assert result.exit_code == 0 and result.output == "Basic abc\n"

    result = _invoke(["reveal", "variable", "--env", "7", "--key", "basicAuthManager", "-o", "json"], service)
    assert json.loads(result.output)["value"] == "Basic abc"

    service.reveal_variable.side_effect = NavigationRevisionNotFound(1, "x", [])
    assert _invoke(["reveal", "variable", "--env", "7", "--key", "k"], service).exit_code == 1

    assert _invoke(["reveal", "variable", "--env", "7"], service).exit_code != 0  # --key obrigatório
    assert _invoke(["reveal"], service).exit_code != 0
