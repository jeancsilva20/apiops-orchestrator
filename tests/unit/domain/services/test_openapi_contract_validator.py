"""Swagger validate: local checks of the declared OpenAPI contract."""

import datetime
from types import SimpleNamespace

import pytest

from apiops_orchestrator.domain.services.openapi_contract_validator import validate

OK = {"200": {"description": "Consulta realizada"}}
GOOD_SUMMARY = "Consulta de tarefas"
GOOD_DESCRIPTION = "Consulta as tarefas abertas do time"


def _op(method, path, **fields):
    data = {"path": path, "description": GOOD_DESCRIPTION, "summary": GOOD_SUMMARY, "responses": OK}
    data.update(fields)
    file = f"resources/t/{method.lower()}_{path.strip('/').replace('/', '_')}.yaml"
    return SimpleNamespace(method=method, data=data, file_path=file)


def _resource(*operations, **data):
    return SimpleNamespace(
        data=dict({"name": "Tarefas"}, **data),
        operations=list(operations),
        file_path="resources/t/resource.yaml",
    )


def _run(*resources, components=None, spec=None, ignored=()):
    basic_info = {"apiVersion": "api-management.sensedia.com/v1", "spec": dict({"id": 1}, **(spec or {}))}
    return validate(
        basic_info=basic_info,
        components=components or {},
        resources=list(resources) or [_resource(_op("GET", "/tarefas"))],
        ignored=ignored,
    )


def _errors(*resources, **kwargs):
    return _run(*resources, **kwargs).errors


def _single_error(*resources, **kwargs):
    [error] = _errors(*resources, **kwargs)
    return error


def test_a_well_described_contract_has_no_errors_nor_warnings():
    components = {
        "schemas": {
            "Tarefa": {
                "type": "object",
                "description": "Tarefa do serviço de letras",
                "properties": {"id": {"type": "string", "description": "Identificador da tarefa"}},
            }
        },
        "securitySchemes": {"Token": {"type": "http", "scheme": "bearer"}},
    }
    operation = _op(
        "GET",
        "/tarefas/{id}",
        parameters=[
            {"name": "id", "in": "path", "required": True, "description": "Id da tarefa",
             "schema": {"type": "string"}}
        ],
        responses={
            "200": {
                "description": "Tarefa encontrada",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Tarefa"}}},
            }
        },
        security=[{"Token": []}],
    )

    result = _run(_resource(operation), components=components, spec={"security": [{"Token": []}]})

    assert result.errors == []
    assert result.warnings == []


# --- 1: outside the model ----------------------------------------------------


def test_extension_in_an_operation_file_is_an_error():
    error = _single_error(_resource(_op("GET", "/tarefas", **{"x-rate": 1})))
    assert "em `x-rate`" in error and "extensões `x-*`" in error


def test_extension_inside_a_contract_field_is_an_error():
    responses = {"200": {"description": "Consulta realizada", "x-cache": True}}
    error = _single_error(_resource(_op("GET", "/tarefas", responses=responses)))
    assert "responses.200.x-cache" in error


def test_property_named_like_an_extension_is_not_an_error():
    components = {
        "schemas": {
            "T": {
                "type": "object",
                "description": "Objeto com cabeçalho",
                "properties": {"x-request-id": {"type": "string", "description": "Rastreamento"}},
            }
        }
    }
    assert _errors(components=components) == []


@pytest.mark.parametrize("field", ["servers", "info"])
def test_servers_and_info_are_not_declared_in_the_repository(field):
    error = _single_error(spec={field: {}})
    assert f"spec.{field}" in error and "vem do Manager" in error


def test_reusable_parameters_section_is_an_error():
    error = _single_error(components={"parameters": {"Page": {"name": "page", "in": "query"}}})
    assert "escreva cada um por extenso" in error


@pytest.mark.parametrize("section", ["links", "callbacks", "outra"])
def test_section_outside_the_model_is_an_error(section):
    error = _single_error(components={section: {}})
    assert "seção fora do modelo" in error


def test_components_yml_must_be_renamed():
    error = _single_error(ignored=["components.yml"])
    assert "`components.yaml`" in error


# --- 2 to 5: references ------------------------------------------------------


