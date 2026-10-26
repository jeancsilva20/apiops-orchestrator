"""OpenAPI contract battery against the API-lab 425 (WRITES the Draft and restores it).

Runs the real `sen validate` with a contract over the Draft flow and reads the
revision swagger back. Not run by default: requires `APIOPS_BATERIA_425=1` and
a valid consulting session (`sen login`). The tests run in order; the Draft is
restored from the swagger backup at the end.
"""

import copy
import importlib.util
import json
import os
from pathlib import Path

import pytest
import yaml

from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
    LocalFileImporterAdapter,
)
from apiops_orchestrator.application.exceptions.validate_exceptions import (
    InvalidContractError,
)
from apiops_orchestrator.application.services.repo_importer_service import RepoCanonicalReader
from apiops_orchestrator.application.services.validate_service import ValidateService
from apiops_orchestrator.domain.services import openapi_contract
from apiops_orchestrator.domain.services import repo_layout as layout
from apiops_orchestrator.domain.services import revision_payload
from apiops_orchestrator.domain.services.repo_materializer import materialize

API_ID = 425
TEMPLATE_ID = 414
DOCUMENTED_PATH = "/c1-pura"
DOCUMENTED_RESOURCE = "Quebra"
EXTRACTOR = Path(__file__).resolve().parents[3] / "apiops-versioner" / "extrair_estrutura_v2.py"

pytestmark = pytest.mark.skipif(
    os.environ.get("APIOPS_BATERIA_425") != "1",
    reason="battery that WRITES the API-lab 425; requires APIOPS_BATERIA_425=1",
)

COMPONENTS = {
    "securitySchemes": {
        "TokenPortador": {
            "type": "http",
            "scheme": "bearer",
            "description": "Token obtido no fluxo de autenticação do gateway",
        }
    },
    "schemas": {
        "Tarefa": {
            "type": "object",
            "description": "Tarefa do laboratório de contrato",
            "required": ["id"],
            "properties": {"id": {"type": "string", "description": "Identificador da tarefa"}},
        },
        "NovaTarefa": {
            "type": "object",
            "description": "Dados para criar uma tarefa",
            "required": ["titulo"],
            "properties": {"titulo": {"type": "string", "description": "Título da nova tarefa"}},
        },
    },
    "responses": {
        "NaoEncontrado": {"description": "Tarefa não encontrada no laboratório"},
        "RequisicaoInvalida": {"description": "Requisição fora do contrato da rota"},
    },
    "requestBodies": {
        "NovaTarefa": {
            "required": True,
            "description": "Corpo de criação de tarefa",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/NovaTarefa"}}},
        }
    },
}

DOCUMENTED_POST = {
    "path": DOCUMENTED_PATH,
    "summary": "Cria uma tarefa no laboratório",
    "operationId": "criarTarefaLab",
    "tags": ["Laboratorio"],
    "requestBody": {"$ref": "#/components/requestBodies/NovaTarefa"},
    "responses": {
        "201": {
            "description": "Tarefa criada com sucesso",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Tarefa"}}},
        },
        "400": {"$ref": "#/components/responses/RequisicaoInvalida"},
    },
}

UNDOCUMENTED_POST = {"path": DOCUMENTED_PATH, "responses": {"200": {"description": "OK"}}}


# --------------------------------------------------------------------- harness


class _RecordingManager:
    """Delegates to the real adapter and records the name of each call."""

    def __init__(self, inner):
        self._inner = inner
        self.calls = []

    def __getattr__(self, name):
        attribute = getattr(self._inner, name)
        if not callable(attribute):
            return attribute

        def call(*args, **kwargs):
            self.calls.append(name)
            return attribute(*args, **kwargs)

        return call


@pytest.fixture(scope="module")
def manager():
    from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
        ManagerApiAdapter,
    )
    from apiops_orchestrator.main import _build_admin_token, _load_settings

    settings = _load_settings()
    return _RecordingManager(
        ManagerApiAdapter(
            token=_build_admin_token(settings),
            base_path="/api-manager/api/v3/",
            max_retries=3,
            settings=settings,
        )
    )


