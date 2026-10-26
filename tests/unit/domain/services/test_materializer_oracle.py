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
from apiops_orchestrator.domain.services.repo_materializer import materialize

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


def _carregar_fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _arvore_commitada(name):
    base = EXEMPLOS / name
    return {
        str(p.relative_to(base)).replace("\\", "/"): p.read_text(encoding="utf-8")
        for p in base.rglob("*.yaml")
    }


@pytest.mark.parametrize("name,resources,operations,files", CASOS)
@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_materializacao_reproduz_a_arvore_commitada(name, resources, operations, files):
    data = _carregar_fixture(name)
    resultado = materialize(data["api"], data["revision"])

    gerado = {a.file_path: a.text for a in resultado.files}
    assert len(gerado) == files
    assert gerado == _arvore_commitada(name), (
        f"{name}: a materialização divergiu da árvore de referência"
    )


@pytest.mark.parametrize("name,resources,operations,files", CASOS)
@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_materializacao_e_deterministica(name, resources, operations, files):
    data = _carregar_fixture(name)
    a = materialize(data["api"], data["revision"])
    b = materialize(data["api"], data["revision"])
    assert [(x.file_path, x.text) for x in a.files] == [
        (x.file_path, x.text) for x in b.files
    ]


@pytest.mark.parametrize("name,resources,operations,files", CASOS)
@pytest.mark.skipif(not EXEMPLOS.is_dir(), reason="exemplos gerados ausentes")
def test_todo_arquivo_commitado_parseia(name, resources, operations, files):
    """O README afirmava isso e estava errado: dois arquivos de `api-400-rev4`
    emitiam `replaceChar: *****` sem aspas e não eram parseáveis."""
    for file_path, text in _arvore_commitada(name).items():
        try:
            yaml.safe_load(text)
        except yaml.YAMLError as exc:
            pytest.fail(f"{name}/{file_path} não parseia: {exc}")


@pytest.mark.parametrize("name,resources,operations,files", CASOS)
@pytest.mark.skipif(not EXEMPLOS.is_dir(), reason="exemplos gerados ausentes")
def test_round_trip_materializar_e_reler(name, resources, operations, files):
    """A árvore materializada é lida de volta pela E1 sem perda."""
    loaded = RepoCanonicalReader(LocalFileImporterAdapter()).load(
        str(EXEMPLOS / name)
    )
    assert loaded.complete, f"{name}: faltando={loaded.missing} ilegiveis={loaded.unreadable}"
    assert len(loaded.resources) == resources
    assert loaded.total_operations == operations


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_fixtures_nao_carregam_script_de_custom():
    """Guarda de privacidade: o script de um `Custom` é código interno do tenant."""
    for name, *_ in CASOS:
        raw = (FIXTURES / f"{name}.json").read_text(encoding="utf-8")
        assert '"script"' not in raw


@pytest.mark.skipif(not EXEMPLOS.is_dir(), reason="exemplos gerados ausentes")
def test_supressao_sobrevive_ao_round_trip():
    """V-25 ponta a ponta: a raiz mantém o item, a operação que o suprime não."""
    loaded = RepoCanonicalReader(LocalFileImporterAdapter()).load(
        str(EXEMPLOS / "api-417-rev2")
    )
    tipos_raiz = [i["type"] for i in loaded.root["interceptors_request"]]
    assert "XSS threat protection" in tipos_raiz

    operacao = next(
        o
        for r in loaded.resources
        for o in r.operations
        if o.file == "get_tarefas.yaml"
    )
    assert operacao.data["inherit"] is False
    tipos_op = [i["type"] for i in operacao.data["interceptors_request"]]
    assert "XSS threat protection" not in tipos_op
    assert len(tipos_op) == len(tipos_raiz) - 1
