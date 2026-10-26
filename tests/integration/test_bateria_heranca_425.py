"""Bateria de herança contra a API-lab 425 (ESCREVE na Draft e faz deploy no ambiente 7).

Mede o que cada rota **executa**, não só o que o Manager guarda
([V-28](../../docs/feat-api-estructure/decisoes-refino-409/V-28-heranca-composta-pela-plataforma.md)).
Cada interceptor é um `Header` que injeta `X-Lab-<rótulo>`; o destino é um eco
(httpbin), e o trace da chamada (`GET /calls/{id}`) dá quantos interceptors
executaram e, pelos headers na ordem de inserção, em que ordem.

**Não roda por padrão.** Exige `APIOPS_BATERIA_425=1` e sessão válida do
consulting (`sen login`). As fases rodam em ordem: cada uma publica o repositório
inteiro, faz deploy e mede. A Draft é restaurada ao fim.
"""

import copy
import datetime
import json
import os
import time

import pytest
import requests
import yaml

from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
    LocalFileImporterAdapter,
)
from apiops_orchestrator.application.services.validate_service import ValidateService
from apiops_orchestrator.domain.services import repo_layout as layout
from apiops_orchestrator.domain.services.repo_materializer import materializar

API_ID = 425
AMBIENTE = 7
REGUA = 414
GATEWAY = "https://api-consulting.sensedia.com/cli/apiops-lab-heranca/v1"
DESTINO = "https://httpbin.org/anything"

pytestmark = pytest.mark.skipif(
    os.environ.get("APIOPS_BATERIA_425") != "1",
    reason="bateria que ESCREVE na API-lab 425; exige APIOPS_BATERIA_425=1",
)


# --------------------------------------------------------------------- arnês


@pytest.fixture(scope="module")
def manager():
    from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
        ManagerApiAdapter,
    )
    from apiops_orchestrator.main import _build_admin_token, _load_settings

    settings = _load_settings()
    return ManagerApiAdapter(
        token=_build_admin_token(settings),
        base_path="/api-manager/api/v3/",
        max_retries=3,
        settings=settings,
    )


