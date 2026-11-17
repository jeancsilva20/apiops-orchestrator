"""`sen sync` com ports fake: Manager, disco e escrita em memória."""

import copy
import json
import pathlib

import pytest
import yaml

from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
    LocalFileImporterAdapter,
)
from apiops_orchestrator.adapters.outbound.filesystem.repo_writer_adapter import (
    RepoWriterAdapter,
)
from apiops_orchestrator.application.exceptions.sync_exceptions import (
    ApiIdMismatchError,
    ApiNotFoundError,
    EmptyRevisionError,
    InvalidRepositoryError,
    ManagerUnavailableError,
    MissingApiIdError,
    RevisionNotFoundError,
    SessionRejectedError,
    SyncError,
    UnsupportedSwaggerError,
    WriteFailedError,
)
from apiops_orchestrator.application.services.sync_service import SyncService
from apiops_orchestrator.domain.models.api_model import Api, Revision
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.models.sync_view import MODE_CHECK, MODE_LOAD, SCHEMA_SEN_SYNC_V1
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)
from apiops_orchestrator.domain.ports.repo_writer_port import RepoWriteError
from apiops_orchestrator.domain.services import repo_layout as layout

FIXTURES = pathlib.Path(__file__).parents[3] / "fixtures" / "manager"


def _fixture(name="api-417-rev2"):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _swagger(revision, components=None):
    """OpenAPI 3 sintético com uma rota documentada por operação da revisão."""
    paths = {}
    for resource in revision["resources"]:
        for op in resource.get("operations") or []:
            paths.setdefault(op["path"], {})[op["method"].lower()] = {
                "summary": f"Rota {op['method']} {op['path']} do laboratório",
                "responses": {"200": {"description": "Consulta realizada"}},
            }
    return {
        "openapi": "3.0.1",
        "info": {"title": "Lab", "contact": {"name": "Time do laboratório"}},
        "tags": [{"name": "Laboratorio"}],
        "components": components if components is not None else {
            "schemas": {"Tarefa": {"type": "object", "properties": {"id": {"type": "string"}}}}
        },
        "paths": paths,
    }


def _api(revision):
    api = copy.deepcopy(_fixture()["api"])
    api["visibility"] = {"visibilityType": "ORGANIZATION"}
    api["revisions"] = [
        {"id": 9161, "revisionNumber": 1},
        {"id": revision["id"], "revisionNumber": revision["revisionNumber"]},
        {"id": 9327, "revisionNumber": 3},
    ]
    return api


class ManagerFake:
    """Port fake: grava cada chamada e só conhece GET."""

    def __init__(
        self, api=None, revision=None, swagger=None, error_api=None, error_revision=None
    ):
        data = _fixture()
        self.revision = revision if revision is not None else copy.deepcopy(data["revision"])
        self.api = api if api is not None else _api(self.revision)
        self.swagger = swagger if swagger is not None else _swagger(self.revision)
        self.error_api = error_api
        self.error_revision = error_revision
        self.calls = []

    def get_revision_swagger(self, revision_id):
        self.calls.append(f"get_revision_swagger:{revision_id}")
        return copy.deepcopy(self.swagger)

    def get_api_by_id(self, api_id):
        self.calls.append(f"get_api_by_id:{api_id}")
        if self.error_api is not None:
            raise self.error_api
        return Api.model_validate(copy.deepcopy(self.api))

    def get_revision(self, revision_id):
        self.calls.append(f"get_revision:{revision_id}")
        if self.error_revision is not None:
            raise self.error_revision
        return Revision.model_validate(copy.deepcopy(self.revision))

    def __getattr__(self, name):  # pragma: no cover - any other call is a defect
        raise AssertionError(f"o sync só faz GET; chamou {name}")


class WriterSpy:
    def __init__(self, error=None):
        self.error = error
        self.written = None

    def write_managed_area(self, root, files):
        if self.error is not None:
            raise self.error
        self.written = {f.file_path: f.text for f in files}


