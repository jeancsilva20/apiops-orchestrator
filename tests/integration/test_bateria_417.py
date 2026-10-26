"""Bateria de aceitação do `sen validate` contra a API 417 (ESCREVE na Draft).

Reproduz os cenários do
[caderno de testes](../../docs/feat-api-estructure/prova-fluxo-validate/CADERNO-DE-TESTES.md),
agora através do comando implementado em vez do protótipo.

Os oráculos de T06, T07, T08, T11 e T12 seguem a
[V-28](../../docs/feat-api-estructure/decisoes-refino-409/V-28-heranca-composta-pela-plataforma.md):
cada escopo guarda só os itens próprios e as marcações `REMOVED` do que deixa de
herdar. Esta bateria confere o que cada escopo guarda; o que ele executa é
provado pela `test_bateria_heranca_425.py`.

**Não roda por padrão.** Exige `APIOPS_BATERIA_417=1` e sessão válida
(`sen login`): escreve na revisão Draft da API 417.

Disciplina do arnês, herdada do caderno:

* backup completo da API e de **todas** as revisões antes da primeira escrita;
* o repositório baseline é a materialização da **própria Draft**, para que
  publicá-lo seja um no-op e cada cenário tenha um delta só;
* o veredito vem da **releitura por GET**, nunca do código HTTP (W-8);
* restauração após cada cenário, e conferência do baseline ao fim.
"""

import copy
import json
import os
import pathlib
import shutil

import pytest

from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
    LocalFileImporterAdapter,
)
from apiops_orchestrator.application.exceptions.validate_exceptions import (
    GovernanceBlockedError,
    IdentityMismatchError,
)
from apiops_orchestrator.application.services.validate_service import ValidateService
from apiops_orchestrator.domain.services.interceptor_flow import partition
from apiops_orchestrator.domain.services.repo_materializer import materialize

API_ID = 417
DRAFT_REVISION = 1

pytestmark = pytest.mark.skipif(
    os.environ.get("APIOPS_BATERIA_417") != "1",
    reason="bateria que ESCREVE na API 417; exige APIOPS_BATERIA_417=1",
)


# --------------------------------------------------------------------- arnês


@pytest.fixture(scope="module")
def manager():
    from apiops_orchestrator.main import _build_admin_token, _load_settings
    from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
        ManagerApiAdapter,
    )

    settings = _load_settings()
    return ManagerApiAdapter(
        token=_build_admin_token(settings),
        base_path="/api-manager/api/v3/",
        max_retries=3,
        settings=settings,
    )


@pytest.fixture(scope="module")
def settings_local():
    from apiops_orchestrator.main import _load_settings

    settings = _load_settings()
    assert not settings.pipeline_mode, "a bateria roda em modo local"
    # Ausente vale como Draft em modo local.
    assert (settings.TARGET_REVISION_NUMBER or DRAFT_REVISION) == DRAFT_REVISION
    return settings


@pytest.fixture(scope="module")
def backup(manager, tmp_path_factory):
    """Backup completo ANTES da primeira escrita, gravado em disco."""
    api = manager.get_api_by_id(API_ID)
    data = {"api": api, "revisions": {}}
    for revision in api.get("revisions") or []:
        data["revisions"][str(revision["id"])] = manager.get_revision(revision["id"])

    destination = tmp_path_factory.mktemp("backup") / "backup-417.json"
    destination.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[arnês] backup em {destination}")
    return data


@pytest.fixture(scope="module")
def draft_id(backup):
    for revision in backup["api"].get("revisions") or []:
        if revision.get("revisionNumber") == DRAFT_REVISION:
            return revision["id"]
    pytest.fail("a API 417 não tem revisão de número 1 (Draft)")


@pytest.fixture(scope="module")
def baseline_repo(backup, draft_id, tmp_path_factory):
    """Materializa a PRÓPRIA Draft: publicá-la de volta é um no-op."""
    draft = backup["revisions"][str(draft_id)]
    resultado = materialize(backup["api"], draft)

    root = tmp_path_factory.mktemp("baseline") / "repo"
    for file in resultado.files:
        destination = root / file.file_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(file.text, encoding="utf-8")

    # A régua não vem do wire (D-12): o manifesto precisa declará-la.
    manifesto = root / "api-basic-info.yaml"
    manifesto.write_text(
        manifesto.read_text(encoding="utf-8").replace("template: ''", "template: 414"),
        encoding="utf-8",
    )
    return root