@pytest.fixture(scope="module")
def lab(manager, tmp_path_factory):
    """API, id da Draft e backup; restaura a Draft ao fim do módulo.

    A restauração é pelo swagger exportado: as fases apagam recursos, e o
    backup da revisão apontaria ids que deixaram de existir. O swagger recria a
    árvore sem ids (V-28 §7).
    """
    api = manager.get_api_by_id(API_ID)
    draft_id = next(r["id"] for r in api["revisions"] if r["revisionNumber"] == 1)
    backup = manager.get_revision(draft_id)
    swagger = manager._request("GET", f"revisions/{draft_id}/swagger")
    destino = tmp_path_factory.mktemp("backup") / "backup-425.json"
    destino.write_text(
        json.dumps({"revision": backup, "swagger": swagger}, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n[arnês] backup em {destino}")
    yield {"api": api, "draft_id": draft_id, "backup": backup}
    manager._request("PUT", f"revisions/{draft_id}/swagger", json=copy.deepcopy(swagger))


@pytest.fixture(scope="module")
def validar(manager):
    from apiops_orchestrator.main import _load_settings

    settings = _load_settings()
    assert not settings.modo_pipeline, "a bateria roda em modo local, na Draft"
    servico = ValidateService(
        manager_api=manager, importer=LocalFileImporterAdapter(), settings=settings
    )

    def _validar(caminho):
        perguntas = []
        view = servico.validate(caminho, confirmar=lambda texto: perguntas.append(texto) or True)
        return view, "\n".join(perguntas)

    return _validar


def _header(rotulo):
    return {
        "type": "Header",
        "content": {
            "headerList": [
                {"name": f"X-Lab-{rotulo}", "tokenType": "CUSTOM", "attribute": rotulo},
                {"name": "X-Lab-Ordem", "tokenType": "CUSTOM", "attribute": rotulo},
            ],
            "ignoreBodyValidationMultiPartFormData": False,
        },
    }


def _bloco(inherit, rotulos):
    bloco = {} if inherit is None else {"inherit": inherit}
    if rotulos:
        bloco["interceptors_request"] = [_header(r) for r in rotulos]
    return bloco


def _escrever(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        yaml.safe_dump(dados, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def _repo(tmp_path, lab, raiz, recursos):
    """Repositório inteiro: `raiz` são rótulos; `recursos` é
    `{pasta: (nome, inherit, rótulos, {path: (inherit, rótulos)})}`."""
    basic_info = next(
        a for a in materializar(lab["api"], lab["backup"]).arquivos
        if a.caminho == layout.ARQUIVO_BASIC_INFO
    )
    (tmp_path / layout.ARQUIVO_BASIC_INFO).write_text(
        basic_info.texto.replace("template: ''", f"template: {REGUA}"), encoding="utf-8"
    )
    _escrever(tmp_path / layout.ARQUIVO_RAIZ, {"destination": {"url": DESTINO}, **_bloco(None, raiz)})
    for pasta, (nome, inherit, rotulos, rotas) in recursos.items():
        base = tmp_path / layout.PASTA_RECURSOS / pasta
        _escrever(base / layout.ARQUIVO_RECURSO, {"name": nome, **_bloco(inherit, rotulos)})
        for path, (inherit_rota, rotulos_rota) in rotas.items():
            arquivo = base / f"get{path.replace('/', '_')}.yaml"
            _escrever(
                arquivo,
                {
                    "path": path,
                    **_bloco(inherit_rota, rotulos_rota),
                    "responses": {"200": {"description": "OK"}},
                },
            )
    return tmp_path


# --------------------------------------------------------------------- medição


def _chamadas(manager, inicio, path):
    """Chamadas da rota desde `inicio`, pelo trace do Manager (sem método no port)."""
    fim = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=5)
    resposta = manager._request("GET", "calls", params={
        "actualPage": 1, "pageSize": 5, "apiId": API_ID, "uri": path,
        "beginDate": inicio.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endDate": fim.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "environmentId": "", "httpResponse": -2, "operationId": "", "regex": "",
        "resourceId": "", "revisionId": "",
    })
    return [c for c in resposta.get("calls") or [] if (c.get("uri") or "").endswith(path)]


def _execucao(manager, chamada):
    """Rótulos executados, na ordem, e quantas execuções de interceptor houve."""
    detalhe = manager._request(
        "GET", f"calls/{chamada['id']}", params={"yearMonth": chamada["yearMonth"]}
    )
    trace = json.loads(detalhe.get("trace") or "[]")
    execucoes = sum(
        1 for t in trace
        if t["message"].startswith("Executing ") and t["message"].endswith(" Interceptor")
    )
    ordem = []
    for linha in (detalhe.get("requestHeaders") or "").splitlines():
        chave, _, valor = linha.partition(": ")
        if chave.startswith("x-lab-") and chave != "x-lab-ordem" and valor not in ordem:
            ordem.append(valor)
    return ordem, execucoes


def _medir(manager, paths):
    inicio = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=5)
    for path in paths:
        requests.get(f"{GATEWAY}{path}", timeout=30)
    resultado = {}
    for path in paths:
        for _ in range(9):
            chamadas = _chamadas(manager, inicio, path)
            if chamadas:
                break
            time.sleep(10)
        assert chamadas, f"a chamada a {path} não apareceu no trace"
        resultado[path] = _execucao(manager, max(chamadas, key=lambda c: c["receivedOn"]))
    return resultado


def _deploy_e_conferir(manager, lab, esperado):
    """Deploy da Draft e medição até o gateway refletir a revisão publicada."""
    manager.deploy_revision(AMBIENTE, lab["draft_id"])
    obtido = {}
    for _ in range(4):
        time.sleep(20)
        obtido = _medir(manager, list(esperado))
        if all(obtido[p] == (esperado[p], len(esperado[p])) for p in esperado):
            return
    divergentes = {
        p: {"esperado": esperado[p], "obtido": obtido[p]}
        for p in esperado if obtido[p] != (esperado[p], len(esperado[p]))
    }
    pytest.fail(f"execução diferente da esperada: {divergentes}")


# --------------------------------------------------------------------- fases


def test_1_heranca_nos_tres_niveis(tmp_path, lab, validar, manager):
    """Raiz R1, R2. Recurso que herda, que quebra e que acrescenta, com rotas que
    herdam, acrescentam, quebram e quebram sem itens."""
    repo = _repo(tmp_path, lab, ["R1", "R2"], {
        "heranca": ("Heranca", True, [], {
            "/s1-pura": (True, []),
            "/s2-append": (True, ["S2"]),
            "/s5-quebra": (False, ["S5"]),
            "/s7-vazia": (False, []),
        }),
        "quebra": ("Quebra", False, ["C1"], {
            "/c1-pura": (True, []),
            "/c3-quebra": (False, ["C3"]),
        }),
        "append": ("Append", True, ["B1"], {
            "/b2-append": (True, ["B2"]),
            "/b3-quebra": (False, ["B3"]),
        }),
    })

    view, _ = validar(repo)
    assert view.publicacao.verified, view.publicacao.divergences

    _deploy_e_conferir(manager, lab, {
        "/s1-pura": ["R1", "R2"],
        "/s2-append": ["R1", "R2", "S2"],
        "/s5-quebra": ["S5"],
        "/s7-vazia": [],
        "/c1-pura": ["C1"],
        "/c3-quebra": ["C3"],
        "/b2-append": ["R1", "R2", "B1", "B2"],
        "/b3-quebra": ["B3"],
    })


def test_2_item_novo_no_pai_na_mesma_publicacao(tmp_path, lab, validar, manager):
    """R3 entra na raiz e C5 no recurso que quebra: as rotas que quebram já não
    os executam nesta publicação (marcação por `idTemp`)."""
    repo = _repo(tmp_path, lab, ["R1", "R2", "R3"], {
        "heranca": ("Heranca", True, [], {
            "/s1-pura": (True, []),
            "/s2-append": (True, ["S2"]),
            "/s5-quebra": (False, ["S5"]),
            "/s7-vazia": (False, []),
        }),
        "quebra": ("Quebra", False, ["C1", "C5"], {
            "/c1-pura": (True, []),
            "/c3-quebra": (False, ["C3"]),
        }),
        "append": ("Append", True, ["B1"], {
            "/b2-append": (True, ["B2"]),
            "/b3-quebra": (False, ["B3"]),
        }),
    })

    view, pergunta = validar(repo)
    assert view.publicacao.verified, view.publicacao.divergences
    assert "rode o comando de novo" not in pergunta.lower()

    _deploy_e_conferir(manager, lab, {
        "/s1-pura": ["R1", "R2", "R3"],
        "/s5-quebra": ["S5"],
        "/s7-vazia": [],
        "/c1-pura": ["C1", "C5"],
        "/c3-quebra": ["C3"],
        "/b2-append": ["R1", "R2", "R3", "B1", "B2"],
        "/b3-quebra": ["B3"],
    })


def test_3_volta_a_herdar_item_sai_do_pai_e_corte_avisado(tmp_path, lab, validar, manager):
    """R2 sai da raiz; `s5` volta a herdar; `s1` passa a quebrar e o comando
    avisa o herdado que ela deixa de executar (só R1 e R3: R2 saiu do pai)."""
    repo = _repo(tmp_path, lab, ["R1", "R3"], {
        "heranca": ("Heranca", True, [], {
            "/s1-pura": (False, ["S1"]),
            "/s2-append": (True, ["S2"]),
            "/s5-quebra": (True, []),
            "/s7-vazia": (False, []),
        }),
        "quebra": ("Quebra", False, ["C1", "C5"], {
            "/c1-pura": (True, []),
            "/c3-quebra": (False, ["C3"]),
        }),
        "append": ("Append", True, ["B1"], {
            "/b2-append": (True, ["B2"]),
            "/b3-quebra": (False, ["B3"]),
        }),
    })

    view, pergunta = validar(repo)
    assert view.publicacao.verified, view.publicacao.divergences
    assert "GET /s1-pura: o arquivo declara `inherit: false`, e ao publicar este ponto " \
           "deixa de executar 2 interceptor(es)" in pergunta
    assert pergunta.count("deixa de executar") == 1

    _deploy_e_conferir(manager, lab, {
        "/s1-pura": ["S1"],
        "/s2-append": ["R1", "R3", "S2"],
        "/s5-quebra": ["R1", "R3"],
        "/s7-vazia": [],
        "/c1-pura": ["C1", "C5"],
        "/b2-append": ["R1", "R3", "B1", "B2"],
        "/b3-quebra": ["B3"],
    })
