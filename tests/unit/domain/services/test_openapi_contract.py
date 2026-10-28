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


def test_empty_root_security_is_absent_and_an_empty_operation_security_is_kept():
    """The Manager keeps `security: []` of an operation (public route) and drops the root one."""
    operation = _op("GET", {"path": "/health", "security": [], "responses": OK})

    contract = oc.extract_contract(
        basic_info={"spec": {"security": [], "tags": [{"name": "Saude"}]}},
        components={},
        resources=[_resource({}, operation)],
    )
    document = oc.apply_contract(_current(), contract)

    assert contract.root == {"tags": [{"name": "Saude"}]}
    assert "security" not in document
    assert contract.operations[("GET", "/health")]["security"] == []


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


def test_parameter_keeps_the_extensions_of_the_manager_one_with_same_name_and_location():
    current = _current()
    current["paths"]["/tarefas/{id}"]["get"]["parameters"] = [
        {"name": "expand", "in": "query", "description": "Antiga", "x-example": "comentarios"}
    ]
    declared = {"name": "expand", "in": "query", "description": "Nova", "schema": {"type": "string"}}

    document = oc.apply_contract(current, _contract(parameters=[declared]))

    assert document["paths"]["/tarefas/{id}"]["get"]["parameters"] == [
        {
            "name": "expand",
            "in": "query",
            "description": "Nova",
            "schema": {"type": "string"},
            "x-example": "comentarios",
        }
    ]


def test_path_item_parameter_extensions_are_kept_in_the_operation():
    current = _current()
    current["paths"]["/tarefas/{id}"]["parameters"][0]["x-example"] = "42"

    document = oc.apply_contract(
        current, _contract(parameters=[{"name": "id", "in": "path", "required": True}])
    )

    assert document["paths"]["/tarefas/{id}"]["get"]["parameters"] == [
        {"name": "id", "in": "path", "required": True, "x-example": "42"}
    ]


def test_extensions_do_not_go_to_a_parameter_in_another_location():
    current = _current()
    current["paths"]["/tarefas/{id}"]["get"]["parameters"] = [
        {"name": "expand", "in": "query", "x-example": "comentarios"}
    ]

    document = oc.apply_contract(current, _contract(parameters=[{"name": "expand", "in": "header"}]))

    assert document["paths"]["/tarefas/{id}"]["get"]["parameters"] == [{"name": "expand", "in": "header"}]


def test_kept_parameter_extensions_make_the_second_write_unnecessary():
    current = _current()
    current["paths"]["/tarefas/{id}"]["get"]["parameters"] = [
        {"name": "expand", "in": "query", "x-example": "comentarios"}
    ]
    contract = _contract(parameters=[{"name": "expand", "in": "query"}])

    written = oc.apply_contract(current, contract)

    assert oc.same_document(written, oc.apply_contract(written, contract))


def test_method_outside_the_repository_leaves_the_path_that_keeps_another():
    current = _current()
    current["paths"]["/tarefas/{id}"]["delete"] = {"summary": "Remove", "responses": OK, "x-interceptors": {}}

    document = oc.apply_contract(current, _contract())

    assert "delete" not in document["paths"]["/tarefas/{id}"]
    assert document["paths"]["/tarefas/{id}"]["get"]["summary"] == "Consulta uma tarefa"


def test_path_left_without_operations_is_dropped():
    current = _current()
    current["paths"]["/saude"] = {"get": {"summary": "Saúde", "responses": OK}}

    document = oc.apply_contract(current, _contract())

    assert "/saude" not in document["paths"]
    assert "/tarefas/{id}" in document["paths"]


def test_a_route_outside_the_repository_alone_makes_the_write_necessary():
    written = oc.apply_contract(_current(), _contract())
    assert oc.same_document(oc.apply_contract(written, _contract()), written)

    written["paths"]["/tarefas/{id}"]["delete"] = {"summary": "Remove", "responses": OK}

    assert not oc.same_document(oc.apply_contract(written, _contract()), written)


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
        "GET /tarefas/{id} · parâmetro id (path)",
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


def test_path_item_parameter_declared_in_the_route_does_not_leave():
    contract = _contract(parameters=[{"name": "id", "in": "path", "required": True}, {"name": "expand", "in": "query"}])

    items = oc.removed_items(_current(), contract)

    assert all("parâmetro id" not in item for item in items)


def test_path_item_parameter_of_a_route_only_in_the_manager_is_left_to_the_flow_warning():
    current = _current()
    current["paths"]["/tarefas/{id}"]["delete"] = {"responses": {"204": {"description": "Removida"}}}
    contract = _contract(parameters=[{"name": "id", "in": "path", "required": True}, {"name": "expand", "in": "query"}])

    items = oc.removed_items(current, contract)

    assert all("DELETE" not in item for item in items)


def test_parameter_in_the_path_item_and_in_the_operation_is_listed_once():
    current = _current()
    current["paths"]["/tarefas/{id}"]["get"]["parameters"].append({"name": "id", "in": "path", "required": True})

    items = oc.removed_items(current, _contract())

    assert items.count("GET /tarefas/{id} · parâmetro id (path)") == 1


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


def test_same_documentation_ignores_the_flow_extensions_only():
    before = _current()
    after = _current()
    after["x-interceptors"] = {"9": {"x-interceptor-type": "LOG"}}
    after["paths"]["/tarefas/{id}"]["get"]["x-destination"] = "https://outro"

    assert oc.same_documentation(before, after)

    after["paths"]["/tarefas/{id}"]["get"]["description"] = "Consulta uma tarefa pelo id"
    assert not oc.same_documentation(before, after)


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
