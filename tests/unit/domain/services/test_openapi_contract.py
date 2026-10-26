"""OpenAPI contract: extraction, merge into the revision swagger and comparison."""

import datetime
from types import SimpleNamespace

from apiops_orchestrator.domain.services import openapi_contract as oc

OK = {"200": {"description": "Consulta realizada"}}


def _op(method, data, file=None):
    return SimpleNamespace(method=method, data=data, file_path=file or f"resources/t/{method.lower()}.yaml")


def _resource(data, *operations):
    return SimpleNamespace(data=data, operations=list(operations), file_path="resources/t/resource.yaml")


def _current():
    return {
        "openapi": "3.0.0",
        "info": {"title": "Tarefas", "version": "1.0.0", "contact": {"name": "Antigo"}},
        "servers": [{"url": "/tarefas/v1"}],
        "tags": [{"name": "Antiga"}],
        "x-interceptors": {"1": {"x-interceptor-type": "LOG"}},
        "components": {
            "schemas": {"Legado": {"type": "object"}},
            "parameters": {"Page": {"name": "page", "in": "query"}},
        },
        "paths": {
            "/tarefas/{id}": {
                "parameters": [{"name": "id", "in": "path", "required": True}],
                "get": {
                    "description": "Consulta uma tarefa",
                    "summary": "Antigo",
                    "operationId": "antigo",
                    "parameters": [{"name": "expand", "in": "query"}],
                    "responses": {"200": {"description": "OK"}, "404": {"description": "Sem tarefa"}},
                    "x-resource-name": "Tarefas",
                    "x-interceptors": {},
                },
            }
        },
    }


def _contract(**operation_fields):
    fields = {"parameters": [], "responses": OK, "summary": "Consulta uma tarefa"}
    fields.update(operation_fields)
    return oc.RepositoryContract(operations={("GET", "/tarefas/{id}"): fields})


# --- normalize_yaml ----------------------------------------------------------


def test_normalize_yaml_turns_numeric_keys_and_dates_into_text():
    value = {200: {"example": datetime.date(2024, 1, 31)}, "at": datetime.datetime(2024, 1, 31, 10, 0)}

    assert oc.normalize_yaml(value) == {
        "200": {"example": "2024-01-31"},
        "at": "2024-01-31T10:00:00",
    }


def test_normalize_yaml_keeps_booleans_as_values():
    assert oc.normalize_yaml({True: 1, "required": True}) == {True: 1, "required": True}


# --- merge_parameters --------------------------------------------------------


def test_operation_parameter_overrides_the_resource_one_with_same_name_and_location():
    resource = [
        {"name": "X-Correlation-Id", "in": "header", "required": False},
        {"name": "page", "in": "query"},
    ]
    operation = [{"name": "X-Correlation-Id", "in": "header", "required": True}]

    assert oc.merge_parameters(resource, operation) == [
        {"name": "page", "in": "query"},
        {"name": "X-Correlation-Id", "in": "header", "required": True},
    ]


def test_same_name_in_another_location_is_another_parameter():
    resource = [{"name": "id", "in": "header"}]
    operation = [{"name": "id", "in": "path", "required": True}]

    assert len(oc.merge_parameters(resource, operation)) == 2


# --- extract_contract --------------------------------------------------------


def test_extract_contract_keeps_only_the_contract_fields():
    basic_info = {"spec": {"name": "Tarefas", "contact": {"name": "Time"}, "apiTags": []}}
    components = {"schemas": {"Tarefa": {"type": "object"}}, "parameters": {"Ignorado": {}}}
    operation = _op(
        "GET",
        {
            "path": "/tarefas",
            "description": "Lista tarefas",
            "inherit": True,
            "interceptors_request": [{"type": "Log"}],
            "responses": {200: {"description": "Lista devolvida"}},
        },
    )

    contract = oc.extract_contract(
        basic_info=basic_info, components=components, resources=[_resource({"name": "T"}, operation)]
    )

    assert contract.root == {"contact": {"name": "Time"}}
    assert contract.components == {"schemas": {"Tarefa": {"type": "object"}}}
    assert contract.operations == {
        ("GET", "/tarefas"): {
            "responses": {"200": {"description": "Lista devolvida"}},
            "parameters": [],
            "summary": "Lista tarefas",
        }
    }


