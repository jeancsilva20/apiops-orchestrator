"""Leituras de navegação sobre o wire cru: níveis api → estrutura → fluxos → item."""

import json
import pathlib

import pytest

from apiops_orchestrator.domain.services import api_navigation as nav

FIXTURES = pathlib.Path(__file__).parents[3] / "fixtures" / "manager"


def _item(id_, point, kind, position=0, status="REFERENCE", content=None, **extra):
    return {
        "id": id_,
        "position": position,
        "executionPoint": point,
        "type": kind,
        "status": status,
        "content": json.dumps(content) if isinstance(content, (dict, list)) else content,
        "parent": None,
        "parentType": "REVISION",
        "customInterceptorId": None,
        **extra,
    }


def _wire():
    """API com duas revisões; a corrente quebra herança no recurso Token."""
    revision = {
        "id": 8948,
        "revisionNumber": 4,
        "lifeCycle": "DRAFT",
        "workflowId": 139,
        "workflowStageId": 420,
        "destination": None,
        "timeout": None,
        "interceptors": [
            _item(1, "FIRST", "Log", 0, content={"acceptedTerms": True}),
            _item(2, "FIRST", "OAuth", 1, content={"grantTypes": ["CLIENT_CREDENTIALS"]}),
            _item(3, "SECOND", "Log", 2, content={"acceptedTerms": True}),
            _item(4, "THIRD", "Trace", 3),  # fora de FIRST/SECOND: preservado
        ],
        "resources": [
            {
                "id": 10,
                "name": "Token",
                "description": "Recurso de token",
                "destination": None,
                "timeout": None,
                "interceptors": [
                    _item(20, "FIRST", "OAuth", 0, status="REMOVED", parent={"id": 2}),
                ],
                "operations": [
                    {
                        "id": 11,
                        "method": "POST",
                        "path": "/oauth2/token",
                        "destination": "https://backend/token",
                        "timeout": "30000",
                        "interceptors": [
                            _item(
                                30,
                                "FIRST",
                                "Custom",
                                0,
                                content={"id": 31, "name": "My Custom", "script": "x"},
                                customInterceptorId=31,
                            ),
                        ],
                    },
                    {"id": 12, "method": "GET", "path": "/x", "interceptors": []},
                ],
            },
            {
                "id": 13,
                "name": "User",
                "interceptors": [_item(40, "FIRST", "Log", 0, content={"acceptedTerms": True})],
                "operations": [],
            },
        ],
    }
    older = {"id": 8862, "revisionNumber": 1, "interceptors": [], "resources": []}
    api = {
        "id": 400,
        "name": "Orchestrator Auth API",
        "version": "1.0.1",
        "basePath": "/orq-auth/v1",
        "description": "Auth API.",
        "apiType": "REST",
        "visibility": {
            "visibilityType": "GROUP",
            "owner": "paulo",
            "groupVisibility": {"name": "APIOps"},
            "users": [{"id": 6, "username": "isaac"}],
        },
        "apiResponsible": {"username": "paulo", "groupName": ""},
        "apiTags": [{"attributeName": "team", "tags": ["apiops"]}],
        "plans": [{"name": "Default"}],
        "environments": [
            {
                "id": 1,
                "name": "Default",
                "inboundUrl": "https://gw/",
                "revisionDeployed": {"revisionId": 8948, "revisionNumber": 4},
            },
            {"id": 7, "name": "DEV", "inboundUrl": "https://gw/dev/"},
        ],
        "revisions": [older, revision],
        "lastRevision": revision,
    }
    return api, revision


# --------------------------------------------------------------------------- revisão


def test_select_revision_by_number_by_id_and_default():
    api, revision = _wire()
    assert nav.select_revision(api, number=4) is revision
    assert nav.select_revision(api, revision_id=8862)["revisionNumber"] == 1
    assert nav.select_revision(api) is revision  # lastRevision
    assert nav.select_revision(api, number=9) is None
    assert nav.select_revision(api, revision_id=1) is None
    assert nav.available_revision_numbers(api) == [1, 4]


