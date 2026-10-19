"""Bateria de aceitação do `sen validate` contra a API 417 (ESCREVE na Draft).

Reproduz os cenários do
[caderno de testes](../../docs/feat-api-estructure/prova-fluxo-validate/CADERNO-DE-TESTES.md),
agora através do comando implementado em vez do protótipo.

O **T11 teve o oráculo corrigido** e o **T12 é novo**: ambos cobrem a
[V-27](../../docs/feat-api-estructure/decisoes-refino-409/V-27-fluxo-resolvido-no-repositorio.md),
que tirou a resolução da herança da plataforma. O T11 original passava verde com
a rota executando só o item acrescentado — o append apagava o herdado.

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
    IdentidadeDivergenteError,
)
from apiops_orchestrator.application.services.validate_service import ValidateService
from apiops_orchestrator.domain.services.interceptor_flow import particionar
from apiops_orchestrator.domain.services.repo_materializer import materializar

API_ID = 417
REVISAO_DRAFT = 1

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
    assert not settings.modo_pipeline, "a bateria roda em modo local"
    # Ausente vale como Draft em modo local.
    assert (settings.TARGET_REVISION_NUMBER or REVISAO_DRAFT) == REVISAO_DRAFT
    return settings


@pytest.fixture(scope="module")
def backup(manager, tmp_path_factory):
    """Backup completo ANTES da primeira escrita, gravado em disco."""
    api = manager.get_api_by_id(API_ID)
    dados = {"api": api, "revisions": {}}
    for revisao in api.get("revisions") or []:
        dados["revisions"][str(revisao["id"])] = manager.get_revision(revisao["id"])

    destino = tmp_path_factory.mktemp("backup") / "backup-417.json"
    destino.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[arnês] backup em {destino}")
    return dados


@pytest.fixture(scope="module")
def draft_id(backup):
    for revisao in backup["api"].get("revisions") or []:
        if revisao.get("revisionNumber") == REVISAO_DRAFT:
            return revisao["id"]
    pytest.fail("a API 417 não tem revisão de número 1 (Draft)")


@pytest.fixture(scope="module")
def baseline_repo(backup, draft_id, tmp_path_factory):
    """Materializa a PRÓPRIA Draft: publicá-la de volta é um no-op."""
    draft = backup["revisions"][str(draft_id)]
    resultado = materializar(backup["api"], draft)

    raiz = tmp_path_factory.mktemp("baseline") / "repo"
    for arquivo in resultado.arquivos:
        destino = raiz / arquivo.caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(arquivo.texto, encoding="utf-8")

    # A régua não vem do wire (D-12): o manifesto precisa declará-la.
    manifesto = raiz / "api-basic-info.yaml"
    manifesto.write_text(
        manifesto.read_text(encoding="utf-8").replace("template: ''", "template: 414"),
        encoding="utf-8",
    )
    return raiz


@pytest.fixture
def repo(baseline_repo, tmp_path):
    """Cópia fresca do baseline para cada cenário."""
    alvo = tmp_path / "repo"
    shutil.copytree(baseline_repo, alvo)
    return alvo


@pytest.fixture
def validar(manager, settings_local):
    servico = ValidateService(
        manager_api=manager,
        importer=LocalFileImporterAdapter(),
        settings=settings_local,
    )
    return lambda caminho: servico.validate(caminho, confirmar=lambda _: True)


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


def _operacoes(revisao):
    return {
        (r.get("name"), str(o.get("method") or "").upper(), o.get("path"))
        for r in (revisao.get("resources") or [])
        for o in (r.get("operations") or [])
    }


def _recurso(revisao, nome):
    for r in revisao.get("resources") or []:
        if r.get("name") == nome:
            return r
    return {}


def _operacao(revisao, metodo, path):
    for r in revisao.get("resources") or []:
        for o in r.get("operations") or []:
            if str(o.get("method") or "").upper() == metodo and o.get("path") == path:
                return o
    return {}


def _governados(no):
    return particionar((no or {}).get("interceptors"))[0]


def _escrever(caminho: pathlib.Path, texto: str):
    caminho.write_text(texto, encoding="utf-8")


# --------------------------------------------------------------------- T01..T11


def test_T01_description_da_api_replica(repo, validar, manager, draft_id):
    manifesto = repo / "api-basic-info.yaml"
    novo = "Descricao EDITADA pela bateria de aceitacao do APIOps."
    conteudo = manifesto.read_text(encoding="utf-8")
    inicio = conteudo.index("  description:")
    fim = conteudo.index("  template:")
    _escrever(manifesto, conteudo[:inicio] + f'  description: "{novo}"\n' + conteudo[fim:])

    validar(repo)

    assert manager.get_api_by_id(API_ID).get("description") == novo


@pytest.mark.sem_escrita
def test_T02_basepath_divergente_aborta_sem_escrever(repo, validar, manager, draft_id):
    antes = _reler(manager, draft_id)
    manifesto = repo / "api-basic-info.yaml"
    _escrever(
        manifesto,
        manifesto.read_text(encoding="utf-8").replace("/letras/v2", "/letras/v9"),
    )

    with pytest.raises(IdentidadeDivergenteError):
        validar(repo)

    assert manager.get_api_by_id(API_ID).get("basePath") == "/letras/v2"
    assert _operacoes(_reler(manager, draft_id)) == _operacoes(antes)


@pytest.mark.sem_escrita
def test_T03_governanca_bloqueia_e_a_tag_permanece(repo, validar, manager):
    manifesto = repo / "api-basic-info.yaml"
    conteudo = manifesto.read_text(encoding="utf-8")
    inicio = conteudo.index("  apiTags:")
    _escrever(
        manifesto,
        conteudo[:inicio]
        + '  apiTags:\n    - attributeName: "teste giroto"\n      tags: ["teste giroto"]\n',
    )

    with pytest.raises(GovernanceBlockedError) as capturado:
        validar(repo)

    assert capturado.value.exit_code == 3
    assert "My new" in capturado.value.message
    tags = {t.get("attributeName") for t in (manager.get_api_by_id(API_ID).get("apiTags") or [])}
    assert "My new" in tags, "o pré-check barrou ANTES de escrever: a tag continua"


def test_T04_destination_de_operacao_replica(repo, validar, manager, draft_id):
    arquivo = repo / "resources" / "tarefas" / "get_tarefas.yaml"
    novo = "https://dev-backend.ecad.org.br/EDITADO-PELA-BATERIA/tarefas"
    conteudo = arquivo.read_text(encoding="utf-8")
    linhas = [
        f"  url: {novo}" if l.strip().startswith("url:") else l
        for l in conteudo.split("\n")
    ]
    _escrever(arquivo, "\n".join(linhas))

    validar(repo)

    assert _operacao(_reler(manager, draft_id), "GET", "/tarefas").get("destination") == novo


def test_T05_rota_nova_nasce_sem_id_e_herda_por_lista_vazia(repo, validar, manager, draft_id):
    pasta = repo / "resources" / "musicas"
    pasta.mkdir(parents=True)
    _escrever(pasta / "resource.yaml", 'name: "Musicas"\ninherit: true\n')
    _escrever(
        pasta / "get_musicas.yaml",
        "path: /musicas\ndestination:\n  url: https://dev-backend.ecad.org.br/musicas\ninherit: true\n",
    )

    validar(repo)

    depois = _reler(manager, draft_id)
    assert ("Musicas", "GET", "/musicas") in _operacoes(depois)
    assert len(_governados(_operacao(depois, "GET", "/musicas"))) == 0
    assert len(_governados(depois)) > 0, "a raiz mantém o fluxo"


def test_T06_lista_vazia_herda_nao_zera(repo, validar, manager, draft_id):
    """O achado mais valioso do caderno: 'rota sem fluxo' não existe."""
    recurso = repo / "resources" / "letras" / "resource.yaml"
    _escrever(
        recurso,
        recurso.read_text(encoding="utf-8").replace("inherit: true", "inherit: false"),
    )
    rota = repo / "resources" / "letras" / "post_tarefas_{id}_letras.yaml"
    _escrever(
        rota, rota.read_text(encoding="utf-8").replace("inherit: true", "inherit: false")
    )

    validar(repo)

    depois = _reler(manager, draft_id)
    assert len(_governados(_recurso(depois, "Letras"))) == 0
    assert len(_governados(_operacao(depois, "POST", "/tarefas/{id}/letras"))) == 0
    assert len(_governados(depois)) > 0, "a raiz continua com o fluxo que as rotas herdam"


def test_T07_interceptors_no_recurso_nao_sao_copiados_para_as_rotas(
    repo, validar, manager, draft_id
):
    recurso = repo / "resources" / "tarefas" / "resource.yaml"
    _escrever(
        recurso,
        'name: "Tarefas"\ninherit: false\n\ninterceptors_request:\n'
        "  - type: Custom\n    id: 32\n"
        "  - type: Payload size\n    content:\n      maxSize: 2048\n",
    )

    validar(repo)

    depois = _reler(manager, draft_id)
    assert len(_governados(_recurso(depois, "Tarefas"))) == 2
    assert len(_governados(_operacao(depois, "GET", "/tarefas"))) == 0


def test_T08_interceptors_declarados_na_rota_sobem(repo, validar, manager, draft_id):
    rota = repo / "resources" / "tarefas" / "get_tarefas_{id}.yaml"
    _escrever(
        rota,
        "path: /tarefas/{id}\ninherit: false\n\ninterceptors_request:\n"
        "  - type: Custom\n    id: 33\n"
        "  - type: Log\n    content:\n      acceptedTerms: true\n",
    )

    validar(repo)

    itens = _governados(_operacao(_reler(manager, draft_id), "GET", "/tarefas/{id}"))
    assert {i.get("type") for i in itens} == {"Custom", "Log"}


def test_T10_arquivo_removido_remove_a_rota(repo, validar, manager, draft_id):
    (repo / "resources" / "letras" / "delete_letras_{id}.yaml").unlink()

    validar(repo)

    depois = _reler(manager, draft_id)
    assert ("Letras", "DELETE", "/letras/{id}") not in _operacoes(depois)
    assert len(_recurso(depois, "Letras").get("operations") or []) == 1


_APPEND = (
    "\n\ninterceptors_request:\n  - type: Payload size\n    content:\n      maxSize: 2048\n"
)
_ROTA_LETRAS = ("resources", "letras", "post_tarefas_{id}_letras.yaml")


def test_T11_append_soma_ao_herdado_em_vez_de_substitui_lo(
    repo, validar, manager, draft_id
):
    """O oráculo que faltava — e que deixou o defeito da V-27 passar verde.

    A versão anterior perguntava "a rota ganhou o item?" e passava com a rota
    executando **só** ele: pela W-4 a lista própria não vazia É o fluxo inteiro,
    então o append apagava o herdado sob HTTP 200. A pergunta certa é "a rota
    continua executando o que herdava?".
    """
    herdado = [i.get("type") for i in _governados(_reler(manager, draft_id))]
    assert len(herdado) > 1, "o cenário só vale se a raiz tiver fluxo para herdar"

    rota = repo.joinpath(*_ROTA_LETRAS)
    _escrever(rota, rota.read_text(encoding="utf-8").rstrip() + _APPEND)

    validar(repo)

    tipos = [
        i.get("type")
        for i in _governados(
            _operacao(_reler(manager, draft_id), "POST", "/tarefas/{id}/letras")
        )
    ]
    assert "Payload size" in tipos
    assert len(tipos) == len(herdado) + 1, (
        f"o append tem de PRESERVAR o herdado: esperado {len(herdado)} + 1, veio {tipos}"
    )


def test_T12_restaurar_heranca_e_acrescentar_na_mesma_declaracao(
    repo, validar, manager, draft_id
):
    """O pedido que a V-26 não expressava (V-27 §4).

    Primeiro quebra a herança da rota, deixando-a com lista própria obsoleta.
    Depois declara `inherit: true` **com** um item — que sob a V-26 somaria à
    lista obsoleta, e sob a V-27 significa "o fluxo do pai, mais este item".
    """
    herdado = [i.get("type") for i in _governados(_reler(manager, draft_id))]
    rota = repo.joinpath(*_ROTA_LETRAS)
    cabecalho = "path: /tarefas/{id}/letras\n"

    # 1. quebra: a rota passa a executar só o XSS.
    _escrever(
        rota,
        cabecalho + "inherit: false\n\ninterceptors_request:\n"
        "  - type: XSS threat protection\n    content: {}\n",
    )
    validar(repo)
    antes = _governados(_operacao(_reler(manager, draft_id), "POST", "/tarefas/{id}/letras"))
    assert [i.get("type") for i in antes] == ["XSS threat protection"]

    # 2. restaura a herança E acrescenta, numa só declaração.
    _escrever(rota, cabecalho + "inherit: true" + _APPEND)
    validar(repo)

    tipos = [
        i.get("type")
        for i in _governados(
            _operacao(_reler(manager, draft_id), "POST", "/tarefas/{id}/letras")
        )
    ]
    assert tipos == herdado + ["Payload size"], (
        "a herança tinha de voltar do repositório, sem o XSS obsoleto: " f"{tipos}"
    )


# --------------------------------------------------------------------- baseline


@pytest.mark.sem_escrita
def test_ZZ_estado_final_identico_ao_baseline(backup, manager, draft_id):
    """Roda por último: o alfabeto garante a ordem dentro do módulo."""
    antes = backup["revisions"][str(draft_id)]
    depois = _reler(manager, draft_id)
    api = manager.get_api_by_id(API_ID)

    assert api.get("name") == backup["api"].get("name")
    assert api.get("basePath") == backup["api"].get("basePath")
    assert api.get("version") == backup["api"].get("version")
    assert {t.get("attributeName") for t in (api.get("apiTags") or [])} == {
        t.get("attributeName") for t in (backup["api"].get("apiTags") or [])
    }
    assert _operacoes(depois) == _operacoes(antes)
    assert len(_governados(depois)) == len(_governados(antes))
    for recurso in antes.get("resources") or []:
        nome = recurso.get("name")
        assert len(_governados(_recurso(depois, nome))) == len(_governados(recurso)), nome