def test_reference_to_a_missing_schema():
    content = {"application/json": {"schema": {"$ref": "#/components/schemas/Tarefa"}}}
    responses = {"200": {"description": "Consulta realizada", "content": content}}
    error = _single_error(_resource(_op("GET", "/tarefas", responses=responses)))
    assert "`#/components/schemas/Tarefa` não existe" in error
    assert "get_tarefas.yaml" in error


def test_reference_to_the_wrong_section():
    components = {"requestBodies": {"Nova": {"content": {}}}}
    responses = {"200": {"description": "Consulta realizada"}, "404": {"$ref": "#/components/requestBodies/Nova"}}
    error = _single_error(_resource(_op("GET", "/tarefas", responses=responses)), components=components)
    assert "só cabe referência a `#/components/responses/`" in error


@pytest.mark.parametrize("ref", ["./schemas/tarefa.yaml", "https://x/tarefa.json"])
def test_external_reference_is_an_error(ref):
    content = {"application/json": {"schema": {"$ref": ref}}}
    responses = {"200": {"description": "Consulta realizada", "content": content}}
    error = _single_error(_resource(_op("GET", "/tarefas", responses=responses)))
    assert "não é aceito" in error


def test_swagger_2_reference_points_to_the_openapi_3_section():
    content = {"application/json": {"schema": {"$ref": "#/definitions/Tarefa"}}}
    responses = {"200": {"description": "Consulta realizada", "content": content}}
    error = _single_error(_resource(_op("GET", "/tarefas", responses=responses)))
    assert "formato do Swagger 2.0" in error and "#/components/schemas/" in error


def test_cycle_between_responses_is_an_error():
    components = {
        "responses": {
            "A": {"$ref": "#/components/responses/B"},
            "B": {"$ref": "#/components/responses/A"},
        }
    }
    errors = _errors(components=components)
    assert any("ciclo" in e for e in errors)


def test_recursive_schema_is_allowed():
    components = {
        "schemas": {
            "No": {
                "type": "object",
                "description": "Nó de uma árvore",
                "properties": {"filhos": {"type": "array", "items": {"$ref": "#/components/schemas/No"}}},
            }
        }
    }
    assert _errors(components=components) == []


def test_security_must_name_a_declared_scheme():
    error = _single_error(_resource(_op("GET", "/tarefas", security=[{"Token": []}])))
    assert "`Token` não está em `securitySchemes`" in error


def test_public_route_has_an_empty_security():
    assert _errors(_resource(_op("GET", "/saude", security=[]))) == []


# --- 7 to 10: parameters -----------------------------------------------------


PATH_ID = {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}


def test_resource_path_parameter_must_exist_in_every_route():
    resource = _resource(_op("GET", "/tarefas"), _op("GET", "/tarefas/{id}"), parameters=[PATH_ID])
    error = _single_error(resource)
    assert "não existe em `/tarefas`" in error and "resource.yaml" in error


def test_resource_path_parameter_valid_for_every_route():
    resource = _resource(_op("GET", "/tarefas/{id}"), _op("PUT", "/tarefas/{id}"), parameters=[PATH_ID])
    assert _errors(resource) == []


def test_template_parameter_must_be_declared():
    error = _single_error(_resource(_op("GET", "/tarefas/{id}")))
    assert "tem `{id}`" in error


def test_operation_path_parameter_must_be_in_the_template():
    error = _single_error(_resource(_op("GET", "/tarefas", parameters=[PATH_ID])))
    assert "`id` não existe na rota `/tarefas`" in error


def test_path_parameter_must_be_required():
    parameter = dict(PATH_ID, required=False)
    error = _single_error(_resource(_op("GET", "/tarefas/{id}", parameters=[parameter])))
    assert "`required: true`" in error


def test_repeated_parameter_in_the_same_file():
    page = {"name": "page", "in": "query"}
    error = _single_error(_resource(_op("GET", "/tarefas", parameters=[page, page])))
    assert "repetido" in error


def test_parameter_reference_is_an_error():
    parameters = [{"$ref": "#/components/parameters/Page"}]
    error = _single_error(_resource(_op("GET", "/tarefas", parameters=parameters)))
    assert "escreva-o por extenso" in error


def test_parameter_without_location_is_an_error():
    error = _single_error(_resource(_op("GET", "/tarefas", parameters=[{"name": "page"}])))
    assert "`name` e de `in`" in error


# --- 11 to 13, 16: operations ------------------------------------------------