@pytest.fixture(scope="module")
def lab(manager, tmp_path_factory):
    """API, Draft id and backup; restores the Draft swagger at the end of the module."""
    api = manager.get_api_by_id(API_ID)
    assert "lab heranca" in (api.get("name") or "").lower(), "the session is not the consulting one"
    draft_id = next(r["id"] for r in api["revisions"] if r["revisionNumber"] == 1)
    revision = manager.get_revision(draft_id)
    swagger = manager.get_revision_swagger(draft_id)
    target = tmp_path_factory.mktemp("backup") / "backup-425-contract.json"
    target.write_text(
        json.dumps({"revision": revision, "swagger": swagger}, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n[harness] backup at {target}")
    yield {"api": api, "draft_id": draft_id, "revision": revision, "swagger": swagger}
    manager.update_revision_swagger(draft_id, copy.deepcopy(swagger))


@pytest.fixture(scope="module")
def state():
    """Values carried from one ordered test to the next."""
    return {}


@pytest.fixture(scope="module")
def validate(manager):
    from apiops_orchestrator.main import _load_settings

    settings = _load_settings()
    assert not settings.pipeline_mode, "the battery runs in local mode, on the Draft"
    service = ValidateService(
        manager_api=manager, importer=LocalFileImporterAdapter(), settings=settings
    )

    def run(path):
        questions = []
        view = service.validate(path, confirm=lambda q: questions.append(q) or True)
        return view, questions

    return run


def _write_yaml(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _read_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _resource_folder(repo, name):
    for resource_file in (repo / layout.RESOURCES_FOLDER).glob(f"*/{layout.RESOURCE_FILE}"):
        if _read_yaml(resource_file).get("name") == name:
            return resource_file.parent
    raise AssertionError(f"resource {name} not materialized")


def _operation_file(repo, path, method="get"):
    for operation_file in (repo / layout.RESOURCES_FOLDER).glob(f"*/{method}_*.yaml"):
        if _read_yaml(operation_file).get("path") == path:
            return operation_file
    raise AssertionError(f"{method.upper()} {path} not materialized")


def _repository(
    tmp_path,
    lab,
    with_404=True,
    without_responses=False,
    new_route=None,
    changed_payload=False,
):
    """The Draft flow, materialized from the backup, with the contract on top."""
    for file in materialize(lab["api"], lab["revision"]).files:
        target = tmp_path / file.file_path
        target.parent.mkdir(parents=True, exist_ok=True)
        text = file.text
        if file.file_path == layout.BASIC_INFO_FILE:
            text = text.replace("template: ''", f"template: {TEMPLATE_ID}")
        target.write_text(text, encoding="utf-8")

    basic_info_path = tmp_path / layout.BASIC_INFO_FILE
    basic_info = _read_yaml(basic_info_path)
    basic_info["spec"].update(
        {
            "contact": {"name": "Time do laboratório", "email": "lab@exemplo.com"},
            "tags": [{"name": "Laboratorio", "description": "Rotas do laboratório de contrato"}],
            "security": [{"TokenPortador": []}],
        }
    )
    _write_yaml(basic_info_path, basic_info)

    components = copy.deepcopy(COMPONENTS)
    if changed_payload:
        tarefa = components["schemas"]["Tarefa"]
        tarefa["required"] = ["id", "titulo"]
        tarefa["properties"]["titulo"] = {"type": "string", "description": "Título da tarefa"}
        components["requestBodies"]["NovaTarefa"]["description"] = "Corpo de criação, revisado"
    _write_yaml(tmp_path / layout.COMPONENTS_FILE, components)

    for operation_path in (tmp_path / layout.RESOURCES_FOLDER).glob("*/*.yaml"):
        if operation_path.name == layout.RESOURCE_FILE:
            continue
        data = _read_yaml(operation_path)
        data["summary"] = f"Rota {data['path']} do laboratório"
        data["responses"] = {"200": {"description": "Consulta realizada"}}
        if data["path"] == DOCUMENTED_PATH:
            data["operationId"] = "listarTarefasLab"
            data["tags"] = ["Laboratorio"]
            data["parameters"] = [
                {
                    "name": "page",
                    "in": "query",
                    "description": "Número da página",
                    "schema": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50 if changed_payload else 100,
                        "default": 1,
                    },
                }
            ]
            data["responses"] = {
                "200": {
                    "description": "Tarefa encontrada",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Tarefa"}}
                    },
                }
            }
            if with_404:
                data["responses"]["404"] = {"$ref": "#/components/responses/NaoEncontrado"}
            if without_responses:
                del data["responses"]
        _write_yaml(operation_path, data)

    if new_route is not None:
        post = DOCUMENTED_POST if new_route == "documented" else UNDOCUMENTED_POST
        _write_yaml(
            _resource_folder(tmp_path, DOCUMENTED_RESOURCE) / f"post{DOCUMENTED_PATH.replace('/', '_')}.yaml",
            copy.deepcopy(post),
        )
    return tmp_path


def _contract_failures(view):
    markers = ("não foi gravado", "não é o que foi enviado", "recusou", "Não consegui", "não respondeu")
    return [
        a.message for a in view.findings
        if a.scope == "repositório" and any(m in a.message for m in markers)
    ]


def _contract_of(repo):
    loaded = RepoCanonicalReader(LocalFileImporterAdapter()).load(str(repo))
    contract = openapi_contract.extract_contract(
        basic_info=loaded.basic_info, components=loaded.components, resources=loaded.resources
    )
    paths = {}
    for (method, path), fields in contract.operations.items():
        paths.setdefault(path, {})[method.lower()] = fields
    return {
        "info": {"contact": contract.root.get("contact")},
        "tags": contract.root.get("tags"),
        "security": contract.root.get("security"),
        "components": contract.components,
        "paths": paths,
    }


def _pull_with_extractor(token, target):
    """Runs the extractor v2 unchanged, with the session token and the 425 Draft, into `target`."""
    spec = importlib.util.spec_from_file_location("extrator_v2_contract_battery", EXTRACTOR)
    extractor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extractor)
    extractor.TOKEN = token
    extractor.API_ID = API_ID
    extractor.REVISION_NUMBER = 1
    extractor.DESTINO = str(target)
    assert extractor.main() == 0
    return target / f"api-{API_ID}-rev1"


