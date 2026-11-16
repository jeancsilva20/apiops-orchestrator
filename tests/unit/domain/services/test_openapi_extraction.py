"""Swagger → contrato do repositório (o sentido que o `sen sync` usa)."""

from apiops_orchestrator.domain.services.openapi_contract import (
    document_format,
    is_openapi_3,
    swagger_components,
    swagger_operations_contract,
    swagger_root_contract,
    without_extensions,
)

SWAGGER = {
    "openapi": "3.0.1",
    "info": {"title": "Lab", "contact": {"name": "Time", "x-slack": "#lab"}},
    "tags": [{"name": "Tarefas", "x-order": 1}],
    "security": [{"Token": []}],
    "x-sensedia": True,
    "components": {
        "schemas": {"Tarefa": {"type": "object", "properties": {"x-id": {"type": "string"}}}},
        "parameters": {"Pagina": {"name": "page", "in": "query", "schema": {"type": "integer"}}},
        "securitySchemes": {"Token": {"type": "http", "scheme": "bearer"}},
        "callbacks": {"ignorado": {}},
    },
    "paths": {
        "/tarefas": {
            "parameters": [{"name": "tenant", "in": "header", "schema": {"type": "string"}}],
            "get": {
                "summary": "Lista",
                "operationId": "listar",
                "x-interceptors": {},
                "parameters": [
                    {"$ref": "#/components/parameters/Pagina"},
                    None,
                    {"name": "tenant", "in": "header", "schema": {"type": "integer"}},
                ],
                "responses": {"200": {"description": "OK", "x-flag": 1}},
            },
            "post": {"requestBody": {"content": {}}, "responses": {}},
        },
        "/vazio": "nao e objeto",
    },
}


def test_root_contract_sem_extensoes():
    root = swagger_root_contract(SWAGGER)
    assert root == {
        "contact": {"name": "Time"},
        "tags": [{"name": "Tarefas"}],
        "security": [{"Token": []}],
    }


def test_components_so_as_secoes_governadas():
    components = swagger_components(SWAGGER)
    assert set(components) == {"schemas", "securitySchemes"}
    # `x-id` é nome de propriedade, não extensão
    assert "x-id" in components["schemas"]["Tarefa"]["properties"]


def test_operacoes_mesclam_parametros_e_expandem_ref():
    warnings = []
    ops = swagger_operations_contract(SWAGGER, warnings)
    get = ops[("GET", "/tarefas")]
    assert get["summary"] == "Lista" and get["operationId"] == "listar"
    assert "x-interceptors" not in get
    assert get["parameters"] == [
        {"name": "page", "in": "query", "schema": {"type": "integer"}},
        {"name": "tenant", "in": "header", "schema": {"type": "integer"}},
    ]
    assert get["responses"] == {"200": {"description": "OK"}}
    assert any("não é objeto" in w for w in warnings)


def test_responses_vazio_e_omitido_e_requestbody_mantido():
    ops = swagger_operations_contract(SWAGGER, [])
    post = ops[("POST", "/tarefas")]
    assert "responses" not in post
    assert post["requestBody"] == {"content": {}}
    assert ("GET", "/vazio") not in ops


def test_ref_inexistente_e_avisado_e_mantido():
    document = {
        "openapi": "3.0.0",
        "paths": {"/a": {"get": {"parameters": [{"$ref": "#/components/parameters/Nada"}]}}},
    }
    warnings = []
    ops = swagger_operations_contract(document, warnings)
    assert ops[("GET", "/a")]["parameters"] == [{"$ref": "#/components/parameters/Nada"}]
    assert warnings == ["GET /a: #/components/parameters/Nada não existe em components.parameters — escrito como está"]


def test_valores_livres_preservam_chaves_x():
    assert without_extensions({"example": {"x-a": 1}, "x-b": 2}) == {"example": {"x-a": 1}}


def test_formato_do_documento():
    assert is_openapi_3(SWAGGER)
    assert not is_openapi_3({"swagger": "2.0"})
    assert document_format({"swagger": "2.0"}) == "Swagger 2.0"
    assert document_format({}) == "formato sem `openapi`"