@pytest.fixture
def repo(baseline_repo, tmp_path):
    """Cópia fresca do baseline para cada cenário."""
    target = tmp_path / "repo"
    shutil.copytree(baseline_repo, target)
    return target


@pytest.fixture
def validate(manager, settings_local):
    servico = ValidateService(
        manager_api=manager,
        importer=LocalFileImporterAdapter(),
        settings=settings_local,
    )
    return lambda file_path: servico.validate(file_path, confirm=lambda _: True)


@pytest.fixture(autouse=True)
def restaurar(request, manager, backup, draft_id):
    """Restaura a Draft com um `PUT` do payload do backup.

    **Não** republica o repositório baseline. Sob a V-26 isso nem funcionava: o
    baseline declarava `inherit: true` com lista vazia, lista vazia **herda** em
    vez de zerar, e o append do cenário sobrevivia — foi assim que T07, T08 e
    T11 deixaram 5 interceptors a mais depois de uma execução inteira.

    A V-27 resolveria esse caso (o baseline passaria a mandar `[]` e o escopo
    voltaria a herdar), mas republicar continua sendo restauração **derivada**:
    reconstrói o estado a partir do repositório em vez de devolver o que foi
    medido. Só o `PUT` do payload capturado é fiel ao que estava lá.
    """
    yield
    if request.node.get_closest_marker("sem_escrita"):
        return
    manager.update_revision(draft_id, copy.deepcopy(backup["revisions"][str(draft_id)]))


def _reler(manager, draft_id):
    return manager.get_revision(draft_id)


def _operacoes(revision):
    return {
        (r.get("name"), str(o.get("method") or "").upper(), o.get("path"))
        for r in (revision.get("resources") or [])
        for o in (r.get("operations") or [])
    }


def _recurso(revision, name):
    for r in revision.get("resources") or []:
        if r.get("name") == name:
            return r
    return {}


def _operacao(revision, method, path):
    for r in revision.get("resources") or []:
        for o in r.get("operations") or []:
            if str(o.get("method") or "").upper() == method and o.get("path") == path:
                return o
    return {}


def _governed(no):
    return partition((no or {}).get("interceptors"))[0]


def _live(no):
    return [i for i in _governed(no) if i.get("status") != "REMOVED"]


def _marcacoes(no):
    return [i for i in _governed(no) if i.get("status") == "REMOVED"]


def _write(file_path: pathlib.Path, text: str):
    file_path.write_text(text, encoding="utf-8")


def _arquivo_da_rota(repo: pathlib.Path, path: str) -> pathlib.Path:
    """Arquivo de operação que declara `path`, onde quer que esteja a pasta."""
    for file in repo.joinpath("resources").rglob("*.yaml"):
        if f"path: {path}\n" in file.read_text(encoding="utf-8"):
            return file
    raise AssertionError(f"nenhum arquivo declara a rota {path}")


# --------------------------------------------------------------------- T01..T11


def test_T01_description_da_api_replica(repo, validate, manager, draft_id):
    manifesto = repo / "api-basic-info.yaml"
    new = "Descricao EDITADA pela bateria de aceitacao do APIOps."
    conteudo = manifesto.read_text(encoding="utf-8")
    inicio = conteudo.index("  description:")
    fim = conteudo.index("  template:")
    _write(manifesto, conteudo[:inicio] + f'  description: "{new}"\n' + conteudo[fim:])

    validate(repo)

    assert manager.get_api_by_id(API_ID).get("description") == new


@pytest.mark.sem_escrita
def test_T02_basepath_divergente_aborta_sem_escrever(repo, validate, manager, draft_id):
    antes = _reler(manager, draft_id)
    manifesto = repo / "api-basic-info.yaml"
    _write(
        manifesto,
        manifesto.read_text(encoding="utf-8").replace("/letras/v2", "/letras/v9"),
    )

    with pytest.raises(IdentityMismatchError):
        validate(repo)

    assert manager.get_api_by_id(API_ID).get("basePath") == "/letras/v2"
    assert _operacoes(_reler(manager, draft_id)) == _operacoes(antes)


