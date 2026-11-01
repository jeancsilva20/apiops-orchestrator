"""Access Control (roles/usuários/times/permissões), referência de tipos, donos e filtros."""

import json

import pytest

from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    _translate_row,
)
from apiops_orchestrator.application.services.api_listing_service import CatalogFilters
from apiops_orchestrator.domain.services import access_control as access
from apiops_orchestrator.domain.services import api_navigation as nav
from apiops_orchestrator.domain.services import interceptor_types as itypes
from apiops_orchestrator.domain.services import tenant_catalog as tenant


# --------------------------------------------------------------------------- access control


def test_role_documents():
    policy = {
        "id": "u1",
        "name": "Admin",
        "description": "",
        "sensediaManaged": True,
        "usersChangeable": False,
        "products": [{"id": "p1", "name": "API Platform", "inlinePermission": "api-platform.enabled"}],
    }
    assert access.describe_role(policy) == {
        "id": "u1",
        "name": "Admin",
        "description": None,
        "managedBySensedia": True,
        "usersChangeable": False,
        "products": [{"id": "p1", "name": "API Platform", "inlinePermission": "api-platform.enabled"}],
    }
    permissions = [
        {"productName": "API Platform", "productId": "p1", "permissions": [
            {"id": "x", "code": "api-platform.apis.view", "name": "View", "description": ""},
            {"id": "y", "code": "api-platform.apis.create", "name": "Create", "description": "d"},
        ]},
        {"productName": "Access Control", "productId": "p0", "permissions": ["access-control.users.list"]},
    ]
    users = [{"username": "zed", "status": "CREATED", "email": "z"}, {"username": "ana", "status": "ACTIVE"}]
    document = access.role_document(policy, permissions, users)
    assert [b["product"] for b in document["permissions"]] == ["Access Control", "API Platform"]
    assert [p["code"] for p in document["permissions"][1]["permissions"]] == ["api-platform.apis.create", "api-platform.apis.view"]
    assert document["permissions"][0]["permissions"][0] == {"code": "access-control.users.list", "name": None, "description": None}
    assert [u["username"] for u in document["users"]] == ["ana", "zed"]
    assert document["totals"] == {"permissions": 3, "products": 2, "users": 2}
    assert access.role_matches(policy, "ADM") and not access.role_matches(policy, "nope")
    assert access.role_matches(policy, None)


def test_user_and_team_documents():
    user = {"username": "paulo", "name": "P", "email": "p@x", "status": "CREATED", "providerType": "LOCAL",
            "isFederated": False, "enabled": True, "mfaEnabled": False, "tags": ["t"], "createdAt": "d"}
    document = access.user_document(
        user,
        [{"name": "Lab", "description": ""}, {"name": "APIOps", "description": "d"}],
        [{"id": "r", "name": "Super Admin", "description": "all", "sensediaManaged": True}],
    )
    assert [t["name"] for t in document["teams"]] == ["APIOps", "Lab"]
    assert document["roles"] == [{"id": "r", "name": "Super Admin", "description": "all", "managedBySensedia": True}]
    assert document["isSuperAdmin"] is True and document["tags"] == ["t"] and document["enabled"] is True

    plain = access.user_document(user, [], [{"id": "r", "name": "Read-Only"}])
    assert plain["isSuperAdmin"] is False

    team = access.team_document({"name": "APIOps", "description": "d"}, [{"username": "b"}, {"username": "a"}])
    assert [m["username"] for m in team["members"]] == ["a", "b"] and team["totals"] == {"members": 2}


def test_permissions_document_groups_by_domain():
    document = access.permissions_document(
        "API Platform", ["api-platform.apis.view", "api-platform.apis.create", "api-platform.oauth-config.update", "weird"]
    )
    assert document["domains"] == [
        {"domain": "apis", "codes": ["api-platform.apis.create", "api-platform.apis.view"]},
        {"domain": "oauth-config", "codes": ["api-platform.oauth-config.update"]},
        {"domain": "weird", "codes": ["weird"]},
    ]
    assert document["totals"] == {"codes": 4, "domains": 3}


# --------------------------------------------------------------------------- referência de tipos (doc 06)


@pytest.mark.parametrize(
    "type_name,content,unknown,missing",
    [
        ("Mock", {"body": "x", "headers": "Content-Type: application/json", "status": "200", "ignoreBodyValidationMultiPartFormData": False}, [], []),
        ("Rate limit", {"quota": "100", "interval": "MINUTE", "limitBy": "TOTAL_CALLS"}, [], ["headerKey", "noHeaderBehavior", "rateLimitHeader", "soft", "softvalue"]),
        ("OAuth", {"grantTypes": ["CLIENT_CREDENTIALS"], "ignoreBodyValidationMultiPartFormData": False}, [], ["location", "name"]),
        ("Log", {"acceptedTerms": True}, [], ["encryptContent", "encryptPathAndParameters"]),
        ("Client ID validation", {"location": "ANY", "name": "client_id", "responseContentType": "APPLICATION_JSON"}, [], []),
        ("Custom", {"debug": False, "abort": False, "name": "x", "script": "//"}, [], ["id", "tags", "visibility"]),
        ("JSON schema validation", {"jsonSchema": "{\"type\":\"object\"}", "surprise": 1}, ["surprise"], []),
        ("log obfuscation", {"location": "HEADER", "attr": "a", "regexToReplace": "r", "replaceChar": "*"}, [], []),
    ],
)
def test_doc06_contents_match_the_reference(type_name, content, unknown, missing):
    result = itypes.check_fields(type_name, content)
    assert result is not None
    assert result["unknown"] == unknown
    assert result["missing"] == missing


