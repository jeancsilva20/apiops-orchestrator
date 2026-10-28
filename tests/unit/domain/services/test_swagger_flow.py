"""Revision flow as swagger extensions, and the swagger aligned to it."""

import copy

from apiops_orchestrator.domain.services import swagger_flow as sf


def _item(item_id, position, attribute, status="REFERENCE", parent=None, flow_type="Header", **extra):
    item = {
        "id": item_id,
        "position": position,
        "type": flow_type,
        "content": '{"headerList": [{"name": "X-%s"}]}' % attribute,
        "executionPoint": "FIRST",
        "status": status,
        "parent": {"id": parent} if parent is not None else None,
        "customInterceptorId": None,
    }
    item.update(extra)
    return item


def _revision():
    """Root R1; resource Quebra drops R1 and adds C1; GET /c3 drops C1 and adds C3; GET /s1 in Heranca inherits."""
    return {
        "id": 9554,
        "destination": "https://httpbin.org/anything",
        "apiBroken": False,
        "interceptors": [_item(10, 0, "R1")],
        "resources": [
            {
                "name": "Quebra",
                "description": None,
                "destination": None,
                "timeout": None,
                "apiBroken": False,
                "interceptors": [_item(20, 0, "R1", "REMOVED", parent=10), _item(21, 1, "C1")],
                "operations": [
                    {
                        "method": "GET",
                        "path": "/c3",
                        "description": "Consulta c3",
                        "destination": None,
                        "timeout": None,
                        "apiBroken": False,
                        "interceptors": [_item(30, 1, "C1", "REMOVED", parent=21), _item(31, 1, "C3")],
                    }
                ],
            },
            {
                "name": "Heranca",
                "description": "Rotas que herdam",
                "destination": None,
                "timeout": "30",
                "apiBroken": False,
                "interceptors": [],
                "operations": [
                    {
                        "method": "GET",
                        "path": "/s1",
                        "description": "Consulta s1",
                        "destination": "https://destino",
                        "timeout": None,
                        "apiBroken": False,
                        "interceptors": [],
                    }
                ],
            },
        ],
    }


def _x(position, attribute, status="REFERENCE", parent=None, swagger_type="HEADER"):
    item = {
        "x-interceptor-position": position,
        "x-interceptor-type": swagger_type,
        "x-interceptor-content": '{"headerList": [{"name": "X-%s"}]}' % attribute,
        "x-interceptor-execution-point": "FIRST",
        "x-interceptor-status": status,
    }
    if parent is not None:
        item["x-interceptor-parent-id"] = parent
    return item


def _swagger():
    """What the Manager exports for `_revision()`, with its own local keys."""
    return {
        "openapi": "3.0.0",
        "info": {"title": "Lab", "version": "1.0.0"},
        "servers": [{"url": "/lab"}],
        "x-life-cycle": "Stage One",
        "x-destination": "https://httpbin.org/anything",
        "x-api-broken": False,
        "x-interceptors": {"7": _x(0, "R1")},
        "x-resources": {
            "Quebra": {"x-api-broken": False, "x-interceptors": {"40": _x(0, "R1", "REMOVED", 7), "41": _x(1, "C1")}},
            "Heranca": {"x-resource-description": "Rotas que herdam", "x-timeout": 30, "x-api-broken": False,
                        "x-interceptors": {}},
        },
        "paths": {
            "/c3": {
                "get": {
                    "summary": "Consulta c3",
                    "description": "Consulta c3",
                    "responses": {"200": {"description": "OK"}},
                    "x-resource-name": "Quebra",
                    "x-api-broken": False,
                    "x-interceptors": {"50": _x(1, "C3"), "51": _x(1, "C1", "REMOVED", 41)},
                }
            },
            "/s1": {
                "get": {
                    "summary": "Consulta s1",
                    "description": "Consulta s1",
                    "responses": {"200": {"description": "OK"}},
                    "x-resource-name": "Heranca",
                    "x-destination": "https://destino",
                    "x-api-broken": False,
                    "x-interceptors": {},
                }
            },
        },
    }


# --- swagger_type ----------------------------------------------------------------


def test_swagger_type_is_the_upper_case_name_with_underscores():
    assert sf.swagger_type("Rate limit") == "RATE_LIMIT"
    assert sf.swagger_type("HTTP method") == "HTTP_METHOD"


def test_swagger_type_follows_the_measured_exceptions():
    assert sf.swagger_type("Digital signature") == "APIKEY_DIGITAL_SIGNATURE"
    assert sf.swagger_type("GZip pack") == "GZIPPACK"
    assert sf.swagger_type("Java") == "CUSTOM_JAVA"
    assert sf.swagger_type("XSLT") == "XSL_TRANSFORMATION"


# --- flow_extensions -------------------------------------------------------------


def test_keys_are_numbered_root_first_and_markers_point_to_the_parent_key():
    flow = sf.flow_extensions(_revision())

    assert list(flow.root["x-interceptors"]) == ["1"]
    quebra = flow.resources["Quebra"]["x-interceptors"]
    assert quebra["2"]["x-interceptor-parent-id"] == 1
    c3 = flow.operations[("GET", "/c3")]["x-interceptors"]
    removed = next(i for i in c3.values() if i["x-interceptor-status"] == "REMOVED")
    assert removed["x-interceptor-parent-id"] == 3  # C1 of the resource
    assert flow.operations[("GET", "/c3")]["x-resource-name"] == "Quebra"