def test_declared_summary_is_kept():
    operation = _op("GET", {"path": "/t", "description": "Descrição longa", "summary": "Resumo", "responses": OK})

    contract = oc.extract_contract(basic_info={}, components={}, resources=[_resource({}, operation)])

    assert contract.operations[("GET", "/t")]["summary"] == "Resumo"


def test_resource_parameters_go_into_every_operation():
    shared = {"name": "X-Correlation-Id", "in": "header"}
    resource = _resource(
        {"name": "T", "parameters": [shared]},
        _op("GET", {"path": "/t", "responses": OK}),
        _op("POST", {"path": "/t", "responses": OK}),
    )

    contract = oc.extract_contract(basic_info={}, components={}, resources=[resource])

    assert contract.operations[("GET", "/t")]["parameters"] == [shared]
    assert contract.operations[("POST", "/t")]["parameters"] == [shared]


# --- apply_contract ----------------------------------------------------------


def test_apply_contract_replaces_only_the_governed_fields():
    contract = oc.RepositoryContract(
        root={"tags": [{"name": "Tarefas"}]},
        components={"schemas": {"Tarefa": {"type": "object"}}},
        operations={("GET", "/tarefas/{id}"): {"parameters": [], "responses": OK, "summary": "Consulta"}},
    )

    document = oc.apply_contract(_current(), contract)
    operation = document["paths"]["/tarefas/{id}"]["get"]

    assert document["tags"] == [{"name": "Tarefas"}]
    assert "contact" not in document["info"]
    assert document["components"]["schemas"] == {"Tarefa": {"type": "object"}}
    assert operation["responses"] == OK
    assert operation["summary"] == "Consulta"
    assert operation["parameters"] == []
    assert "operationId" not in operation


def test_apply_contract_keeps_what_the_manager_owns():
    document = oc.apply_contract(_current(), _contract())
    operation = document["paths"]["/tarefas/{id}"]["get"]

    assert document["servers"] == [{"url": "/tarefas/v1"}]
    assert document["info"]["title"] == "Tarefas"
    assert document["x-interceptors"] == {"1": {"x-interceptor-type": "LOG"}}
    assert document["components"]["parameters"] == {"Page": {"name": "page", "in": "query"}}
    assert operation["description"] == "Consulta uma tarefa"
    assert operation["x-resource-name"] == "Tarefas"
    assert operation["x-interceptors"] == {}


def test_apply_contract_clears_path_item_parameters():
    document = oc.apply_contract(_current(), _contract())

    assert "parameters" not in document["paths"]["/tarefas/{id}"]


def test_apply_contract_does_not_touch_the_current_document():
    current = _current()
    oc.apply_contract(current, _contract())

    assert current == _current()


def test_route_only_in_the_manager_is_left_alone():
    current = _current()
    current["paths"]["/saude"] = {"get": {"summary": "Saúde", "responses": OK}}

    document = oc.apply_contract(current, _contract())

    assert document["paths"]["/saude"] == {"get": {"summary": "Saúde", "responses": OK}}


def test_missing_routes_lists_repository_routes_absent_from_the_document():
    contract = oc.RepositoryContract(
        operations={("GET", "/tarefas/{id}"): {}, ("POST", "/tarefas"): {}}
    )

    assert oc.missing_routes(_current(), contract) == ["POST /tarefas"]


def test_is_swagger_2():
    assert oc.is_swagger_2({"swagger": "2.0", "paths": {}})
    assert not oc.is_swagger_2({"openapi": "3.0.0"})


# --- removed_items -----------------------------------------------------------