# --------------------------------------------------------------------- tests


def test_1_contract_is_written_and_the_flow_is_kept(tmp_path, lab, validate, manager):
    manager.calls.clear()
    view, questions = validate(_repository(tmp_path, lab))

    assert view.publication.verified is True
    [question] = questions
    assert "O swagger da revisão também recebe o contrato OpenAPI" in question
    assert _contract_failures(view) == []
    assert manager.calls.index("update_revision") < manager.calls.index("update_revision_swagger")

    swagger = manager.get_revision_swagger(lab["draft_id"])
    operation = swagger["paths"][DOCUMENTED_PATH]["get"]
    assert operation["operationId"] == "listarTarefasLab"
    assert operation["responses"]["404"] == {"$ref": "#/components/responses/NaoEncontrado"}
    assert "NaoEncontrado" in swagger["components"]["responses"]
    assert swagger["info"]["contact"]["name"] == "Time do laboratório"
    assert swagger["servers"] == lab["swagger"]["servers"]


def test_2_second_run_does_not_rewrite_the_swagger(tmp_path, lab, validate, manager):
    manager.calls.clear()
    view, questions = validate(_repository(tmp_path, lab))

    assert view.publication.verified is True
    assert "saem da documentação" not in questions[0]
    assert "update_revision_swagger" not in manager.calls
    assert _contract_failures(view) == []


def test_3_removed_documentation_is_announced_and_the_runtime_is_kept(
    tmp_path, lab, validate, manager
):
    """Same flow as the previous run, only the contract changes: the runtime must not move."""
    before = manager.get_revision(lab["draft_id"])
    manager.calls.clear()

    view, questions = validate(_repository(tmp_path, lab, with_404=False))

    assert f"GET {DOCUMENTED_PATH} · resposta 404" in questions[0]
    assert "update_revision_swagger" in manager.calls
    assert _contract_failures(view) == []
    swagger = manager.get_revision_swagger(lab["draft_id"])
    assert "404" not in swagger["paths"][DOCUMENTED_PATH]["get"]["responses"]
    assert revision_payload.verify(before, manager.get_revision(lab["draft_id"])) == []


def test_4_invalid_contract_writes_nothing(tmp_path, lab, validate, manager):
    manager.calls.clear()

    with pytest.raises(InvalidContractError) as raised:
        validate(_repository(tmp_path, lab, without_responses=True))

    assert "não declara `responses`" in raised.value.message
    assert manager.calls == []


def test_5_new_documented_route_keeps_the_completeness(tmp_path, lab, validate, manager, state):
    before = manager.get_revision_completeness(lab["draft_id"]).score

    view, _ = validate(_repository(tmp_path, lab, new_route="documented"))

    assert view.publication.verified is True
    assert _contract_failures(view) == []
    swagger = manager.get_revision_swagger(lab["draft_id"])
    post = swagger["paths"][DOCUMENTED_PATH]["post"]
    assert post["requestBody"] == {"$ref": "#/components/requestBodies/NovaTarefa"}
    assert post["responses"]["400"] == {"$ref": "#/components/responses/RequisicaoInvalida"}
    assert post["x-resource-name"] == DOCUMENTED_RESOURCE
    state["documented"] = view.completeness.score
    print(f"\n[completeness] before {before} · with the documented new route {view.completeness.score}")
    assert view.completeness.score >= before