def test_select_revision_falls_back_to_highest_number_without_last_revision():
    api, _ = _wire()
    api.pop("lastRevision")
    assert nav.select_revision(api)["revisionNumber"] == 4


# --------------------------------------------------------------------------- nível 1


def test_api_summary_reads_identity_environments_and_revisions():
    api, _ = _wire()
    summary = nav.api_summary(api)

    assert summary["id"] == 400 and summary["basePath"] == "/orq-auth/v1"
    assert summary["visibility"] == {
        "type": "GROUP",
        "owner": "paulo",
        "groupName": "APIOps",
        "users": ["isaac"],
    }
    assert summary["lastRevisionNumber"] == 4
    assert summary["environments"][0]["deployedRevision"] == {"number": 4, "id": 8948}
    assert summary["environments"][1]["deployedRevision"] is None

    by_number = {r["number"]: r for r in summary["revisions"]}
    assert list(by_number) == [1, 4]  # ordenadas pelo número
    current = by_number[4]
    assert current["current"] is True and by_number[1]["current"] is False
    assert current["resources"] == 2 and current["operations"] == 2
    assert current["rootInterceptors"] == 3  # o THIRD não conta
    assert current["deployedIn"] == ["Default"]


# --------------------------------------------------------------------------- escopos


def test_scope_tree_composes_inheritance_per_scope():
    _, revision = _wire()
    tree = nav.scope_tree(revision)

    assert [i["id"] for i in tree.effective] == [1, 2, 3]
    assert tree.preserved == 1 and tree.inherits is None

    token, user = tree.children
    assert token.key == "token" and token.kind == "resource"
    assert token.own == [] and token.inherits is False
    assert token.removals == [
        {"targetId": 2, "type": "OAuth", "executionPoint": "FIRST", "resolved": True}
    ]
    assert [i["id"] for i in token.effective] == [1, 3]

    post, get = token.children
    assert post.key == "POST /oauth2/token" and post.resource_key == "token"
    assert [i["id"] for i in post.own] == [30]
    assert [i["id"] for i in post.effective] == [1, 3, 30]
    assert post.inherits is True
    assert [i["id"] for i in get.effective] == [1, 3]

    assert [i["id"] for i in user.effective] == [1, 2, 3, 40]


def test_unresolved_removal_is_flagged():
    _, revision = _wire()
    revision["resources"][0]["interceptors"][0]["parent"] = {"id": 999}
    token = nav.scope_tree(revision).children[0]
    assert token.removals[0]["resolved"] is False
    assert token.removals[0]["targetId"] == 999
    assert [i["id"] for i in token.effective] == [1, 2, 3]


@pytest.mark.parametrize(
    "resource,operation,expected",
    [
        (None, None, ["all", "token", "POST /oauth2/token", "GET /x", "user"]),
        ("Token", None, ["token", "POST /oauth2/token", "GET /x"]),
        ("token", None, ["token", "POST /oauth2/token", "GET /x"]),
        ("10", None, ["token", "POST /oauth2/token", "GET /x"]),
        ("tóken", None, ["token", "POST /oauth2/token", "GET /x"]),
        (None, "post /oauth2/token/", ["POST /oauth2/token"]),
        (None, "/x", ["GET /x"]),
        (None, "11", ["POST /oauth2/token"]),
        ("User", "/x", []),
        ("nada", None, []),
    ],
)
def test_select_scopes_by_resource_and_operation(resource, operation, expected):
    _, revision = _wire()
    scopes = nav.select_scopes(nav.scope_tree(revision), resource=resource, operation=operation)
    assert [s.key for s in scopes] == expected


# --------------------------------------------------------------------------- nível 2


