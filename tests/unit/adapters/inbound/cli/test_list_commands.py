"""Catalogos do tenant, consumo, access control e os filtros de `sen list api`.

Recortado de `test_navigation_commands.py`, que chegou a 916 linhas cobrindo 36
comandos. Os corpos sao os mesmos; o que mudou foi a casa e a origem dos
helpers, que vieram para `tests/sen_support/`.
"""

import json
from unittest.mock import MagicMock


from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from sen_support.cli_payloads import item as _item
from sen_support.cli_invoke import invocar_navegacao as _invoke, runner


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
# --------------------------------------------------------------------------- donos, access control, tipos, --point, list api filtros


def test_list_owners_uses_the_listing_service():
    from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import _translate_row

    listing = MagicMock()
    listing.list_apis.return_value = [
        _translate_row({"apiId": 1, "apiName": "A", "owner": "paulo", "contextType": "GROUP", "contextGroupName": "APIOps"}),
        _translate_row({"apiId": 2, "apiName": "B", "owner": "ana", "contextType": "ME"}),
    ]
    result = runner.invoke(app, ["sen", "list", "owners"], obj={"api_listing_service_factory": lambda: listing, "api_navigation_service_factory": lambda: MagicMock()})
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "paulo" in out and "APIOps" in out and "1 A" in out and "sen list api --all --owner" in out
    listing.list_apis.assert_called_once_with(query=None, offset=0, limit=None)

    result = runner.invoke(app, ["sen", "list", "owners", "-o", "json"], obj={"api_listing_service_factory": lambda: listing, "api_navigation_service_factory": lambda: MagicMock()})
    assert json.loads(result.output)[0]["owner"] == "ana"  # empate: ordem alfabética


def test_access_control_commands():
    service = MagicMock()
    service.roles.return_value = [{"id": "r1", "name": "Admin", "description": "all", "managedBySensedia": True, "usersChangeable": False, "products": [{"id": "p", "name": "API Platform", "inlinePermission": None}]}]
    result = _invoke(["list", "roles", "--query", "adm"], service)
    assert result.exit_code == 0 and "Admin" in result.output and "Sensedia" in result.output
    service.roles.assert_called_once_with("adm")

    service.role.return_value = {
        "id": "r1", "name": "Admin", "description": "all", "managedBySensedia": True, "usersChangeable": False, "products": [],
        "permissions": [{"product": "API Platform", "productId": "p", "permissions": [{"code": "api-platform.apis.view", "name": "View", "description": None}]}],
        "users": [{"username": "paulo", "status": "CREATED"}], "totals": {"permissions": 1, "products": 1, "users": 1},
    }
    result = _invoke(["get", "role", "--id", "Admin"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "api-platform.apis.view" in out and "USUÁRIOS 1" in out and "paulo" in out
    service.role.assert_called_once_with("Admin")

    service.user.return_value = {"username": "paulo", "name": "P", "email": "e", "status": "CREATED", "providerType": "LOCAL", "isFederated": False, "createdAt": "d", "enabled": True, "mfaEnabled": True, "tags": [], "teams": [{"name": "APIOps", "description": None}], "roles": [{"id": "s", "name": "Super Admin", "description": None, "managedBySensedia": True}], "isSuperAdmin": True}
    result = _invoke(["get", "user", "--username", "paulo"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "Super Admin" in out and "MFA" in out and "APIOps" in out and "sen list api --all --owner paulo" in out

    service.team.return_value = {"name": "APIOps", "description": "d", "members": [{"username": "paulo", "name": "P", "status": "CREATED"}], "totals": {"members": 1}}
    result = _invoke(["get", "team", "--name", "APIOps"], service)
    assert result.exit_code == 0 and "1 membro(s)" in result.output and "paulo" in result.output

    service.permissions.return_value = {"product": "API Platform", "domains": [{"domain": "apis", "codes": ["api-platform.apis.view"]}], "totals": {"codes": 1, "domains": 1}}
    result = _invoke(["list", "permissions", "--product", "API Platform"], service)
    assert result.exit_code == 0 and "api-platform.apis.view" in result.output
    service.permissions.assert_called_once_with("API Platform")
def test_list_api_filters_and_wide_columns():
    from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import _translate_row
    from apiops_orchestrator.application.services.api_listing_service import CatalogFilters

    listing = MagicMock()
    listing.list_apis.return_value = [
        _translate_row({"apiId": 400, "apiName": "Orchestrator Auth API", "basePath": "/orq-auth/v1", "version": "1.0.1", "owner": "paulo", "contextType": "GROUP", "contextGroupName": "APIOps",
                        "lastRevision": 8948, "revisions": [{"id": 8948, "revisionNumber": 4}], "wokflow": [{"apiRevision": 8948, "workflowId": 139, "workflowStageId": 420}]}),
    ]
    obj = {"api_listing_service_factory": lambda: listing}
    result = runner.invoke(app, ["sen", "list", "api", "--all", "--owner", "paulo", "--team", "APIOps", "--wide"], obj=obj)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    # Em 80 colunas a grade de 9 colunas quebra células; as colunas são conferidas no JSON abaixo.
    assert "filtros: --owner paulo --team APIOps" in out
    assert "janela: todas as APIs visíveis (--all)" in out
    listing.list_apis.assert_called_once_with(query=None, offset=0, limit=None, filters=CatalogFilters(owner="paulo", team="APIOps"))

    result = runner.invoke(app, ["sen", "list", "api", "--stage", "420", "-w", "-o", "json"], obj=obj)
    document = json.loads(result.output)
    assert document[0]["owner"] == "paulo" and document[0]["workflowStageId"] == 420
    assert listing.list_apis.call_args.kwargs["filters"] == CatalogFilters(stage_id=420)

    assert runner.invoke(app, ["sen", "list", "api", "--context", "nope"], obj=obj).exit_code == 1
    assert runner.invoke(app, ["sen", "list", "api", "--id", "400", "--owner", "x"], obj=obj).exit_code == 1

    # sem filtro, a assinatura antiga é preservada (compatibilidade com os testes existentes)
    listing.list_apis.reset_mock()
    runner.invoke(app, ["sen", "list", "api"], obj=obj)
    listing.list_apis.assert_called_once_with(query=None, offset=0, limit=10)


def test_list_api_filter_by_attribute():
    from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import _translate_row
    from apiops_orchestrator.application.services.api_listing_service import CatalogFilters

    listing = MagicMock()
    listing.list_apis.return_value = [
        _translate_row({"apiId": 400, "apiName": "Orchestrator Auth API",
                        "basePath": "/orq-auth/v1", "version": "1.0.1", "owner": "paulo",
                        "lastRevision": 8948, "revisions": [{"id": 8948, "revisionNumber": 4}]}),
    ]
    obj = {"api_listing_service_factory": lambda: listing}

    result = runner.invoke(app, ["sen", "list", "api", "--attribute", "My new"], obj=obj)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert 'filtros: --attribute "My new"' in out  # valor com espaço sai entre aspas
    assert "uma consulta por API" in out  # o custo do filtro é dito na saída
    assert listing.list_apis.call_args.kwargs["filters"] == CatalogFilters(attribute="My new")

    # drill-down é de UMA API: o filtro não combina com --id
    assert runner.invoke(
        app, ["sen", "list", "api", "--id", "400", "--attribute", "CLI"], obj=obj
    ).exit_code == 1
    # nome em branco não filtra nada: recusa antes da rede
    assert runner.invoke(app, ["sen", "list", "api", "--attribute", "   "], obj=obj).exit_code == 1
