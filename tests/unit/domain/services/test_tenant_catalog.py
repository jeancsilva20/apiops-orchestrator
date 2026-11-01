"""Elementos ligados às APIs: ambientes/variáveis (mascaramento), apps, planos, tokens."""

import json

import pytest

from apiops_orchestrator.domain.services import tenant_catalog as tenant


def _environment():
    return {
        "id": 1,
        "name": "Default",
        "description": "Environment Default",
        "inboundUrl": "https://gw/",
        "visibility": {"visibilityType": "ORGANIZATION"},
        "label": {"name": "default", "labelType": "CLOUD"},
        "inboundAddress": {"host": "gw", "protocolType": "HTTPS", "tlsType": "TLS"},
        "mapVars": [
            {
                "id": 1,
                "name": "OAUTH API",
                "description": "",
                "vars": [
                    {"key": "destinationAuthorization", "value": "http://auth.svc", "variableType": "DEFAULT"},
                    {"key": "basicAuthManager", "value": "Basic abc", "variableType": "DEFAULT"},
                    {"key": "dbPassword", "value": "x", "variableType": "SECURED"},
                    {"key": "plain", "value": "Bearer tok", "variableType": "DEFAULT"},
                ],
            },
            {"id": 2, "name": "B", "vars": [{"key": "zeta", "value": "1", "variableType": "Default"}]},
        ],
        "revisionsDeployed": [
            {"apiId": 400, "apiName": "Orchestrator Auth API", "apiVersion": "1.0.1", "revisionId": 8948, "revisionNumber": 4},
            {"apiId": 1, "apiName": "oAuth - RFC", "apiVersion": "2.0.0", "revisionId": 1, "revisionNumber": 1},
        ],
    }


@pytest.mark.parametrize(
    "key,value,expected",
    [
        ("destinationAuthorization", "http://x", True),  # 'auth' no nome
        ("backendUrl", "http://x", False),
        ("apiVersion", "1.0.0", False),
        ("x", "Basic abc", True),
        ("x", "bearer abc", True),
        ("client_secret", "", True),
        ("senhaBanco", "", True),
        ("timeout", "30", False),
        ("client_id_esteira", "abc", True),
    ],
)
def test_looks_sensitive(key, value, expected):
    assert tenant.looks_sensitive(key, value) is expected


def test_variables_are_masked_by_default_and_secured_never_revealed():
    rows = tenant.environment_variables(_environment())
    by_key = {r["key"]: r for r in rows}
    assert [r["key"] for r in rows] == ["zeta", "basicAuthManager", "dbPassword", "destinationAuthorization", "plain"]  # por (mapa, chave)
    assert by_key["basicAuthManager"]["value"] == tenant.MASK and by_key["basicAuthManager"]["masked"] is True
    assert by_key["dbPassword"]["value"] == tenant.MASK and by_key["dbPassword"]["variableType"] == "SECURED"
    assert by_key["plain"]["value"] == tenant.MASK  # valor com esquema Bearer
    assert by_key["zeta"]["value"] == "1" and by_key["zeta"]["masked"] is False
    assert by_key["zeta"]["variableType"] == "DEFAULT" and by_key["zeta"]["map"] == "B"
    assert by_key["zeta"]["environmentName"] == "Default"

    revealed = {r["key"]: r for r in tenant.environment_variables(_environment(), show_values=True)}
    assert revealed["basicAuthManager"]["value"] == "Basic abc" and revealed["basicAuthManager"]["masked"] is False
    assert revealed["dbPassword"]["value"] == tenant.MASK and revealed["dbPassword"]["masked"] is True

    assert [r["key"] for r in tenant.environment_variables(_environment(), key="AUTH")] == [
        "basicAuthManager",
        "destinationAuthorization",
    ]


def test_describe_environment_has_no_secret_and_sorted_deployments():
    document = tenant.describe_environment(_environment())
    assert document["gateway"] == {"pool": "default", "type": "CLOUD", "host": "gw", "protocol": "HTTPS", "tls": "TLS"}
    assert document["variableMaps"] == [
        {"id": 1, "name": "OAUTH API", "description": None, "variables": 4},
        {"id": 2, "name": "B", "description": None, "variables": 1},
    ]
    assert [d["apiName"] for d in document["deployed"]] == ["oAuth - RFC", "Orchestrator Auth API"]
    assert document["totals"] == {"deployed": 2}
    assert "Basic abc" not in json.dumps(document)
    assert "dataPlaneSecret" not in json.dumps(document)