def test_6_same_route_without_documentation_lowers_the_completeness(
    tmp_path, lab, validate, manager, state
):
    view, questions = validate(_repository(tmp_path, lab, new_route="undocumented"))

    assert view.publication.verified is True
    assert _contract_failures(view) == []
    for removed in ("requestBody", "operationId", "resposta 201", "resposta 400"):
        assert f"POST {DOCUMENTED_PATH} · {removed}" in questions[0]
    assert any("abaixo do mínimo" in a.message for a in view.findings)
    print(f"\n[completeness] undocumented new route {view.completeness.score} · documented {state['documented']}")
    assert view.completeness.score < state["documented"]


def test_7_changed_payload_is_written(tmp_path, lab, validate, manager, state):
    repo = _repository(tmp_path, lab, new_route="documented", changed_payload=True)
    manager.calls.clear()

    view, _ = validate(repo)

    assert view.publication.verified is True
    assert "update_revision_swagger" in manager.calls
    assert _contract_failures(view) == []
    swagger = manager.get_revision_swagger(lab["draft_id"])
    tarefa = swagger["components"]["schemas"]["Tarefa"]
    assert set(tarefa["required"]) == {"id", "titulo"}
    assert "titulo" in tarefa["properties"]
    get = swagger["paths"][DOCUMENTED_PATH]["get"]
    assert get["parameters"][0]["schema"]["maximum"] == 50
    assert swagger["components"]["requestBodies"]["NovaTarefa"]["description"] == "Corpo de criação, revisado"
    state["uploaded"] = repo


def _break_wrong_section(repo):
    path = _operation_file(repo, DOCUMENTED_PATH)
    data = _read_yaml(path)
    data["responses"]["404"] = {"$ref": "#/components/requestBodies/NovaTarefa"}
    _write_yaml(path, data)


def _break_missing_schema(repo):
    path = _operation_file(repo, DOCUMENTED_PATH)
    data = _read_yaml(path)
    data["responses"]["200"]["content"]["application/json"]["schema"] = {
        "$ref": "#/components/schemas/Inexistente"
    }
    _write_yaml(path, data)


def _break_external_ref(repo):
    path = _operation_file(repo, DOCUMENTED_PATH)
    data = _read_yaml(path)
    data["responses"]["200"]["content"]["application/json"]["schema"] = {"$ref": "./tarefa.yaml"}
    _write_yaml(path, data)


def _break_example_type(repo):
    path = _operation_file(repo, DOCUMENTED_PATH)
    data = _read_yaml(path)
    data["parameters"][0]["example"] = "primeira"
    _write_yaml(path, data)


def _break_enum_type(repo):
    components = _read_yaml(repo / layout.COMPONENTS_FILE)
    components["schemas"]["Tarefa"]["properties"]["id"]["enum"] = [1, 2]
    _write_yaml(repo / layout.COMPONENTS_FILE, components)


def _break_body_on_get(repo):
    path = _operation_file(repo, DOCUMENTED_PATH)
    data = _read_yaml(path)
    data["requestBody"] = {"$ref": "#/components/requestBodies/NovaTarefa"}
    _write_yaml(path, data)


def _break_resource_path_parameter(repo):
    path = _resource_folder(repo, DOCUMENTED_RESOURCE) / layout.RESOURCE_FILE
    data = _read_yaml(path)
    data["parameters"] = [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}]
    _write_yaml(path, data)


def _break_path_parameter_outside_the_route(repo):
    path = _operation_file(repo, DOCUMENTED_PATH)
    data = _read_yaml(path)
    data["parameters"].append({"name": "id", "in": "path", "required": True})
    _write_yaml(path, data)


def _break_repeated_parameter(repo):
    path = _operation_file(repo, DOCUMENTED_PATH)
    data = _read_yaml(path)
    data["parameters"].append(copy.deepcopy(data["parameters"][0]))
    _write_yaml(path, data)


def _break_duplicate_operation_id(repo):
    path = _operation_file(repo, DOCUMENTED_PATH, method="post")
    data = _read_yaml(path)
    data["operationId"] = "listarTarefasLab"
    _write_yaml(path, data)


def _break_unknown_security_scheme(repo):
    path = _operation_file(repo, DOCUMENTED_PATH)
    data = _read_yaml(path)
    data["security"] = [{"Desconhecido": []}]
    _write_yaml(path, data)