def _basic_info(tmp_path, spec):
    (tmp_path / layout.BASIC_INFO_FILE).write_text(
        yaml.safe_dump({"apiVersion": "x", "kind": "ApiBasicInfo", "spec": spec}, allow_unicode=True),
        encoding="utf-8",
    )


def _service(manager=None, writer=None, session=None):
    return SyncService(
        manager_api=manager or ManagerFake(),
        importer=LocalFileImporterAdapter(),
        writer=writer or WriterSpy(),
        session=session,
    )


def _dev_session(groups=("APIOps",)):
    return LoginSession(
        accessToken="t",
        tokenType="Bearer",
        expiresIn=3600,
        scope="read",
        profile="developer",
        userName="dev",
        userEmail="dev@x.com",
        userGroups=list(groups),
    )


# --- carga -------------------------------------------------------------------


def test_carga_grava_a_arvore_e_preserva_o_template(tmp_path):
    _basic_info(tmp_path, {"template": 414})
    manager, writer = ManagerFake(), WriterSpy()
    steps = []

    view = _service(manager, writer).sync(
        tmp_path, api_id=417, revision_number=2, progress=steps.append
    )

    assert view.schema == SCHEMA_SEN_SYNC_V1 and view.mode == MODE_LOAD
    assert view.api.manager_id == 417 and view.revision.revision_number == 2
    assert set(writer.written) == set(view.files) and len(view.files) == 14
    basic_info = yaml.safe_load(writer.written[layout.BASIC_INFO_FILE])
    assert basic_info["spec"]["template"] == 414
    assert basic_info["spec"]["id"] == 417
    assert basic_info["spec"]["contact"] == {"name": "Time do laboratório"}
    assert yaml.safe_load(writer.written[layout.COMPONENTS_FILE])["schemas"]["Tarefa"]
    assert view.resources == 4 and view.operations == 7
    assert manager.calls == [
        "get_api_by_id:417", "get_revision:9175", "get_revision_swagger:9175"
    ]
    assert steps[0] == "Consultando a API no Manager" and "Gravando os arquivos" in steps


def test_id_vem_do_spec_quando_o_argumento_falta(tmp_path):
    _basic_info(tmp_path, {"id": 417, "template": ""})
    manager = ManagerFake()
    _service(manager).sync(tmp_path, api_id=None, revision_number=2)
    assert manager.calls[0] == "get_api_by_id:417"


def test_sem_id_em_lugar_nenhum_falha_sem_rede(tmp_path):
    manager, writer = ManagerFake(), WriterSpy()
    with pytest.raises(MissingApiIdError) as info:
        _service(manager, writer).sync(tmp_path, api_id=None, revision_number=4)
    assert info.value.exit_code == 1 and manager.calls == [] and writer.written is None


def test_id_diferente_do_spec_falha_sem_rede(tmp_path):
    _basic_info(tmp_path, {"id": 425})
    manager, writer = ManagerFake(), WriterSpy()
    with pytest.raises(ApiIdMismatchError) as info:
        _service(manager, writer).sync(tmp_path, api_id=417, revision_number=4)
    assert info.value.exit_code == 5 and manager.calls == [] and writer.written is None


def test_basic_info_ilegivel_aborta_sem_rede(tmp_path):
    (tmp_path / layout.BASIC_INFO_FILE).write_text("spec: [\n", encoding="utf-8")
    manager = ManagerFake()
    with pytest.raises(SyncError) as info:
        _service(manager).sync(tmp_path, api_id=417, revision_number=4)
    assert info.value.exit_code == 1 and manager.calls == []


def test_api_inexistente_e_invisivel_respondem_igual(tmp_path):
    not_found = ManagerApiTransportRejectedError(404, "Not Found")
    invisible = ManagerFake()
    invisible.api["visibility"] = {"visibilityType": "GROUP", "groupVisibility": {"name": "Outro"}}
    messages = []
    for manager in (ManagerFake(error_api=not_found), invisible):
        writer = WriterSpy()
        with pytest.raises(ApiNotFoundError) as info:
            _service(manager, writer, session=_dev_session()).sync(
                tmp_path, api_id=417, revision_number=2
            )
        messages.append(info.value.message)
        assert info.value.exit_code == 3 and writer.written is None
        assert not any(c.startswith("get_revision") for c in manager.calls)
    assert messages[0] == messages[1] and "417" in messages[0]


