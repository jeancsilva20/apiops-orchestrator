"""Niveis de detalhe de uma API: `sen get api|resources|interceptors|custom|swagger`, governanca e referencia de tipo.

Recortado de `test_navigation_commands.py`, que chegou a 916 linhas cobrindo 36
comandos. Os corpos sao os mesmos; o que mudou foi a casa e a origem dos
helpers, que vieram para `tests/sen_support/`.
"""

import json
from unittest.mock import MagicMock

import yaml

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from apiops_orchestrator.application.exceptions.navigation_exceptions import (
    NavigationRevisionNotFound,
)
from sen_support.cli_payloads import API, COUNTS, REVISION, item as _item
from sen_support.cli_invoke import invocar_navegacao as _invoke, runner


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
        400, None, None, resource="Token", operation="POST /x", effective=False, include_content=False, point=None
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
        400, None, None, resource=None, operation=None, effective=True, include_content=True, point=None
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
def test_interceptor_type_reference_commands():
    service = MagicMock()
    service.interceptor_type.return_value = {"type": "Rate limit", "group": "Traffic", "executionPoints": ["request"], "fields": [{"name": "quota", "meaning": "chamadas"}], "commonFields": ["ignoreBodyValidationMultiPartFormData"], "example": {"quota": "100"}, "note": None}
    result = _invoke(["get", "interceptor-type", "--type", "Rate limit"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "Rate limit" in out and "quota" in out and '"quota": "100"' in out
    service.interceptor_type.assert_called_once_with("Rate limit")

    service.interceptor_types.return_value = [service.interceptor_type.return_value, {"type": "GZip pack", "group": "Transformation", "executionPoints": ["request"], "fields": [], "commonFields": ["x"], "example": None, "note": None}]
    result = _invoke(["get", "interceptor-type"], service)
    assert result.exit_code == 0 and "GZip pack" in result.output and "sem campos próprios" in result.output
    assert len(json.loads(_invoke(["get", "interceptor-type", "-o", "json"], service).output)) == 2


def test_get_interceptors_point_and_other_points_and_reference():
    service = MagicMock()
    service.interceptors.return_value = {
        "api": API, "revision": REVISION, "mode": "own", "point": "THIRD",
        "scopes": [{**_scope(own={"request": [], "response": []}), "other": [{**_item(99, kind="Custom"), "executionPoint": "THIRD", "summary": '#1 "x"'}]}],
    }
    result = _invoke(["get", "interceptors", "--id", "400", "--point", "THIRD"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "só THIRD" in out and "outros pontos" in out and "[99]" in out and "THIRD" in out
    assert service.interceptors.call_args.kwargs["point"] == "THIRD"

    service.interceptor.return_value = {
        "api": API, "revision": REVISION,
        "scope": {"scope": "all", "kind": "root", "label": "all", "id": 1, "resource": None},
        "interceptor": {**_item(5, kind="Mock", content={"body": "x", "weird": 1}), "parentType": "REVISION", "parentId": None, "governed": True},
        "reference": {"type": "Mock", "known": ["body"], "unknown": ["weird"], "missing": ["headers", "status"]},
    }
    result = _invoke(["get", "interceptors", "--id", "400", "--item", "5"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "fora da referência: weird" in out and "esperados ausentes: headers, status" in out and 'sen get interceptor-type --type "Mock"' in out

    assert _invoke(["get", "interceptors", "--id", "400", "--item", "5", "--point", "FIRST"], service).exit_code == 1
