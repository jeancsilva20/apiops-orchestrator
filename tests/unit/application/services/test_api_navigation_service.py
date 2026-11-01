"""Use-cases de navegação: visibilidade, seleção de revisão e tradução de falhas."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    UNAUTHORIZED_MESSAGE,
    UNAVAILABLE_MESSAGE,
)
from apiops_orchestrator.application.exceptions.navigation_exceptions import (
    NavigationApiNotFound,
    NavigationCustomNotFound,
    NavigationError,
    NavigationInterceptorNotFound,
    NavigationPlatformError,
    NavigationRevisionNotFound,
    NavigationScopeNotFound,
)
from apiops_orchestrator.application.services.api_navigation_service import (
    ApiNavigationService,
)
from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from apiops_orchestrator.domain.models.api_visibility_model import OwnershipContext
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiPort,
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
    ManagerApiUnexpectedResponseError,
)


def _api():
    revision = {
        "id": 8948,
        "revisionNumber": 4,
        "interceptors": [
            {"id": 1, "position": 0, "executionPoint": "FIRST", "type": "Log", "status": "REFERENCE"}
        ],
        "resources": [
            {
                "id": 10,
                "name": "Token",
                "interceptors": [],
                "operations": [
                    {"id": 11, "method": "POST", "path": "/oauth2/token", "interceptors": []}
                ],
            }
        ],
    }
    return {
        "id": 400,
        "name": "Orchestrator Auth API",
        "version": "1.0.1",
        "basePath": "/orq-auth/v1",
        "revisions": [{"id": 8862, "revisionNumber": 1, "interceptors": [], "resources": []}, revision],
        "lastRevision": revision,
        "environments": [],
    }


def _port(api=None):
    port = MagicMock(spec=ManagerApiPort)
    port.get_api_by_id.return_value = api if api is not None else _api()
    return port


def _developer(username="dev", groups=("APIOps",)):
    return SimpleNamespace(is_super_admin=False, userName=username, userGroups=list(groups))


# --------------------------------------------------------------------------- visibilidade


def test_super_admin_reads_manager_directly():
    port = _port()
    service = ApiNavigationService(port, session=None)

    detail = service.api_detail(400)

    assert detail["id"] == 400 and detail["lastRevisionNumber"] == 4
    port.get_api_by_id.assert_called_once_with(400)
    port.list_api_detail.assert_not_called()


def test_developer_goes_through_the_catalog_guard():
    port = _port()
    port.list_api_detail.return_value = ApiCatalogEntry(
        id=400, contextType=OwnershipContext.GROUP, contextGroupName="APIOps"
    )
    service = ApiNavigationService(port, session=_developer())

    assert service.api_detail(400)["id"] == 400
    port.list_api_detail.assert_called_once_with(400)


@pytest.mark.parametrize(
    "entry",
    [
        None,
        ApiCatalogEntry(id=400, contextType=OwnershipContext.ME, owner="someone-else"),
        ApiCatalogEntry(id=400, contextType=OwnershipContext.GROUP, contextGroupName="Other"),
    ],
)
def test_invisible_or_missing_api_answers_not_found(entry):
    port = _port()
    port.list_api_detail.return_value = entry
    service = ApiNavigationService(port, session=_developer())

    with pytest.raises(NavigationApiNotFound) as info:
        service.api_detail(400)
    assert "400" in info.value.message
    port.get_api_by_id.assert_not_called()


# --------------------------------------------------------------------------- revisão


def test_revision_by_number_by_id_and_missing():
    service = ApiNavigationService(_port(), session=None)

    _, by_number = service.revision(400, number=1)
    assert by_number["id"] == 8862
    _, by_id = service.revision(400, revision_id=8948)
    assert by_id["revisionNumber"] == 4
    _, current = service.revision(400)
    assert current["id"] == 8948

    with pytest.raises(NavigationRevisionNotFound) as info:
        service.revision(400, number=7)
    assert "de número 7" in info.value.message
    assert "1, 4" in info.value.message
    assert "sen get api --id 400" in info.value.message

    with pytest.raises(NavigationRevisionNotFound) as info:
        service.revision(400, revision_id=5)
    assert "de id 5" in info.value.message


# --------------------------------------------------------------------------- níveis


def test_structure_interceptors_and_item():
    service = ApiNavigationService(_port(), session=None)

    structure = service.structure(400)
    assert structure["totals"] == {"resources": 1, "operations": 1}

    flows = service.interceptors(400, resource="Token", effective=True)
    assert [s["scope"] for s in flows["scopes"]] == ["token", "POST /oauth2/token"]

    with pytest.raises(NavigationScopeNotFound) as info:
        service.interceptors(400, resource="Token", operation="GET /nope")
    assert "--resource 'Token' --operation 'GET /nope'" in info.value.message

    item = service.interceptor(400, 1)
    assert item["scope"]["kind"] == "root" and item["interceptor"]["type"] == "Log"

    with pytest.raises(NavigationInterceptorNotFound):
        service.interceptor(400, 999)


def test_custom_interceptor_present_and_absent():
    port = _port()
    port.get_custom_interceptor_by_id.return_value = {"id": 31, "name": "X", "script": "s"}
    service = ApiNavigationService(port, session=None)
    assert service.custom_interceptor(31) == {"id": 31, "name": "X", "script": "s"}

    port.get_custom_interceptor_by_id.return_value = None
    with pytest.raises(NavigationCustomNotFound) as info:
        service.custom_interceptor(31)
    assert "31" in info.value.message


def test_swagger_uses_the_selected_revision_id():
    port = _port()
    port.get_revision_swagger.return_value = {"openapi": "3.0.0"}
    service = ApiNavigationService(port, session=None)

    assert service.swagger(400, number=1) == {"openapi": "3.0.0"}
    port.get_revision_swagger.assert_called_once_with(8862)

    port.get_revision_swagger.side_effect = ManagerApiUnexpectedResponseError("x")
    with pytest.raises(NavigationPlatformError):
        service.swagger(400)


def test_export_materializes_the_canonical_tree():
    service = ApiNavigationService(_port(), session=None)

    api, revision, result = service.export(400, number=4)

    assert api["id"] == 400 and revision["id"] == 8948
    assert result.paths == [
        "api-basic-info.yaml",
        "all.yaml",
        "resources/token/resource.yaml",
        "resources/token/post_oauth2_token.yaml",
    ]


# --------------------------------------------------------------------------- falhas


@pytest.mark.parametrize(
    "signal,expected_type,expected_text",
    [
        (ManagerApiTransportRejectedError(404, "Not Found"), NavigationApiNotFound, "400"),
        (ManagerApiTransportRejectedError(401, "Unauthorized"), NavigationPlatformError, UNAUTHORIZED_MESSAGE),
        (ManagerApiTransportUnavailableError("down"), NavigationPlatformError, UNAVAILABLE_MESSAGE),
    ],
)
def test_port_signals_become_navigation_errors(signal, expected_type, expected_text):
    port = _port()
    port.get_api_by_id.side_effect = signal
    service = ApiNavigationService(port, session=None)

    with pytest.raises(expected_type) as info:
        service.api_detail(400)
    assert expected_text in info.value.message


def test_custom_404_outside_an_api_is_not_an_api_not_found():
    port = _port()
    port.get_custom_interceptor_by_id.side_effect = ManagerApiTransportRejectedError(
        418, "Teapot"
    )
    service = ApiNavigationService(port, session=None)
    with pytest.raises(NavigationPlatformError):
        service.custom_interceptor(1)


# --------------------------------------------------------------------------- catálogos e governança (mapeamento APIM/AG)


def _workflow_327():
    return {
        "workflowId": 327,
        "workflowName": "Sura",
        "workflowCategory": "TEAM",
        "groupId": "Lab-tech",
        "stages": [
            {
                "workflowStageId": 784,
                "workflowStageName": "Dev-Uat",
                "position": 2,
                "completenessRequisite": 80.0,
                "interceptorsRequisites": [],
                "attributesRequisites": [{"attributeId": 149, "tagId": None, "mustHave": True}],
                "deployableEnvironments": [9],
                "environments": [],
            },
            {
                "workflowStageId": 783,
                "workflowStageName": "Sandbox",
                "position": 1,
                "completenessRequisite": 0.0,
                "interceptorsRequisites": [
                    {"interceptorType": "Log", "mustHave": True, "executionPoint": "FIRST", "positionType": "ANY", "flowType": "API"},
                    {"interceptorType": "OAuth", "mustHave": True, "executionPoint": "FIRST", "positionType": "ANY", "flowType": "API"},
                ],
                "attributesRequisites": [],
                "deployableEnvironments": [1],
                "environments": [],
            },
        ],
    }


def _governed_port():
    api = _api()
    api["revisions"][1].update({"workflowId": 327, "workflowStageId": 783})
    api["lastRevision"] = api["revisions"][1]
    api["apiTags"] = [{"attributeName": "My new", "tags": ["Tag1"]}]
    api["environments"] = [
        {"id": 1, "name": "Default", "revisionDeployed": {"revisionId": 8948, "revisionNumber": 4}},
        {"id": 9, "name": "HMG"},
    ]
    port = _port(api)
    port.get_workflow.return_value = _workflow_327()
    port.list_workflows.return_value = [_workflow_327()]
    port.list_environments.return_value = [{"id": 1, "name": "Default", "inboundUrl": "https://gw/", "isDeployable": True}, {"id": 9, "name": "HMG"}]
    port.list_attributes.return_value = [{"id": 149, "name": "My new", "tags": ["Tag1", "Tag2"], "inUse": True}, {"id": 96, "name": "CLI", "tags": []}]
    port.get_revision_completeness.return_value = SimpleNamespace(score=77.5, suggestions=["a", "b"])
    return port


def test_catalog_listings_are_normalized():
    port = _governed_port()
    port.list_interceptor_catalog.return_value = [
        {"name": "Log", "category": "DEFAULT", "executionPoint": "1;2", "flowType": "ANY", "tags": ["Logging"], "id": None},
        {"name": "Oauth - RFC", "category": "JAVASCRIPT", "executionPoint": "1", "flowType": "ANY", "tags": ["Oauth"], "id": 1},
        {"name": "Access token metric", "category": "DEFAULT", "executionPoint": "2", "flowType": "API", "tags": [], "id": None},
    ]
    service = ApiNavigationService(port, session=None)

    assert service.environments()[0] == {"id": 1, "name": "Default", "description": None, "inboundUrl": "https://gw/", "isDeployable": True, "tlsType": None}
    assert service.attributes()[1] == {"id": 96, "name": "CLI", "tags": [], "inUse": None}

    workflows = service.workflows()
    assert workflows[0]["name"] == "Sura" and workflows[0]["group"] == "Lab-tech"
    assert [s["id"] for s in workflows[0]["stages"]] == [783, 784]  # ordenados por posição
    assert workflows[0]["stages"][0]["interceptors"] == 2

    catalog = service.interceptor_catalog()
    assert [c["name"] for c in catalog] == ["Access token metric", "Log", "Oauth - RFC"]  # nativos primeiro, por nome
    assert catalog[1]["executionPoints"] == ["request", "response"] and catalog[1]["kind"] == "native"
    assert catalog[2] == {"name": "Oauth - RFC", "kind": "custom", "category": "JAVASCRIPT", "id": 1, "executionPoints": ["request"], "flowType": "ANY", "tags": ["Oauth"]}
    assert [c["name"] for c in service.interceptor_catalog(custom_only=True)] == ["Oauth - RFC"]
    assert [c["name"] for c in service.interceptor_catalog(tag="logging")] == ["Log"]


def test_workflow_detail_resolves_names_and_missing_workflow():
    port = _governed_port()
    service = ApiNavigationService(port, session=None)

    document = service.workflow(327)
    assert document["id"] == 327
    sandbox, dev_uat = document["stages"]
    assert sandbox["name"] == "Sandbox" and sandbox["deployableEnvironments"] == [{"id": 1, "name": "Default"}]
    assert dev_uat["attributes"][0]["name"] == "My new"

    port.get_workflow.side_effect = ManagerApiTransportRejectedError(404, "Not Found")
    with pytest.raises(NavigationError) as info:
        service.workflow(999)
    assert "Workflow 999" in info.value.message and "sen list workflows" in info.value.message


def test_api_detail_enriches_revisions_with_stage_names():
    service = ApiNavigationService(_governed_port(), session=None)
    revisions = {r["number"]: r for r in service.api_detail(400)["revisions"]}
    assert revisions[4]["workflowName"] == "Sura" and revisions[4]["stageName"] == "Sandbox"
    assert revisions[1]["stageName"] is None


def test_api_detail_survives_catalog_failure():
    port = _governed_port()
    port.list_workflows.side_effect = ManagerApiTransportUnavailableError("down")
    document = ApiNavigationService(port, session=None).api_detail(400)
    assert document["revisions"][1]["stageName"] is None


def test_governance_evaluates_current_and_next_stage():
    service = ApiNavigationService(_governed_port(), session=None)

    document = service.governance(400)

    assert document["workflow"]["name"] == "Sura"
    assert document["stage"] == {"id": 783, "name": "Sandbox", "position": 1}
    assert document["maturity"] == {"score": 77.5, "suggestions": 2}
    assert document["deployedIn"] == [{"id": 1, "name": "Default"}]

    current = document["current"]
    assert current["summary"]["overall"] == "fail"
    by_requirement = {v["requirement"]: v["status"] for v in current["verdicts"]}
    assert by_requirement["deve ter Log no request na raiz da API"] == "ok"
    assert by_requirement["deve ter OAuth no request na raiz da API"] == "fail"

    following = document["next"]
    assert following["stage"]["name"] == "Dev-Uat"
    statuses = {v["requirement"]: v["status"] for v in following["verdicts"]}
    assert statuses["maturidade (completeness) ≥ 80%"] == "fail"
    assert statuses["deve declarar o atributo My new"] == "ok"
    assert statuses["deploy só nos ambientes permitidos pelo stage"] == "fail"
    assert document["warnings"] == []


def test_governance_without_stage_or_with_unknown_stage_warns():
    port = _governed_port()
    api = port.get_api_by_id.return_value
    api["revisions"][1]["workflowStageId"] = None
    service = ApiNavigationService(port, session=None)
    document = service.governance(400)
    assert document["current"] is None and document["warnings"]

    api["revisions"][1]["workflowStageId"] = 999
    document = service.governance(400)
    assert document["workflow"]["id"] == 327 and document["stage"] is None
    assert "999" in document["warnings"][0]


def test_governance_flags_invalid_tags_and_missing_completeness():
    port = _governed_port()
    port.get_api_by_id.return_value["apiTags"] = [{"attributeName": "My new", "tags": ["Nope"]}]
    port.get_revision_completeness.side_effect = ManagerApiTransportUnavailableError("down")
    document = ApiNavigationService(port, session=None).governance(400)
    assert document["maturity"] == {"score": None, "suggestions": None}
    assert any("'Nope'" in w for w in document["warnings"])
    assert any("completeness" in w for w in document["warnings"])
    statuses = {v["requirement"]: v["status"] for v in document["next"]["verdicts"]}
    assert statuses["maturidade (completeness) ≥ 80%"] == "unknown"
    assert statuses["deve declarar o atributo My new"] == "fail"  # tag inválida não conta


def test_impact_translates_the_tree_and_picks_a_default_environment():
    port = _governed_port()
    port.get_impact_tree.return_value = {
        "rootNode": {
            "name": "Orchestrator Auth API",
            "type": "REST",
            "properties": [{"key": "Revision", "value": "4"}, {"key": "Base Path", "value": "/orq-auth/v1"}],
            "children": [
                {
                    "name": "/users/{username}",
                    "type": "RESOURCE",
                    "children": [
                        {
                            "name": "GET",
                            "type": "METHOD",
                            "operationId": 9121,
                            "children": [
                                {"name": "API Destination", "type": "DESTINATION", "properties": [{"key": "Endpoint", "value": "https://backend/users"}]}
                            ],
                        }
                    ],
                },
                {"name": "/oauth2/token", "type": "RESOURCE", "children": [{"name": "POST", "type": "METHOD", "operationId": 8953}]},
                {
                    "name": "Plan A",
                    "type": "PLAN",
                    "children": [{"name": "App 1", "type": "APP", "properties": [{"key": "Status", "value": "APPROVED"}, {"key": "appId", "value": "42"}]}],
                },
            ],
        }
    }
    service = ApiNavigationService(port, session=None)

    document = service.impact(400)

    port.get_impact_tree.assert_called_once_with(400, 1)  # primeiro ambiente com revisão no ar
    assert document["environment"] == {"id": 1, "name": "Default"}
    assert document["revisionNumber"] == "4" and document["basePath"] == "/orq-auth/v1"
    assert document["routes"] == [
        {"path": "/oauth2/token", "methods": [{"method": "POST", "operationId": 8953, "destination": None}]},
        {"path": "/users/{username}", "methods": [{"method": "GET", "operationId": 9121, "destination": "https://backend/users"}]},
    ]
    assert document["plans"] == [{"name": "Plan A", "apps": [{"name": "App 1", "status": "APPROVED", "appId": "42"}]}]
    assert document["totals"] == {"routes": 2, "operations": 2, "plans": 1, "apps": 1}

    service.impact(400, 9)
    assert port.get_impact_tree.call_args.args == (400, 9)

    port.get_impact_tree.return_value = {}
    with pytest.raises(NavigationPlatformError):
        service.impact(400)


# --------------------------------------------------------------------------- consumo e infra


def _consumer_port():
    port = _governed_port()
    port.get_environment.return_value = {
        "id": 1, "name": "Default", "inboundUrl": "https://gw/",
        "mapVars": [{"id": 1, "name": "M", "vars": [
            {"key": "backendUrl", "value": "http://b", "variableType": "DEFAULT"},
            {"key": "basicAuth", "value": "Basic x", "variableType": "DEFAULT"},
        ]}],
        "revisionsDeployed": [{"apiId": 400, "apiName": "Orchestrator Auth API", "revisionId": 8948, "revisionNumber": 4}],
    }
    port.list_apps.return_value = [
        {"id": 42, "name": "Super Admin", "status": "APPROVED", "developer": "a@x", "clientId": "*****", "secret": "*****",
         "apis": [{"id": 400, "name": "Orchestrator Auth API", "plans": [{"id": 66, "name": "P"}]}], "accessTokens": []},
        {"id": 7, "name": "Other", "status": "APPROVED", "developer": "b@x", "apis": [], "accessTokens": []},
    ]
    port.get_app.return_value = port.list_apps.return_value[0]
    port.list_plans.return_value = [
        {"id": 66, "name": "P", "defaultPlan": True, "api": {"id": 400, "name": "Orchestrator Auth API"}, "interceptors": []},
        {"id": 10, "name": "CRM default", "defaultPlan": True, "api": {"id": 29, "name": "CRM Service"}, "interceptors": [{"id": 1}]},
    ]
    port.get_plan.return_value = port.list_plans.return_value[1]
    port.list_access_tokens.return_value = [
        {"_id": "t1", "code": "S", "owner": "o", "app": {"id": 45, "name": "CI"}, "status": "ACTIVE", "creationDate": "2026-11-01", "apis": [{"id": 400, "name": "x"}]},
        {"_id": "t2", "code": "S", "owner": "o", "app": {"id": 42, "name": "SA"}, "status": "ACTIVE", "creationDate": "2026-11-02", "apis": [{"id": 1, "name": "y"}]},
    ]
    port.list_users.return_value = [{"username": "zed", "status": "CREATED"}, {"username": "ana", "status": "ACTIVE"}]
    port.list_groups.return_value = [{"name": "Lab", "description": ""}, {"name": "APIOps", "description": "d"}]
    port.list_inbounds.return_value = [{"id": 1, "name": "Default", "host": "h"}]
    port.list_gateway_pools.return_value = [{"id": 1, "name": "default", "routes": 3}]
    return port


def test_environment_and_variables_mask_secrets():
    port = _consumer_port()
    service = ApiNavigationService(port, session=None)

    document = service.environment(1)
    assert document["deployed"][0]["apiId"] == 400
    values = {v["key"]: v["value"] for v in document["variables"]}
    assert values == {"backendUrl": "http://b", "basicAuth": "•••••"}

    revealed = {v["key"]: v["value"] for v in service.variables(1, show_values=True)}
    assert revealed["basicAuth"] == "Basic x"
    assert [v["key"] for v in service.variables(1, key="url")] == ["backendUrl"]

    # sem --env: percorre todos os ambientes do catálogo
    port.list_environments.return_value = [{"id": 1, "name": "Default"}, {"id": 9, "name": "HMG"}]
    rows = service.variables()
    assert len(rows) == 4 and port.get_environment.call_count >= 3

    port.get_environment.return_value = {}
    with pytest.raises(NavigationError) as info:
        service.environment(77)
    assert "Ambiente 77" in info.value.message


def test_apps_plans_tokens_filters_and_details():
    port = _consumer_port()
    service = ApiNavigationService(port, session=None)

    assert [a["id"] for a in service.apps()] == [7, 42]  # ordenados por nome
    assert [a["id"] for a in service.apps(api_id=400)] == [42]
    assert [a["id"] for a in service.apps(query="super")] == [42]
    assert service.app(42)["apis"][0]["plans"] == [{"id": 66, "name": "P", "defaultPlan": None}]
    port.get_app.return_value = None
    with pytest.raises(NavigationError):
        service.app(999)

    assert [p["id"] for p in service.plans()] == [10, 66]  # por nome da API
    assert [p["id"] for p in service.plans(api_id=400)] == [66]
    assert [p["id"] for p in service.plans(query="crm")] == [10]
    assert service.plan(10)["flow"] == {"request": [], "response": []}
    port.get_plan.return_value = None
    with pytest.raises(NavigationError):
        service.plan(999)

    tokens = service.tokens()
    assert [t["id"] for t in tokens] == ["t2", "t1"]  # mais recentes primeiro
    assert "S" not in str(tokens)
    assert [t["id"] for t in service.tokens(app_id=45)] == ["t1"]
    assert [t["id"] for t in service.tokens(api_id=1)] == ["t2"]


def test_people_and_infra_listings():
    port = _consumer_port()
    service = ApiNavigationService(port, session=None)
    assert [u["username"] for u in service.users("a")] == ["ana", "zed"]
    port.list_users.assert_called_once_with("a")
    assert [g["name"] for g in service.teams()] == ["APIOps", "Lab"]
    assert service.inbounds()[0]["host"] == "h"
    assert service.gateway_pools()[0]["routes"] == 3

    port.list_apps.side_effect = ManagerApiTransportRejectedError(401, "Unauthorized")
    with pytest.raises(NavigationPlatformError) as info:
        service.apps()
    assert UNAUTHORIZED_MESSAGE in info.value.message