def test_super_admin_enxerga_api_de_outro_grupo(tmp_path):
    manager = ManagerFake()
    manager.api["visibility"] = {"visibilityType": "GROUP", "groupVisibility": {"name": "Outro"}}
    admin = LoginSession(
        accessToken="t", tokenType="Bearer", expiresIn=3600, scope="all",
        profile="super-admin", adminAccessToken="a",
    )
    view = _service(manager, session=admin).sync(tmp_path, api_id=417, revision_number=2)
    assert view.mode == MODE_LOAD


def test_revisao_inexistente_lista_as_disponiveis(tmp_path):
    manager, writer = ManagerFake(), WriterSpy()
    with pytest.raises(RevisionNotFoundError) as info:
        _service(manager, writer).sync(tmp_path, api_id=417, revision_number=4)
    assert info.value.exit_code == 4
    assert "Disponíveis: 1, 2, 3" in info.value.message
    assert manager.calls == ["get_api_by_id:417"] and writer.written is None


def test_revisao_sem_recursos_aborta(tmp_path):
    revision = dict(_fixture()["revision"], resources=[])
    manager, writer = ManagerFake(revision=revision), WriterSpy()
    with pytest.raises(EmptyRevisionError) as info:
        _service(manager, writer).sync(tmp_path, api_id=417, revision_number=2)
    assert info.value.exit_code == 4 and writer.written is None


@pytest.mark.parametrize("status", [401, 403])
def test_sessao_recusada_pelo_manager(tmp_path, status):
    manager = ManagerFake(error_api=ManagerApiTransportRejectedError(status, "Denied"))
    with pytest.raises(SessionRejectedError) as info:
        _service(manager).sync(tmp_path, api_id=417, revision_number=2)
    assert info.value.exit_code == 2 and "sen login" in info.value.message


def test_manager_indisponivel(tmp_path):
    manager = ManagerFake(error_revision=ManagerApiTransportUnavailableError("down"))
    with pytest.raises(ManagerUnavailableError) as info:
        _service(manager).sync(tmp_path, api_id=417, revision_number=2)
    assert info.value.exit_code == 7


def test_outra_recusa_do_manager_vira_erro_interno(tmp_path):
    manager = ManagerFake(error_api=ManagerApiTransportRejectedError(429, "Too Many"))
    with pytest.raises(SyncError) as info:
        _service(manager).sync(tmp_path, api_id=417, revision_number=2)
    assert info.value.exit_code == 1 and "429" not in info.value.message


def test_falha_de_escrita_vira_exit_6(tmp_path):
    writer = WriterSpy(error=RepoWriteError("caminho longo demais", "resources/x/get.yaml"))
    with pytest.raises(WriteFailedError) as info:
        _service(ManagerFake(), writer).sync(tmp_path, api_id=417, revision_number=2)
    assert info.value.exit_code == 6
    assert "resources/x/get.yaml" in info.value.message and "260" in info.value.message


def test_avisos_saem_deduplicados_e_ordenados(tmp_path):
    view = _service().sync(tmp_path, api_id=417, revision_number=2)
    assert view.warnings == sorted(set(view.warnings))


# --- verificação ---------------------------------------------------------------


def _loaded_repo(tmp_path, template=414):
    """Repositório igual ao Manager: a carga real gravada em disco."""
    _basic_info(tmp_path, {"template": template})
    _service(ManagerFake(), RepoWriterAdapter(max_path=None)).sync(
        tmp_path, api_id=417, revision_number=2
    )


def test_check_logo_depois_da_carga_nao_tem_diferenca(tmp_path):
    _loaded_repo(tmp_path)
    manager = ManagerFake()
    view = _service(manager).check(tmp_path, api_id=None, revision_number=2)
    assert view.mode == MODE_CHECK and view.in_sync and view.differences == []
    assert manager.calls == [
        "get_api_by_id:417", "get_revision:9175", "get_revision_swagger:9175"
    ]