def test_removed_items_lists_what_the_repository_does_not_declare():
    items = oc.removed_items(_current(), _contract())

    assert items == [
        "info.contact",
        "tags",
        "components.schemas.Legado",
        "/tarefas/{id} · parameters do path",
        "GET /tarefas/{id} · operationId",
        "GET /tarefas/{id} · resposta 404",
        "GET /tarefas/{id} · parâmetro expand (query)",
    ]


def test_nothing_is_removed_when_the_repository_declares_it_all():
    contract = oc.RepositoryContract(
        root={"contact": {"name": "Time"}, "tags": [{"name": "T"}]},
        components={"schemas": {"Legado": {"type": "object"}}},
        operations={
            ("GET", "/tarefas/{id}"): {
                "operationId": "consultar",
                "parameters": [{"name": "expand", "in": "query"}],
                "responses": {"200": {"description": "Ok"}, "404": {"description": "Sem tarefa"}},
            }
        },
    )
    current = _current()
    del current["paths"]["/tarefas/{id}"]["parameters"]

    assert oc.removed_items(current, contract) == []


# --- comparison --------------------------------------------------------------


def test_openapi_defaults_and_required_order_do_not_make_a_difference():
    sent = {
        "components": {"schemas": {"T": {"required": ["b", "a"]}}},
        "paths": {"/t": {"get": {"parameters": [{"name": "page", "in": "query"}]}}},
    }
    written = {
        "components": {"schemas": {"T": {"required": ["a", "b"]}}},
        "paths": {
            "/t": {
                "get": {
                    "parameters": [
                        {"name": "page", "in": "query", "style": "form", "explode": True, "required": False}
                    ]
                }
            }
        },
    }

    assert oc.same_document(sent, written)
    assert oc.verify_contract(sent, written) == []


def test_header_defaults_do_not_make_a_difference():
    sent = {"components": {"headers": {"Total": {"schema": {"type": "integer"}}}}}
    written = {
        "components": {
            "headers": {"Total": {"schema": {"type": "integer"}, "style": "simple", "explode": False}}
        }
    }

    assert oc.same_document(sent, written)


def test_expanded_parameter_reference_is_the_same_parameter():
    page = {"name": "page", "in": "query"}
    sent = {
        "components": {"parameters": {"Page": page}},
        "paths": {"/t": {"get": {"parameters": [{"$ref": "#/components/parameters/Page"}]}}},
    }
    written = {
        "components": {"parameters": {"Page": page}},
        "paths": {"/t": {"get": {"parameters": [dict(page, style="form", explode=True)]}}},
    }

    assert oc.same_document(sent, written)


def test_verify_contract_reports_a_governed_field_written_differently():
    sent = {"paths": {"/t": {"get": {"responses": OK}}}}
    written = {"paths": {"/t": {"get": {"responses": {"200": {"description": "OK"}}}}}}

    [difference] = oc.verify_contract(sent, written)
    assert difference.startswith("GET /t · responses:")


def test_verify_contract_reports_a_route_that_was_not_written():
    sent = {"paths": {"/t": {"get": {"responses": OK}}}}

    assert oc.verify_contract(sent, {"paths": {}}) == [
        "GET /t: a rota enviada não está no swagger gravado"
    ]


def test_verify_contract_reports_a_changed_extension():
    sent = {"paths": {"/t": {"get": {"x-resource-name": "A"}}}}
    written = {"paths": {"/t": {"get": {"x-resource-name": "B"}}}}

    assert oc.verify_contract(sent, written) == [
        "a extensão `paths./t.get.x-resource-name` mudou ao gravar"
    ]


def test_renumbered_interceptor_keys_are_not_a_difference():
    item = {"x-interceptor-type": "LOG", "x-interceptor-position": 1}
    sent = {"x-interceptors": {"1": item}}
    written = {"x-interceptors": {"7": item}}

    assert oc.verify_contract(sent, written) == []