def test_operation_id_must_be_unique():
    resource = _resource(
        _op("GET", "/tarefas", operationId="listar"), _op("POST", "/tarefas", operationId="listar")
    )
    error = _single_error(resource)
    assert "`listar` se repete" in error


def test_request_body_only_on_methods_with_body():
    body = {"content": {"application/json": {"schema": {"type": "object"}}}}
    error = _single_error(_resource(_op("GET", "/tarefas", requestBody=body)))
    assert "só vale em POST, PUT e PATCH; esta rota é GET" in error


def test_response_needs_a_description():
    error = _single_error(_resource(_op("GET", "/tarefas", responses={"200": {}})))
    assert "precisa de `description`" in error


@pytest.mark.parametrize("status", ["20", "600", "2xx"])
def test_invalid_status(status):
    responses = {status: {"description": "Consulta realizada"}}
    error = _single_error(_resource(_op("GET", "/tarefas", responses=responses)))
    assert "status inválido" in error


@pytest.mark.parametrize("status", [200, "2XX", "default"])
def test_valid_status(status):
    responses = {status: {"description": "Consulta realizada"}}
    assert _errors(_resource(_op("GET", "/tarefas", responses=responses))) == []


@pytest.mark.parametrize("responses", [None, {}])
def test_operation_must_declare_responses(responses):
    operation = _op("GET", "/tarefas")
    operation.data.pop("responses")
    if responses is not None:
        operation.data["responses"] = responses
    error = _single_error(_resource(operation))
    assert "não declara `responses`" in error


# --- 14 and 15: types and examples -------------------------------------------


@pytest.mark.parametrize(
    "schema,example,problem",
    [
        ({"type": "integer"}, "primeira", "não é do tipo `integer`"),
        ({"type": "string", "enum": ["A", "B"]}, "C", "não está no `enum`"),
        ({"type": "string", "format": "uuid"}, "123", "formato `uuid`"),
        ({"type": "integer", "format": "int32"}, 2**40, "não cabe em `int32`"),
    ],
)
def test_parameter_example_must_match_the_schema(schema, example, problem):
    parameter = {"name": "p", "in": "query", "schema": schema, "example": example}
    error = _single_error(_resource(_op("GET", "/tarefas", parameters=[parameter])))
    assert problem in error


def test_yaml_date_example_matches_a_date_format():
    parameter = {
        "name": "desde",
        "in": "query",
        "schema": {"type": "string", "format": "date"},
        "example": datetime.date(2024, 1, 31),
    }
    assert _errors(_resource(_op("GET", "/tarefas", parameters=[parameter]))) == []


def test_example_is_checked_against_a_referenced_schema():
    components = {"schemas": {"Id": {"type": "integer", "description": "Identificador"}}}
    content = {"application/json": {"schema": {"$ref": "#/components/schemas/Id"}, "example": "um"}}
    responses = {"200": {"description": "Consulta realizada", "content": content}}
    errors = _errors(_resource(_op("GET", "/tarefas", responses=responses)), components=components)
    assert any("não é do tipo `integer`" in e for e in errors)


def test_enum_values_must_match_the_type():
    components = {
        "schemas": {
            "T": {
                "type": "object",
                "description": "Objeto de teste",
                "properties": {"n": {"type": "integer", "enum": [1, "dois"], "description": "Número"}},
            }
        }
    }
    error = _single_error(components=components)
    assert "'dois'" in error and "`integer`" in error


# --- completeness warnings ---------------------------------------------------


def test_short_descriptions_become_a_single_warning():
    components = {"schemas": {"Tarefa": {"type": "object", "properties": {"id": {"type": "string"}}}}}
    operation = _op(
        "GET",
        "/tarefas",
        summary="",
        description="",
        responses={"200": {"description": "OK"}},
        parameters=[{"name": "page", "in": "query"}],
    )

    result = _run(_resource(operation), components=components)

    assert result.errors == []
    [warning] = result.warnings
    for item in (
        "get_tarefas.yaml · summary (vazia)",
        "get_tarefas.yaml · description (vazia)",
        "get_tarefas.yaml · responses.200 (2 caracteres)",
        "get_tarefas.yaml · parameters.page (query) (vazia)",
        "components.yaml · schemas.Tarefa (vazia)",
        "components.yaml · schemas.Tarefa.properties.id (vazia)",
    ):
        assert item in warning