def _break_response_without_description(repo):
    path = _operation_file(repo, DOCUMENTED_PATH)
    data = _read_yaml(path)
    data["responses"]["200"].pop("description")
    _write_yaml(path, data)


def _break_invalid_status(repo):
    path = _operation_file(repo, DOCUMENTED_PATH)
    data = _read_yaml(path)
    data["responses"]["2xx"] = {"description": "Sucesso genérico"}
    _write_yaml(path, data)


def _break_response_cycle(repo):
    components = _read_yaml(repo / layout.COMPONENTS_FILE)
    components["responses"]["A"] = {"$ref": "#/components/responses/B"}
    components["responses"]["B"] = {"$ref": "#/components/responses/A"}
    _write_yaml(repo / layout.COMPONENTS_FILE, components)


def _break_extension_in_a_route(repo):
    path = _operation_file(repo, DOCUMENTED_PATH)
    data = _read_yaml(path)
    data["x-rate-limit"] = 10
    _write_yaml(path, data)


def _break_servers_in_basic_info(repo):
    path = repo / layout.BASIC_INFO_FILE
    data = _read_yaml(path)
    data["spec"]["servers"] = [{"url": "/outro"}]
    _write_yaml(path, data)


def _break_reusable_parameters(repo):
    components = _read_yaml(repo / layout.COMPONENTS_FILE)
    components["parameters"] = {"Page": {"name": "page", "in": "query"}}
    _write_yaml(repo / layout.COMPONENTS_FILE, components)


def _break_components_yml(repo):
    (repo / layout.COMPONENTS_FILE).rename(repo / "components.yml")


INVALID_CONTRACTS = {
    "ref to the wrong section": (_break_wrong_section, "só cabe referência a `#/components/responses/`"),
    "ref to a missing schema": (_break_missing_schema, "`#/components/schemas/Inexistente` não existe"),
    "external ref": (_break_external_ref, "não é aceito"),
    "example of the wrong type": (_break_example_type, "não é do tipo `integer`"),
    "enum of the wrong type": (_break_enum_type, "não é do tipo `string`"),
    "request body on GET": (_break_body_on_get, "só vale em POST, PUT e PATCH"),
    "resource path parameter missing in a route": (_break_resource_path_parameter, "não existe em"),
    "path parameter outside the route": (_break_path_parameter_outside_the_route, "não existe na rota"),
    "repeated parameter": (_break_repeated_parameter, "repetido"),
    "duplicate operationId": (_break_duplicate_operation_id, "se repete"),
    "unknown security scheme": (_break_unknown_security_scheme, "não está em `securitySchemes`"),
    "response without description": (_break_response_without_description, "precisa de `description`"),
    "invalid status": (_break_invalid_status, "status inválido"),
    "cycle between responses": (_break_response_cycle, "ciclo"),
    "extension in a route file": (_break_extension_in_a_route, "extensões `x-*`"),
    "servers in the basic info": (_break_servers_in_basic_info, "vem do Manager"),
    "reusable parameters section": (_break_reusable_parameters, "escreva cada um por extenso"),
    "components.yml instead of components.yaml": (_break_components_yml, "renomeie-o"),
}


@pytest.mark.parametrize("case", sorted(INVALID_CONTRACTS))
def test_8_invalid_contract_aborts_without_calling_the_manager(case, tmp_path, lab, validate, manager):
    breaker, problem = INVALID_CONTRACTS[case]
    repo = _repository(tmp_path, lab, new_route="documented", changed_payload=True)
    breaker(repo)
    manager.calls.clear()

    with pytest.raises(InvalidContractError) as raised:
        validate(repo)

    assert problem in raised.value.message
    assert raised.value.exit_code == 1
    assert manager.calls == []


@pytest.mark.skipif(not EXTRACTOR.is_file(), reason="extractor v2 not found next to the repository")
def test_9_pulled_api_matches_what_was_uploaded(tmp_path, lab, validate, manager, state):
    pulled = _pull_with_extractor(manager.token, tmp_path / "pulled")

    assert openapi_contract.verify_contract(_contract_of(state["uploaded"]), _contract_of(pulled)) == []

    basic_info = pulled / layout.BASIC_INFO_FILE
    basic_info.write_text(
        basic_info.read_text(encoding="utf-8").replace("template: ''", f"template: {TEMPLATE_ID}"),
        encoding="utf-8",
    )
    manager.calls.clear()
    view, questions = validate(pulled)

    assert view.publication.verified is True
    assert "saem da documentação" not in questions[0]
    assert "update_revision_swagger" not in manager.calls
    assert _contract_failures(view) == []