def test_check_ignora_comentarios_e_formatacao(tmp_path):
    _loaded_repo(tmp_path)
    path = tmp_path / "resources" / "health-check" / "resource.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    reordered = {k: data[k] for k in reversed(list(data))}
    path.write_text("# comentário novo\n" + yaml.safe_dump(reordered, allow_unicode=True), encoding="utf-8")

    view = _service().check(tmp_path, api_id=417, revision_number=2)
    assert view.in_sync, view.differences


def test_check_aponta_alteracao_feita_no_manager(tmp_path):
    _loaded_repo(tmp_path)
    changed = copy.deepcopy(_fixture()["revision"])
    op = changed["resources"][0]["operations"][0]
    op["timeout"] = "99"
    changed["timeout"] = "45"

    view = _service(ManagerFake(revision=changed)).check(tmp_path, api_id=417, revision_number=2)

    assert not view.in_sync
    fields = {(d.file, d.field): (d.repository, d.manager) for d in view.differences}
    assert fields["all.yaml", "destination.timeout"] == ("30", "45")
    op_diff = next(v for (f, field), v in fields.items() if field == "destination.timeout" and f != "all.yaml")
    assert op_diff[1] == "99"


def test_check_aponta_alteracao_feita_no_repositorio(tmp_path):
    _loaded_repo(tmp_path)
    basic = tmp_path / layout.BASIC_INFO_FILE
    data = yaml.safe_load(basic.read_text(encoding="utf-8"))
    data["spec"]["description"] = "Descrição editada no Git"
    basic.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    view = _service().check(tmp_path, api_id=417, revision_number=2)
    assert [(d.file, d.field, d.repository) for d in view.differences] == [
        (layout.BASIC_INFO_FILE, "spec.description", "Descrição editada no Git")
    ]