def test_item_fields_are_converted():
    revision = _revision()
    revision["interceptors"] = [
        _item(10, 0, "R1", flow_type="Custom", customInterceptorId=75),
        _item(11, 1, "R2", flow_type="Mock", status=None),
    ]
    revision["resources"][0]["interceptors"] = []
    revision["resources"][0]["operations"][0]["interceptors"] = []

    custom, mock = sf.flow_extensions(revision).root["x-interceptors"].values()

    assert custom["x-interceptor-type"] == "CUSTOM"
    assert custom["x-interceptor-custom-interceptor-id"] == 75
    assert mock["x-interceptor-type"] == "MOCK"
    assert "x-interceptor-status" not in mock


def test_numeric_timeout_becomes_a_number_and_a_named_one_stays_text():
    revision = _revision()
    revision["resources"][0]["operations"][0]["timeout"] = "timeout_api"

    flow = sf.flow_extensions(revision)

    assert flow.resources["Heranca"]["x-timeout"] == 30
    assert flow.operations[("GET", "/c3")]["x-timeout"] == "timeout_api"


# --- differences -----------------------------------------------------------------


def test_swagger_in_sync_has_no_difference_whatever_its_keys():
    assert sf.differences(_swagger(), _revision()) == []


def test_absent_null_and_default_extensions_are_the_same():
    swagger = _swagger()
    del swagger["x-resources"]["Quebra"]["x-api-broken"]
    swagger["paths"]["/s1"]["get"]["x-timeout"] = None
    del swagger["paths"]["/s1"]["get"]["x-interceptors"]

    assert sf.differences(swagger, _revision()) == []


def test_route_missing_from_the_swagger_is_created():
    swagger = _swagger()
    del swagger["paths"]["/s1"]

    assert sf.differences(swagger, _revision()) == ["GET /s1: criada"]


def test_route_and_resource_the_flow_no_longer_has_are_removed():
    swagger = _swagger()
    swagger["paths"]["/c3"]["post"] = {"x-resource-name": "Velho", "x-interceptors": {}}
    swagger["x-resources"]["Velho"] = {"x-interceptors": {}}

    assert sf.differences(swagger, _revision()) == ["recurso Velho: tirado", "POST /c3: tirada"]


def test_marker_pointing_to_another_parent_is_a_difference():
    swagger = _swagger()
    swagger["paths"]["/c3"]["get"]["x-interceptors"]["51"]["x-interceptor-parent-id"] = 7

    assert sf.differences(swagger, _revision()) == ["GET /c3: interceptors"]


def test_marker_pointing_to_a_missing_key_is_a_difference():
    swagger = _swagger()
    swagger["paths"]["/c3"]["get"]["x-interceptors"]["51"]["x-interceptor-parent-id"] = 22

    assert sf.differences(swagger, _revision()) == ["GET /c3: interceptors"]


def test_stale_destination_description_and_items_are_differences():
    swagger = _swagger()
    swagger["x-interceptors"]["7"]["x-interceptor-content"] = "{}"
    swagger["x-resources"]["Heranca"]["x-resource-description"] = "Antiga"
    swagger["paths"]["/s1"]["get"]["x-destination"] = "https://antigo"
    swagger["paths"]["/s1"]["get"]["description"] = "Antiga"

    assert sf.differences(swagger, _revision()) == [
        "raiz: interceptors",
        "recurso Quebra: interceptors",
        "recurso Heranca: descrição",
        "GET /s1: descrição, destino",
    ]


# --- align -----------------------------------------------------------------------


def test_aligned_swagger_describes_the_flow_and_keeps_the_rest():
    swagger = _swagger()
    del swagger["paths"]["/s1"]
    swagger["paths"]["/c3"]["post"] = {"x-resource-name": "Quebra", "x-interceptors": {}}
    swagger["paths"]["/c3"]["get"]["x-interceptors"]["51"]["x-interceptor-parent-id"] = 22
    swagger["x-resources"]["Quebra"]["x-outra"] = "fica"

    aligned = sf.align(swagger, _revision())

    assert sf.differences(aligned, _revision()) == []
    assert "post" not in aligned["paths"]["/c3"]
    assert aligned["paths"]["/c3"]["get"]["summary"] == "Consulta c3"
    assert aligned["paths"]["/s1"]["get"] == {
        "description": "Consulta s1",
        "x-resource-name": "Heranca",
        "x-destination": "https://destino",
        "x-api-broken": False,
        "x-interceptors": {},
    }
    assert aligned["x-resources"]["Quebra"]["x-outra"] == "fica"
    assert (aligned["servers"], aligned["x-life-cycle"]) == ([{"url": "/lab"}], "Stage One")


def test_path_left_without_operations_is_dropped():
    swagger = _swagger()
    swagger["paths"]["/velho"] = {"get": {"x-resource-name": "Quebra"}}

    assert "/velho" not in sf.align(swagger, _revision())["paths"]


def test_align_does_not_touch_the_document_it_gets():
    swagger = _swagger()
    before = copy.deepcopy(swagger)

    sf.align(swagger, _revision())

    assert swagger == before


# --- unsupported -----------------------------------------------------------------


def test_flow_fields_without_extension_block_the_alignment():
    revision = _revision()
    revision["resources"][0]["connector"] = {"id": 3}
    revision["resources"][1]["operations"][0]["certificateId"] = 12
    revision["resources"][1]["operations"][0]["async"] = False

    assert sf.unsupported(revision) == ["recurso Quebra: connector", "GET /s1: certificateId"]


def test_marker_whose_parent_is_outside_the_revision_blocks_the_alignment():
    revision = _revision()
    revision["resources"][0]["interceptors"][0]["parent"] = {"id": 999}

    assert sf.unsupported(revision) == ["interceptor Header com o pai fora da revisão"]


def test_plain_flow_has_nothing_unsupported():
    assert sf.unsupported(_revision()) == []