def _app():
    return {
        "id": 42,
        "name": "Super Admin",
        "status": "APPROVED",
        "developer": "dev@x",
        "description": "",
        "clientId": "*****",
        "secret": "*****",
        "creationDate": "2026-01-01",
        "extraInfo": {"k": "v"},
        "inboundAddresses": [{"name": "Default"}],
        "accessTokens": [{"_id": "t1"}],
        "apis": [
            {"id": 400, "name": "Orchestrator Auth API", "version": "1.0.1", "plans": [{"id": 66, "name": "P", "defaultPlan": True}]},
            {"id": 1, "name": "oAuth - RFC", "version": "2.0.0", "plans": []},
        ],
    }


def test_describe_app_drops_credentials_and_sorts_subscriptions():
    document = tenant.describe_app(_app())
    assert "clientId" not in document and "secret" not in document
    assert document["accessTokens"] == 1 and document["description"] is None
    assert [a["name"] for a in document["apis"]] == ["oAuth - RFC", "Orchestrator Auth API"]
    assert document["apis"][1]["plans"] == [{"id": 66, "name": "P", "defaultPlan": True}]
    assert "extraInfo" not in document

    detail = tenant.describe_app(_app(), detail=True)
    assert detail["extraInfo"] == {"k": "v"} and detail["inboundAddresses"] == ["Default"]

    assert tenant.app_subscribes(_app(), 400) is True
    assert tenant.app_subscribes(_app(), 999) is False


def test_describe_plan_summary_and_flow():
    plan = {
        "id": 66,
        "name": "Plano",
        "description": "",
        "defaultPlan": True,
        "api": {"id": 400, "name": "Orchestrator Auth API", "version": "1.0.1"},
        "interceptors": [
            {"id": 2, "position": 1, "executionPoint": "SECOND", "type": "Log", "status": "REFERENCE", "content": '{"a":1}'},
            {"id": 1, "position": 0, "executionPoint": "FIRST", "type": "Rate limit", "status": "REFERENCE", "content": '{"quota":"100"}'},
            {"id": 3, "position": 2, "executionPoint": "FIRST", "type": "Mock", "status": "REMOVED"},
        ],
    }
    summary = tenant.describe_plan(plan)
    assert summary == {
        "id": 66,
        "name": "Plano",
        "description": None,
        "defaultPlan": True,
        "api": {"id": 400, "name": "Orchestrator Auth API", "version": "1.0.1"},
        "interceptors": 3,
    }
    detail = tenant.describe_plan(plan, detail=True)
    assert [i["type"] for i in detail["flow"]["request"]] == ["Rate limit"]
    assert detail["flow"]["request"][0]["content"] == {"quota": "100"}
    assert [i["id"] for i in detail["flow"]["response"]] == [2]
    assert tenant.describe_plan({"id": 1, "name": "x"})["api"] is None


def test_describe_token_hides_code_and_filters():
    token = {
        "_id": "abc",
        "code": "SECRET",
        "refreshToken": "SECRET2",
        "owner": "o@x",
        "app": {"id": 45, "name": "CI", "clientId": "*****"},
        "status": "ACTIVE",
        "refreshStatus": "ACTIVE",
        "expiresIn": 43200,
        "creationDate": "2026-11-01",
        "expiredDate": "2026-11-02",
        "apis": [{"id": 400, "name": "Orchestrator Auth API", "version": "1.0.1"}],
        "planIds": [66],
        "extraInfo": {"sensediaGeneratedBy": "client_credentials"},
    }
    document = tenant.describe_token(token)
    assert "SECRET" not in json.dumps(document)
    assert document["id"] == "abc" and document["app"] == {"id": 45, "name": "CI"}
    assert document["generatedBy"] == "client_credentials" and document["planIds"] == [66]

    assert tenant.token_touches(token, app_id=45, api_id=None)
    assert tenant.token_touches(token, app_id=None, api_id=400)
    assert not tenant.token_touches(token, app_id=1, api_id=None)
    assert not tenant.token_touches(token, app_id=45, api_id=999)


def test_people_and_infra_descriptions():
    assert tenant.describe_user({"username": "u", "status": "CREATED", "email": "e"})["email"] == "e"
    assert tenant.describe_group({"name": "APIOps", "description": ""}) == {"name": "APIOps", "description": None}
    inbound = tenant.describe_inbound({"id": 1, "name": "Default", "host": "h", "protocolType": "HTTPS", "tlsType": "TLS", "tlsSecurity": {"minTlsVersion": "TLS_1_2", "maxTlsVersion": "TLS_1_3", "certificateId": "c"}, "gatewayType": "SAAS"})
    assert inbound["minTlsVersion"] == "TLS_1_2" and "certificateId" not in inbound
    assert tenant.describe_gateway_pool({"id": 1, "name": "default", "labelType": "CLOUD", "routes": 396}) == {"id": 1, "name": "default", "description": None, "type": "CLOUD", "routes": 396}
    assert tenant.matches_query(("Super Admin", None), "admin") and not tenant.matches_query(("x",), "y")
    assert tenant.matches_query(("x",), None)