def test_structure_counts_and_destinations():
    api, revision = _wire()
    document = nav.structure(api, revision)

    assert document["revision"]["number"] == 4
    assert document["revision"]["deployedIn"] == ["Default"]
    assert document["root"]["interceptors"] == {
        "own": 3,
        "removes": 0,
        "inherited": 0,
        "effective": 3,
        "preserved": 1,
    }
    token = document["resources"][0]
    assert token["slug"] == "token" and token["inherits"] is False
    assert token["interceptors"]["removes"] == 1 and token["interceptors"]["effective"] == 2
    post = token["operations"][0]
    assert post["destination"] == {"url": "https://backend/token", "timeout": "30000"}
    assert post["interceptors"] == {
        "own": 1,
        "removes": 0,
        "inherited": 2,
        "effective": 3,
        "preserved": 0,
    }
    assert document["totals"] == {"resources": 2, "operations": 2}


# --------------------------------------------------------------------------- nível 3


def test_scope_flows_own_vs_effective_and_content():
    api, revision = _wire()

    own = nav.scope_flows(api, revision, operation="POST /oauth2/token")
    assert own["mode"] == "own"
    (scope,) = own["scopes"]
    assert scope["resource"] == "token"
    assert "effective" not in scope
    (custom,) = scope["own"]["request"]
    assert custom["type"] == "Custom" and custom["customInterceptorId"] == 31
    assert custom["customName"] == "My Custom"
    assert custom["summary"] == '#31 "My Custom"'
    assert "content" not in custom  # o script só com --content/--item

    effective = nav.scope_flows(
        api, revision, operation="POST /oauth2/token", effective=True, include_content=True
    )
    (scope,) = effective["scopes"]
    assert [i["id"] for i in scope["effective"]["request"]] == [1, 30]
    assert [i["id"] for i in scope["effective"]["response"]] == [3]
    assert scope["effective"]["request"][0]["content"] == {"acceptedTerms": True}

    assert nav.scope_flows(api, revision, resource="nada") is None


def test_summary_is_one_line_and_truncated():
    item = _item(1, "FIRST", "Log", content={"regex": "a" * 200, "b": [1, 2]})
    described = nav.describe_item(item)
    assert "\n" not in described["summary"]
    assert len(described["summary"]) <= nav._SUMMARY_LIMIT
    assert described["summary"].startswith("regex=aaaa")
    assert nav.describe_item(_item(2, "FIRST", "Log", content=None))["summary"] == ""
    assert nav.decode_content("not json") == "not json"
    assert nav.decode_content("   ") is None


# --------------------------------------------------------------------------- nível 4


def test_find_interceptor_locates_scope_and_full_content():
    api, revision = _wire()
    scope, item = nav.find_interceptor(revision, 30)
    assert scope.kind == "operation" and scope.key == "POST /oauth2/token"

    document = nav.describe_interceptor(api, revision, scope, item)
    assert document["scope"] == {
        "scope": "POST /oauth2/token",
        "kind": "operation",
        "label": "POST /oauth2/token",
        "id": 11,
        "resource": "token",
    }
    data = document["interceptor"]
    assert data["content"]["script"] == "x" and data["governed"] is True
    assert "summary" not in data

    scope, tombstone = nav.find_interceptor(revision, 20)
    data = nav.describe_interceptor(api, revision, scope, tombstone)["interceptor"]
    assert data["status"] == "REMOVED" and data["parentId"] == 2

    assert nav.find_interceptor(revision, 999) is None


# --------------------------------------------------------------------------- fixture real


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_real_fixture_api_400_rev_4():
    data = json.loads((FIXTURES / "api-400-rev4.json").read_text(encoding="utf-8"))
    api = {**data["api"], "revisions": [data["revision"]], "lastRevision": data["revision"]}
    document = nav.structure(api, data["revision"])
    assert document["totals"] == {"resources": 2, "operations": 4}
    flows = nav.scope_flows(api, data["revision"], effective=True)
    assert len(flows["scopes"]) == 1 + 2 + 4
    for scope in flows["scopes"]:
        counts = scope["counts"]
        assert counts["effective"] == sum(len(v) for v in scope["effective"].values())
