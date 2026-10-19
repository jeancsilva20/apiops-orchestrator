"""Leitor do layout canônico — a E1 do `sen validate` (D-005 §4, V-18)."""

import textwrap

import pytest

from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
    LocalFileImporterAdapter,
)
from apiops_orchestrator.application.services.repo_importer_service import (
    RepoCanonicalReader,
)

BASIC_INFO = """\
apiVersion: api-management.sensedia.com/v1
kind: ApiBasicInfo
spec:
  id: 417
  name: "Servico de Letras"
  version: "1.0.0"
  basePath: "/letras/v2"
  description: "API de teste"
  template: ''
"""

ALL_YAML = """\
destination:
  url: https://backend.exemplo/api
  timeout: '30'

interceptors_request:
  - type: Custom
    id: 32
  - type: Log
    content:
      acceptedTerms: true
"""

RESOURCE_YAML = """\
name: "Tarefas"
description: "Gerenciamento de tarefas"
inherit: true
"""

OPERACAO_YAML = """\
path: /tarefas
destination:
  url: https://backend.exemplo/api/tarefas
inherit: true
"""


@pytest.fixture
def leitor():
    return RepoCanonicalReader(LocalFileImporterAdapter())


def _montar(raiz, arquivos):
    for caminho, conteudo in arquivos.items():
        destino = raiz / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(textwrap.dedent(conteudo), encoding="utf-8")
    return raiz


def test_carrega_um_repositorio_completo(tmp_path, leitor):
    repo = _montar(
        tmp_path,
        {
            "api-basic-info.yaml": BASIC_INFO,
            "all.yaml": ALL_YAML,
            "resources/tarefas/resource.yaml": RESOURCE_YAML,
            "resources/tarefas/get_tarefas.yaml": OPERACAO_YAML,
        },
    )
    r = leitor.carregar(str(repo))

    assert r.completo
    assert r.basic_info["spec"]["id"] == 417
    assert len(r.raiz["interceptors_request"]) == 2
    assert [rec.slug for rec in r.recursos] == ["tarefas"]
    assert r.recursos[0].nome == "Tarefas"
    assert r.total_operacoes == 1


def test_metodo_vem_do_nome_e_path_do_conteudo(tmp_path, leitor):
    repo = _montar(
        tmp_path,
        {
            "api-basic-info.yaml": BASIC_INFO,
            "all.yaml": ALL_YAML,
            "resources/tarefas/resource.yaml": RESOURCE_YAML,
            "resources/tarefas/delete_tarefas_{id}.yaml": "path: /tarefas/{id}\n",
        },
    )
    operacao = leitor.carregar(str(repo)).recursos[0].operacoes[0]

    assert operacao.metodo == "DELETE"
    assert operacao.path == "/tarefas/{id}"
    assert "method" not in operacao.dados


def test_all_yaml_ausente_impede_a_publicacao(tmp_path, leitor):
    """Publicar sem o escopo raiz apagaria o fluxo da revision (V-18 §2.3)."""
    repo = _montar(tmp_path, {"api-basic-info.yaml": BASIC_INFO})
    r = leitor.carregar(str(repo))

    assert not r.completo
    assert "all.yaml" in r.faltando


def test_typo_no_arquivo_base_e_reportado_dos_dois_lados(tmp_path, leitor):
    repo = _montar(
        tmp_path, {"api-basic-info.yaml": BASIC_INFO, "alll.yaml": ALL_YAML}
    )
    r = leitor.carregar(str(repo))

    assert "all.yaml" in r.faltando
    assert "alll.yaml" in r.ignorados


def test_arquivo_ilegivel_falha_alto_em_vez_de_virar_vazio(tmp_path, leitor):
    """O caso real: `replaceChar: *****` sem aspas torna o arquivo imparseável.

    Tratá-lo como arquivo vazio publicaria uma operação sem configuração — uma
    perda silenciosa causada pelo próprio CLI.
    """
    repo = _montar(
        tmp_path,
        {
            "api-basic-info.yaml": BASIC_INFO,
            "all.yaml": ALL_YAML,
            "resources/token/resource.yaml": RESOURCE_YAML,
            "resources/token/post_token.yaml": (
                "path: /token\n"
                "interceptors_request:\n"
                "  - type: Masking\n"
                "    content:\n"
                "      replaceChar: *****\n"
            ),
        },
    )
    r = leitor.carregar(str(repo))

    assert not r.completo
    assert len(r.ilegiveis) == 1
    assert "post_token.yaml" in r.ilegiveis[0]


def test_arquivo_nao_relacionado_nao_derruba_a_leitura(tmp_path, leitor):
    repo = _montar(
        tmp_path,
        {
            "api-basic-info.yaml": BASIC_INFO,
            "all.yaml": ALL_YAML,
            "anotacoes.yaml": "rascunho: true\n",
        },
    )
    r = leitor.carregar(str(repo))

    assert r.completo
    assert r.ignorados == ["anotacoes.yaml"]


def test_repositorio_vazio_lista_os_dois_arquivos_base(tmp_path, leitor):
    r = leitor.carregar(str(tmp_path))
    assert set(r.faltando) == {"api-basic-info.yaml", "all.yaml"}


def test_leitura_nao_toca_a_rede(tmp_path, leitor, monkeypatch):
    """A E1 roda inteira sem rede — é o que permite a guarda abortar antes."""
    import requests

    def _proibido(*args, **kwargs):
        raise AssertionError("a E1 não pode emitir chamada HTTP")

    monkeypatch.setattr(requests, "request", _proibido, raising=False)
    monkeypatch.setattr(requests, "get", _proibido, raising=False)

    repo = _montar(
        tmp_path, {"api-basic-info.yaml": BASIC_INFO, "all.yaml": ALL_YAML}
    )
    assert leitor.carregar(str(repo)).completo