def test_check_nao_grava_nada(tmp_path):
    _loaded_repo(tmp_path)
    writer = WriterSpy()
    before = {p: p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.yaml")}
    _service(ManagerFake(), writer).check(tmp_path, api_id=417, revision_number=2)
    assert writer.written is None
    assert {p: p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.yaml")} == before


def test_check_exige_a_estrutura_completa(tmp_path):
    _basic_info(tmp_path, {"id": 417})
    with pytest.raises(InvalidRepositoryError) as info:
        _service().check(tmp_path, api_id=None, revision_number=2)
    assert info.value.exit_code == 1 and layout.ROOT_FILE in info.value.message


# --- contrato OpenAPI ---------------------------------------------------------------


def test_swagger_2_aborta_sem_gravar(tmp_path):
    manager = ManagerFake(swagger={"swagger": "2.0", "paths": {}})
    writer = WriterSpy()
    with pytest.raises(UnsupportedSwaggerError) as info:
        _service(manager, writer).sync(tmp_path, api_id=417, revision_number=2)
    assert info.value.exit_code == 4 and "Swagger 2.0" in info.value.message
    assert writer.written is None


def test_check_aponta_contrato_alterado_no_manager(tmp_path):
    _loaded_repo(tmp_path)
    revision = _fixture()["revision"]
    changed = _swagger(revision)
    first = revision["resources"][0]["operations"][0]
    changed["paths"][first["path"]][first["method"].lower()]["summary"] = "Resumo novo"
    changed["components"]["schemas"]["Tarefa"]["properties"]["nome"] = {"type": "string"}

    view = _service(ManagerFake(swagger=changed)).check(tmp_path, api_id=417, revision_number=2)

    fields = {(d.file, d.field): (d.repository, d.manager) for d in view.differences}
    assert (layout.COMPONENTS_FILE, "schemas.Tarefa.properties.nome") in fields
    summary = next(v for (f, field), v in fields.items() if field == "summary")
    assert summary[1] == "Resumo novo"
    assert len(fields) == 2


def test_check_aponta_contrato_alterado_no_repositorio(tmp_path):
    _loaded_repo(tmp_path)
    components = tmp_path / layout.COMPONENTS_FILE
    data = yaml.safe_load(components.read_text(encoding="utf-8"))
    data["responses"] = {"NaoEncontrado": {"description": "Tarefa não encontrada"}}
    components.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    view = _service().check(tmp_path, api_id=417, revision_number=2)
    assert [(d.file, d.field, d.manager) for d in view.differences] == [
        (layout.COMPONENTS_FILE, "responses", "<ausente>")
    ]


def test_check_aceita_mock_guardado_como_objeto_no_manager(tmp_path):
    """The 426 Draft kept `body: {}` and `status: 200` as object/number; after a PUT they are text."""
    as_text = copy.deepcopy(_fixture()["revision"])
    op = as_text["resources"][0]["operations"][0]
    op["interceptors"] = list(op.get("interceptors") or []) + [{
        "id": 777, "type": "Mock", "executionPoint": "FIRST", "position": 9,
        "content": '{"body": "{}", "status": "200", "headers": "Content-Type: application/json"}',
    }]
    _basic_info(tmp_path, {"template": 414})
    _service(ManagerFake(revision=as_text), RepoWriterAdapter(max_path=None)).sync(
        tmp_path, api_id=417, revision_number=2
    )

    as_object = copy.deepcopy(as_text)
    as_object["resources"][0]["operations"][0]["interceptors"][-1]["content"] = (
        '{"body": {}, "status": 200, "headers": "Content-Type: application/json"}'
    )
    view = _service(ManagerFake(revision=as_object)).check(tmp_path, api_id=417, revision_number=2)

    assert view.in_sync, view.differences


# --- --template ----------------------------------------------------------------

class ManagerSemTemplate(ManagerFake):
    """Only the API 999 is missing; everything else answers like the fake."""

    def get_api_by_id(self, api_id):
        if api_id == 999:
            self.calls.append(f"get_api_by_id:{api_id}")
            raise ManagerApiTransportRejectedError(404, "Not Found")
        return super().get_api_by_id(api_id)


def test_template_informado_e_conferido_e_gravado(tmp_path):
    _basic_info(tmp_path, {"template": 100})
    manager, writer = ManagerFake(), WriterSpy()

    _service(manager, writer).sync(tmp_path, api_id=417, revision_number=2, template=414)

    assert yaml.safe_load(writer.written[layout.BASIC_INFO_FILE])["spec"]["template"] == 414
    assert manager.calls == [
        "get_api_by_id:417", "get_revision:9175", "get_revision_swagger:9175", "get_api_by_id:414"
    ]


def test_sem_template_mantem_o_do_arquivo(tmp_path):
    _basic_info(tmp_path, {"template": 100})
    manager, writer = ManagerFake(), WriterSpy()

    _service(manager, writer).sync(tmp_path, api_id=417, revision_number=2)

    assert yaml.safe_load(writer.written[layout.BASIC_INFO_FILE])["spec"]["template"] == 100
    assert "get_api_by_id:100" not in manager.calls


def test_template_inexistente_aborta_sem_gravar(tmp_path):
    _basic_info(tmp_path, {"template": 100})
    writer = WriterSpy()

    with pytest.raises(ApiNotFoundError) as exc:
        _service(ManagerSemTemplate(), writer).sync(
            tmp_path, api_id=417, revision_number=2, template=999
        )

    assert exc.value.exit_code == 3 and "999" in exc.value.message
    assert writer.written is None


def test_check_ignora_a_ordem_das_apitags(tmp_path):
    _loaded_repo(tmp_path)
    reordered = copy.deepcopy(_fixture()["api"])
    reordered["visibility"] = {"visibilityType": "ORGANIZATION"}
    reordered["revisions"] = _api(_fixture()["revision"])["revisions"]
    reordered["apiTags"] = list(reversed(reordered["apiTags"] + [{"attributeName": "Z", "tags": ["z"]}]))
    # Same set as the repository once "Z" is removed; the order alone must not count.
    reordered["apiTags"] = [t for t in reordered["apiTags"] if t["attributeName"] != "Z"]

    view = _service(ManagerFake(api=reordered)).check(tmp_path, api_id=417, revision_number=2)

    assert view.in_sync, view.differences