def test_warning_shows_only_the_rules_that_apply_with_their_minimum():
    operation = _op(
        "GET",
        "/tarefas",
        summary="Lista as tarefas",
        responses={"200": {"description": "OK"}, "404": {"description": "Nada"}},
    )

    [warning] = _run(_resource(operation)).warnings

    assert warning.startswith("Estas descrições têm menos caracteres que o mínimo")
    assert "Descrição de resposta: mínimo de 5 caracteres" in warning
    assert "get_tarefas.yaml · responses.200 (2 caracteres)" in warning
    assert "get_tarefas.yaml · responses.404 (4 caracteres)" in warning
    for other in ("`summary`", "parâmetro", "schema", "propriedade"):
        assert other not in warning


def test_summary_falls_back_to_the_description():
    operation = _op("GET", "/tarefas", summary=None, description="Lista as tarefas abertas")
    operation.data.pop("summary")
    assert _run(_resource(operation)).warnings == []


def test_short_summary_taken_from_the_description_says_so():
    without_summary = _op("GET", "/saude", description="OK")
    without_summary.data.pop("summary")
    short_summary = _op("GET", "/tarefas", summary="Abc")

    [warning] = _run(_resource(without_summary, short_summary)).warnings

    assert "get_saude.yaml · summary (2 caracteres, da description)" in warning
    assert "get_tarefas.yaml · summary (3 caracteres)" in warning
    assert "Rota sem `summary` usa a `description` no lugar" in warning


def test_route_description_needs_ten_characters_and_empty_counts():
    short = _op("GET", "/saude", description="ok")
    empty = _op("GET", "/tarefas", description="")
    long_enough = _op("GET", "/letras", description="Consulta letras")

    [warning] = _run(_resource(short, empty, long_enough)).warnings

    assert "Descrição da rota: mínimo de 10 caracteres" in warning
    assert "get_saude.yaml · description (2 caracteres)" in warning
    assert "get_tarefas.yaml · description (vazia)" in warning
    assert "get_letras.yaml" not in warning


def test_short_declared_summary_has_no_description_note():
    [warning] = _run(_resource(_op("GET", "/tarefas", summary="Abc"))).warnings

    assert "get_tarefas.yaml · summary (3 caracteres)" in warning
    assert "da description" not in warning and "usa a `description`" not in warning


def test_enum_schema_warning_says_what_it_is_and_what_to_do():
    components = {"schemas": {"Status": {"type": "string", "enum": ["A"], "description": "Status da tarefa"}}}
    [warning] = _run(components=components).warnings
    assert warning.startswith("Estes schemas não têm `properties`, que o completeness cobra")
    assert (
        "Tipo simples ou lista: declare-o direto na propriedade que o usa, no lugar do `$ref`, e apague o schema"
        in warning
    )
    assert "components.yaml · schemas.Status (texto com `enum`)" in warning
    assert "Objeto" not in warning


def test_schemas_without_properties_are_grouped_by_kind():
    described = "Schema de teste do laboratório"
    components = {
        "schemas": {
            "Codigo": {"type": "integer", "description": described},
            "Vazio": {"type": "object", "description": described},
            "Lista": {"type": "array", "items": {"type": "string"}, "description": described},
            "Composto": {"allOf": [{"$ref": "#/components/schemas/Vazio"}], "description": described},
            "Mapa": {"type": "object", "additionalProperties": {"type": "string"}, "description": described},
        }
    }

    [warning] = _run(components=components).warnings

    simple, obj, composite = warning.split("\n\n")[1:]
    assert simple.startswith("Tipo simples ou lista: declare-o direto na propriedade que o usa")
    assert "schemas.Codigo (número inteiro)" in simple and "schemas.Lista (lista)" in simple
    assert obj == "Objeto: declare as propriedades, com tipo e descrição\n  - components.yaml · schemas.Vazio"
    assert composite.startswith("Composição ou mapa: acrescente `properties: {}` ao schema")
    assert "schemas.Composto (composição)" in composite and "schemas.Mapa (mapa)" in composite


def test_short_descriptions_and_schemas_without_properties_are_two_warnings():
    components = {"schemas": {"Status": {"type": "string", "enum": ["A"], "description": "Curto"}}}

    descriptions, schemas = _run(components=components).warnings

    assert descriptions.startswith("Estas descrições têm menos caracteres que o mínimo")
    assert schemas.startswith("Estes schemas não têm `properties`")
