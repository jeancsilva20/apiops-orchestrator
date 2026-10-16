"""Oracle da materialização: APIs reais → árvore canônica, byte a byte.

As fixtures em `tests/fixtures/manager/` são payloads **reais** do Manager
(APIs 417 e 400), higienizados: carregam apenas os campos que o materializador
consome, e o `content` dos interceptors `Custom` foi retirado — é script interno
do tenant, e o materializador não o usa, porque referencia por
`customInterceptorId`.

Esse par (fixture, árvore commitada) é o que protege a reescrita: qualquer
mudança de nomenclatura, de serialização ou de regime de herança aparece como
diferença de texto, não como teste verde enganoso.
"""

import json
import pathlib

import pytest
import yaml

from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
    LocalFileImporterAdapter,
)
from apiops_orchestrator.application.services.repo_importer_service import (
    RepoCanonicalReader,
)
from apiops_orchestrator.domain.services.repo_materializer import materializar

RAIZ = pathlib.Path(__file__).parents[3]
FIXTURES = RAIZ / "fixtures" / "manager"
EXEMPLOS = (
    RAIZ.parent
    / "docs"
    / "feat-api-estructure"
    / "decisoes-refino-409"
    / "exemplos-gerados"
    / "saida"
)

CASOS = [("api-417-rev2", 4, 7, 13), ("api-400-rev4", 2, 4, 8)]


def _carregar_fixture(nome):
    return json.loads((FIXTURES / f"{nome}.json").read_text(encoding="utf-8"))


def _arvore_commitada(nome):
    base = EXEMPLOS / nome
    return {
        str(p.relative_to(base)).replace("\\", "/"): p.read_text(encoding="utf-8")
        for p in base.rglob("*.yaml")
    }


@pytest.mark.parametrize("nome,recursos,operacoes,arquivos", CASOS)
@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_materializacao_reproduz_a_arvore_commitada(nome, recursos, operacoes, arquivos):
    dados = _carregar_fixture(nome)
    resultado = materializar(dados["api"], dados["revision"])

    gerado = {a.caminho: a.texto for a in resultado.arquivos}
    assert len(gerado) == arquivos
    assert gerado == _arvore_commitada(nome), (
        f"{nome}: a materialização divergiu da árvore de referência"
    )


@pytest.mark.parametrize("nome,recursos,operacoes,arquivos", CASOS)
@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_materializacao_e_deterministica(nome, recursos, operacoes, arquivos):
    dados = _carregar_fixture(nome)
    a = materializar(dados["api"], dados["revision"])
    b = materializar(dados["api"], dados["revision"])
    assert [(x.caminho, x.texto) for x in a.arquivos] == [
        (x.caminho, x.texto) for x in b.arquivos
    ]


@pytest.mark.parametrize("nome,recursos,operacoes,arquivos", CASOS)
@pytest.mark.skipif(not EXEMPLOS.is_dir(), reason="exemplos gerados ausentes")
def test_todo_arquivo_commitado_parseia(nome, recursos, operacoes, arquivos):
    """O README afirmava isso e estava errado: dois arquivos de `api-400-rev4`
    emitiam `replaceChar: *****` sem aspas e não eram parseáveis."""
    for caminho, texto in _arvore_commitada(nome).items():
        try:
            yaml.safe_load(texto)
        except yaml.YAMLError as exc:
            pytest.fail(f"{nome}/{caminho} não parseia: {exc}")


@pytest.mark.parametrize("nome,recursos,operacoes,arquivos", CASOS)
@pytest.mark.skipif(not EXEMPLOS.is_dir(), reason="exemplos gerados ausentes")
def test_round_trip_materializar_e_reler(nome, recursos, operacoes, arquivos):
    """A árvore materializada é lida de volta pela E1 sem perda."""
    lido = RepoCanonicalReader(LocalFileImporterAdapter()).carregar(
        str(EXEMPLOS / nome)
    )
    assert lido.completo, f"{nome}: faltando={lido.faltando} ilegiveis={lido.ilegiveis}"
    assert len(lido.recursos) == recursos
    assert lido.total_operacoes == operacoes


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_fixtures_nao_carregam_script_de_custom():
    """Guarda de privacidade: o script de um `Custom` é código interno do tenant."""
    for nome, *_ in CASOS:
        bruto = (FIXTURES / f"{nome}.json").read_text(encoding="utf-8")
        assert '"script"' not in bruto


@pytest.mark.skipif(not EXEMPLOS.is_dir(), reason="exemplos gerados ausentes")
def test_supressao_sobrevive_ao_round_trip():
    """V-25 ponta a ponta: a raiz mantém o item, a operação que o suprime não."""
    lido = RepoCanonicalReader(LocalFileImporterAdapter()).carregar(
        str(EXEMPLOS / "api-417-rev2")
    )
    tipos_raiz = [i["type"] for i in lido.raiz["interceptors_request"]]
    assert "XSS threat protection" in tipos_raiz

    operacao = next(
        o
        for r in lido.recursos
        for o in r.operacoes
        if o.arquivo == "get_tarefas.yaml"
    )
    assert operacao.dados["inherit"] is False
    tipos_op = [i["type"] for i in operacao.dados["interceptors_request"]]
    assert "XSS threat protection" not in tipos_op
    assert len(tipos_op) == len(tipos_raiz) - 1