def test_reference_catalog_and_lookups():
    assert itypes.find_type("Nope") is None
    assert itypes.check_fields("Nope", {"a": 1}) is None
    assert itypes.check_fields("Log", "not a dict") is None
    kind = itypes.find_type("rate LIMIT")
    described = itypes.describe_type(kind)
    assert described["type"] == "Rate limit" and described["executionPoints"] == ["request"]
    assert {f["name"] for f in described["fields"]} >= {"quota", "interval", "limitBy"}
    assert described["example"]["quota"] == "100"
    custom = itypes.describe_type(itypes.find_type("Custom"))
    assert custom["executionPoints"] == ["request", "response", "third"]
    names = [t.name for t in itypes.all_types()]
    assert len(names) == len(set(names)) and "Java" in names
    assert names == sorted(names, key=lambda n: (itypes.find_type(n).group.lower(), n.lower()))


# --------------------------------------------------------------------------- outros pontos e filtro de ponto


def _revision_with_third():
    item = lambda id_, point, kind, pos, status="REFERENCE": {  # noqa: E731
        "id": id_, "position": pos, "executionPoint": point, "type": kind, "status": status, "parent": None,
        "content": json.dumps({"name": "c", "script": "s"}) if kind == "Custom" else None,
    }
    return {
        "id": 1, "revisionNumber": 1,
        "interceptors": [item(1, "FIRST", "Log", 0), item(2, "SECOND", "Log", 1), item(3, "THIRD", "Custom", 2), item(4, "FIRST", "OAuth", 3, "CHANGED_VALUE")],
        "resources": [{"id": 10, "name": "R", "interceptors": [item(5, "THIRD", "Custom", 0)], "operations": []}],
    }


def test_other_points_are_listed_and_point_filter_applies():
    api = {"id": 1, "name": "A", "revisions": [], "environments": []}
    document = nav.scope_flows(api, _revision_with_third())
    root, resource = document["scopes"]
    assert [i["id"] for i in root["other"]] == [3] and root["other"][0]["executionPoint"] == "THIRD"
    assert [i["id"] for i in root["own"]["request"]] == [1, 4]
    assert root["own"]["request"][1]["status"] == "CHANGED_VALUE"
    assert root["counts"]["preserved"] == 1 and [i["id"] for i in resource["other"]] == [5]
    assert document["point"] is None

    third = nav.scope_flows(api, _revision_with_third(), point="third", effective=True)
    root = third["scopes"][0]
    assert third["point"] == "THIRD"
    assert root["own"] == {"request": [], "response": []} and root["effective"] == {"request": [], "response": []}
    assert [i["id"] for i in root["other"]] == [3]

    response = nav.scope_flows(api, _revision_with_third(), point="2")
    assert [i["id"] for i in response["scopes"][0]["own"]["response"]] == [2]
    assert response["scopes"][0]["own"]["request"] == [] and response["scopes"][0]["other"] == []

    assert nav.normalize_point(None) is None and nav.normalize_point("request") == "FIRST"
    with pytest.raises(ValueError):
        nav.normalize_point("fourth")


def test_item_zoom_carries_the_reference_check():
    api = {"id": 1, "name": "A", "revisions": [], "environments": []}
    revision = _revision_with_third()
    scope, item = nav.find_interceptor(revision, 3)
    document = nav.describe_interceptor(api, revision, scope, item)
    assert document["reference"] == {"type": "Custom", "known": ["name", "script"], "unknown": [], "missing": ["abort", "debug", "id", "tags", "visibility"]}
    assert document["interceptor"]["governed"] is False


# --------------------------------------------------------------------------- donos e filtros do catálogo


def _entries():
    return [
        _translate_row({"apiId": 1, "apiName": "A", "version": "1", "owner": "paulo", "contextType": "GROUP", "contextGroupName": "APIOps",
                        "lastRevision": 10, "revisions": [{"id": 10, "revisionNumber": 1}], "wokflow": [{"apiRevision": 10, "workflowId": 139, "workflowStageId": 420}]}),
        _translate_row({"apiId": 2, "apiName": "B", "version": "1", "owner": "paulo", "contextType": "ORGANIZATION",
                        "lastRevision": 20, "revisions": [{"id": 20, "revisionNumber": 1}], "wokflow": [{"apiRevision": 20, "workflowId": 139, "workflowStageId": 753}]}),
        _translate_row({"apiId": 3, "apiName": "C", "version": "1", "owner": "ana", "contextType": "ME"}),
        _translate_row({"apiId": 4, "apiName": "D", "version": "1"}),
    ]


def test_owners_summary():
    rows = tenant.owners_summary(_entries())
    assert [(r["owner"], r["total"]) for r in rows] == [("paulo", 2), ("-", 1), ("ana", 1)]
    assert rows[0]["contexts"] == ["group", "organization"] and rows[0]["teams"] == ["APIOps"]
    assert [a["id"] for a in rows[0]["apis"]] == [1, 2]


def test_catalog_filters():
    a, b, c, d = _entries()
    assert CatalogFilters().active is False
    assert CatalogFilters(owner="PAULO").matches(a) and not CatalogFilters(owner="paulo").matches(c)
    assert CatalogFilters(team="apiops").matches(a) and not CatalogFilters(team="apiops").matches(b)
    assert CatalogFilters(context="group").matches(a) and CatalogFilters(context="me").matches(c)
    assert not CatalogFilters(context="organization").matches(d)
    assert CatalogFilters(workflow_id=139).matches(a) and CatalogFilters(stage_id=753).matches(b)
    assert not CatalogFilters(stage_id=753).matches(a) and not CatalogFilters(workflow_id=139).matches(c)
    assert CatalogFilters(owner="paulo", stage_id=420).matches(a) and not CatalogFilters(owner="paulo", stage_id=420).matches(b)