@pytest.mark.sem_escrita
def test_T03_governanca_bloqueia_e_a_tag_permanece(repo, validate, manager):
    manifesto = repo / "api-basic-info.yaml"
    conteudo = manifesto.read_text(encoding="utf-8")
    inicio = conteudo.index("  apiTags:")
    _write(
        manifesto,
        conteudo[:inicio]
        + '  apiTags:\n    - attributeName: "teste giroto"\n      tags: ["teste giroto"]\n',
    )

    with pytest.raises(GovernanceBlockedError) as capturado:
        validate(repo)

    assert capturado.value.exit_code == 3
    assert "My new" in capturado.value.message
    tags = {t.get("attributeName") for t in (manager.get_api_by_id(API_ID).get("apiTags") or [])}
    assert "My new" in tags, "o pré-check barrou ANTES de escrever: a tag continua"


def test_T04_destination_de_operacao_replica(repo, validate, manager, draft_id):
    file = repo / "resources" / "tarefas" / "get_tarefas.yaml"
    new = "https://dev-backend.ecad.org.br/EDITADO-PELA-BATERIA/tarefas"
    conteudo = file.read_text(encoding="utf-8")
    lines = [
        f"  url: {new}" if l.strip().startswith("url:") else l
        for l in conteudo.split("\n")
    ]
    _write(file, "\n".join(lines))

    validate(repo)

    assert _operacao(_reler(manager, draft_id), "GET", "/tarefas").get("destination") == new


def test_T05_rota_nova_nasce_sem_id_e_herda_por_lista_vazia(repo, validate, manager, draft_id):
    folder = repo / "resources" / "musicas"
    folder.mkdir(parents=True)
    _write(folder / "resource.yaml", 'name: "Musicas"\ninherit: true\n')
    _write(
        folder / "get_musicas.yaml",
        "path: /musicas\ndestination:\n  url: https://dev-backend.ecad.org.br/musicas\ninherit: true\n",
    )

    validate(repo)

    after = _reler(manager, draft_id)
    assert ("Musicas", "GET", "/musicas") in _operacoes(after)
    assert len(_governed(_operacao(after, "GET", "/musicas"))) == 0
    assert len(_governed(after)) > 0, "a raiz mantém o fluxo"


def test_T06_inherit_false_sem_itens_e_escopo_sem_interceptors(
    repo, validate, manager, draft_id
):
    """Marcar todo o herdado sem itens próprios dá escopo sem fluxo (V-28)."""
    resource = repo / "resources" / "letras" / "resource.yaml"
    _write(
        resource,
        resource.read_text(encoding="utf-8").replace("inherit: true", "inherit: false"),
    )
    route = repo / "resources" / "letras" / "post_tarefas_{id}_letras.yaml"
    _write(
        route, route.read_text(encoding="utf-8").replace("inherit: true", "inherit: false")
    )

    validate(repo)

    after = _reler(manager, draft_id)
    letras = _recurso(after, "Letras")
    assert _live(letras) == []
    assert len(_marcacoes(letras)) == len(_live(after)), "uma marcação por item da raiz"
    # O recurso não executa nada: a rota não tem o que marcar.
    assert _governed(_operacao(after, "POST", "/tarefas/{id}/letras")) == []


def test_T07_interceptors_no_recurso_nao_sao_copiados_para_as_rotas(
    repo, validate, manager, draft_id
):
    resource = _arquivo_da_rota(repo, "/tarefas").parent / "resource.yaml"
    _write(
        resource,
        'name: "Tarefas"\ninherit: false\n\ninterceptors_request:\n'
        "  - type: Custom\n    id: 32\n"
        "  - type: Payload size\n    content:\n      maxSize: 2048\n",
    )

    validate(repo)

    after = _reler(manager, draft_id)
    owner = next(
        r for r in after.get("resources") or []
        if any(o.get("path") == "/tarefas" for o in r.get("operations") or [])
    )
    assert len(_live(owner)) == 2
    assert len(_marcacoes(owner)) == len(_live(after))
    assert _governed(_operacao(after, "GET", "/tarefas")) == []


def test_T08_interceptors_declarados_na_rota_sobem(repo, validate, manager, draft_id):
    route = _arquivo_da_rota(repo, "/tarefas/{id}")
    _write(
        route,
        "path: /tarefas/{id}\ninherit: false\n\ninterceptors_request:\n"
        "  - type: Custom\n    id: 33\n"
        "  - type: Log\n    content:\n      acceptedTerms: true\n",
    )

    validate(repo)

    after = _reler(manager, draft_id)
    operacao = _operacao(after, "GET", "/tarefas/{id}")
    assert {i.get("type") for i in _live(operacao)} == {"Custom", "Log"}
    # O recurso dela só herda: a rota marca cada item da raiz.
    assert len(_marcacoes(operacao)) == len(_live(after))


def test_T10_arquivo_removido_remove_a_rota(repo, validate, manager, draft_id):
    (repo / "resources" / "letras" / "delete_letras_{id}.yaml").unlink()

    validate(repo)

    after = _reler(manager, draft_id)
    assert ("Letras", "DELETE", "/letras/{id}") not in _operacoes(after)
    assert len(_recurso(after, "Letras").get("operations") or []) == 1


_APPEND = (
    "\n\ninterceptors_request:\n  - type: Payload size\n    content:\n      maxSize: 2048\n"
)
_ROTA_LETRAS = ("resources", "letras", "post_tarefas_{id}_letras.yaml")


def test_T11_append_guarda_so_o_item_declarado(repo, validate, manager, draft_id):
    """A plataforma soma o herdado sozinha: copiá-lo na rota o executaria duas
    vezes (V-28). O ✅ original do caderno estava certo."""
    route = repo.joinpath(*_ROTA_LETRAS)
    _write(route, route.read_text(encoding="utf-8").rstrip() + _APPEND)

    validate(repo)

    operacao = _operacao(_reler(manager, draft_id), "POST", "/tarefas/{id}/letras")
    assert [i.get("type") for i in _live(operacao)] == ["Payload size"]
    assert _marcacoes(operacao) == []


def test_T12_restaurar_heranca_e_acrescentar_na_mesma_declaracao(
    repo, validate, manager, draft_id
):
    """Primeiro quebra a herança da rota; depois declara `inherit: true` com um
    item. As marcações e o item obsoleto saem, e só o item novo fica guardado."""
    route = repo.joinpath(*_ROTA_LETRAS)
    cabecalho = "path: /tarefas/{id}/letras\n"

    # 1. quebra: a rota passa a executar só o XSS.
    _write(
        route,
        cabecalho + "inherit: false\n\ninterceptors_request:\n"
        "  - type: XSS threat protection\n    content: {}\n",
    )
    validate(repo)
    after = _reler(manager, draft_id)
    antes = _operacao(after, "POST", "/tarefas/{id}/letras")
    assert [i.get("type") for i in _live(antes)] == ["XSS threat protection"]
    assert len(_marcacoes(antes)) == len(_live(after))

    # 2. restaura a herança E acrescenta, numa só declaração.
    _write(route, cabecalho + "inherit: true" + _APPEND)
    validate(repo)

    operacao = _operacao(_reler(manager, draft_id), "POST", "/tarefas/{id}/letras")
    assert [i.get("type") for i in _live(operacao)] == ["Payload size"]
    assert _marcacoes(operacao) == []


# --------------------------------------------------------------------- baseline


@pytest.mark.sem_escrita
def test_ZZ_estado_final_identico_ao_baseline(backup, manager, draft_id):
    """Roda por último: o alfabeto garante a ordem dentro do módulo."""
    antes = backup["revisions"][str(draft_id)]
    after = _reler(manager, draft_id)
    api = manager.get_api_by_id(API_ID)

    assert api.get("name") == backup["api"].get("name")
    assert api.get("basePath") == backup["api"].get("basePath")
    assert api.get("version") == backup["api"].get("version")
    assert {t.get("attributeName") for t in (api.get("apiTags") or [])} == {
        t.get("attributeName") for t in (backup["api"].get("apiTags") or [])
    }
    assert _operacoes(after) == _operacoes(antes)
    assert len(_governed(after)) == len(_governed(antes))
    for resource in antes.get("resources") or []:
        name = resource.get("name")
        assert len(_governed(_recurso(after, name))) == len(_governed(resource)), name
