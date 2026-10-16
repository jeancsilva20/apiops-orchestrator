"""Nomenclatura do layout canônico (D-005 §4, V-16/V-17, V-18).

Oracle: os nomes produzidos aqui têm de reproduzir exatamente os dos
repositórios materializados em `exemplos-gerados/saida/`, gerados a partir de
APIs reais.
"""

import pathlib
import re

import pytest
import yaml

from apiops_orchestrator.domain.services import repo_layout as rl

RAIZ_EXEMPLOS = (
    pathlib.Path(__file__).parents[4]
    / "docs"
    / "feat-api-estructure"
    / "decisoes-refino-409"
    / "exemplos-gerados"
    / "saida"
)


# --- slug ------------------------------------------------------------------


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("Tarefas", "tarefas"),
        ("Atribuicao Responsavel", "atribuicao-responsavel"),
        ("Serviço de Letras", "servico-de-letras"),
        ("/tarefas/{id}", "tarefas-id"),
        ("  espaços  ", "espacos"),
        ("a---b", "a-b"),
    ],
)
def test_slug_normaliza(entrada, esperado):
    assert rl.slug(entrada) == esperado


def test_slug_trunca_em_fronteira_de_palavra():
    nome = "recurso-com-nome-bastante-longo-que-passa-do-teto-estabelecido-aqui"
    resultado = rl.slug(nome, limite=30)
    assert len(resultado) <= 30
    assert not resultado.endswith("-")
    assert nome.startswith(resultado)


# --- nome de pasta ---------------------------------------------------------


def test_pasta_sem_colisao_usa_o_slug_puro():
    recurso = {"name": "Tarefas", "operations": [{"path": "/tarefas", "method": "GET"}]}
    assert rl.nome_pasta(recurso, [recurso]) == "tarefas"


def test_nome_reservado_do_windows_recebe_sufixo():
    """Uma pasta chamada `con` ou `aux` é incriável no Windows."""
    recurso = {"name": "CON", "operations": [{"path": "/x", "method": "GET"}]}
    assert rl.nome_pasta(recurso, [recurso]) == "con-recurso"


def test_homonimos_sao_desambiguados_por_sufixo_legivel():
    a = {"name": "Itens", "operations": [{"path": "/pedidos/itens", "method": "GET"}]}
    b = {"name": "Itens", "operations": [{"path": "/notas/itens", "method": "GET"}]}
    nomes = {rl.nome_pasta(r, [a, b]) for r in (a, b)}
    assert nomes == {"itens-pedidos-itens", "itens-notas-itens"}
    assert len(nomes) == 2


def test_aviso_distingue_nome_identico_de_truncamento():
    """São problemas diferentes para quem lê o repositório."""
    a = {"name": "Itens", "operations": [{"path": "/a/itens", "method": "GET"}]}
    b = {"name": "Itens", "operations": [{"path": "/b/itens", "method": "GET"}]}
    avisos = []
    rl.nome_pasta(a, [a, b], avisos)
    assert any("MESMO nome" in x for x in avisos)


def test_marca_e_deterministica_e_derivada_das_operacoes():
    r1 = {"name": "X", "operations": [{"path": "/a", "method": "GET"}]}
    r2 = {"name": "X", "operations": [{"path": "/a", "method": "GET"}]}
    assert rl.marca(r1) == rl.marca(r2)
    r3 = {"name": "X", "operations": [{"path": "/b", "method": "GET"}]}
    assert rl.marca(r1) != rl.marca(r3)


def test_marca_ignora_ordem_das_operacoes():
    r1 = {"name": "X", "operations": [{"path": "/a", "method": "GET"}, {"path": "/b", "method": "POST"}]}
    r2 = {"name": "X", "operations": [{"path": "/b", "method": "POST"}, {"path": "/a", "method": "GET"}]}
    assert rl.marca(r1) == rl.marca(r2)


# --- nome de arquivo da operação -------------------------------------------


@pytest.mark.parametrize(
    "metodo,path,esperado",
    [
        ("GET", "/tarefas", "get_tarefas.yaml"),
        ("GET", "/letras/{id}", "get_letras_{id}.yaml"),
        ("POST", "/tarefas/{id}/atribuicao-responsavel", "post_tarefas_{id}_atribuicao-responsavel.yaml"),
        ("DELETE", "/letras/{id}", "delete_letras_{id}.yaml"),
    ],
)
def test_nome_de_arquivo_e_legivel_como_a_rota(metodo, path, esperado):
    """O `{param}` é preservado: o nome do arquivo tem de ser lido como a rota."""
    assert rl.nome_arquivo({"method": metodo, "path": path}) == esperado


def test_nome_longo_e_truncado_com_marca_e_avisa():
    op = {"method": "GET", "path": "/" + "/".join(f"segmento-{i}" for i in range(20))}
    avisos = []
    nome = rl.nome_arquivo(op, avisos)
    assert len(nome) <= rl.MAX_ARQUIVO + len(".yaml")
    assert re.search(r"-[0-9a-f]{6}\.yaml$", nome)
    assert any("truncado" in a for a in avisos)


# --- método derivado do nome do arquivo ------------------------------------


@pytest.mark.parametrize(
    "arquivo,esperado",
    [
        ("get_tarefas.yaml", "GET"),
        ("post_tarefas_{id}_letras.yaml", "POST"),
        ("delete_letras_{id}.yaml", "DELETE"),
        ("resource.yaml", None),
        ("all.yaml", None),
        ("api-basic-info.yaml", None),
        ("qualquer-coisa.yaml", None),
    ],
)
def test_metodo_vem_do_nome_do_arquivo(arquivo, esperado):
    """O YAML da operação NÃO declara `method` (D-005 §4)."""
    assert rl.metodo_do_arquivo(arquivo) == esperado


def test_metodo_sobrevive_ao_truncamento():
    """O método é prefixo, então o truncamento não o alcança."""
    op = {"method": "PATCH", "path": "/" + "/".join(f"seg-{i}" for i in range(20))}
    assert rl.metodo_do_arquivo(rl.nome_arquivo(op)) == "PATCH"


# --- execution points governados -------------------------------------------


@pytest.mark.parametrize("ponto,governado", [("FIRST", True), ("SECOND", True), ("THIRD", False), (None, False)])
def test_particao_do_estado_governado(ponto, governado):
    """V-22: o que está fora de FIRST/SECOND volta intacto e não entra na conformidade."""
    assert rl.eh_governado(ponto) is governado


# --- oracle: os repositórios reais -----------------------------------------


@pytest.mark.skipif(not RAIZ_EXEMPLOS.is_dir(), reason="exemplos gerados ausentes")
def test_round_trip_dos_nomes_contra_os_repositorios_reais():
    """Para cada operação materializada, (método do nome + path do conteúdo)
    tem de reproduzir exatamente o nome do arquivo."""
    conferidas = 0
    for repo in sorted(RAIZ_EXEMPLOS.iterdir()):
        pasta_recursos = repo / rl.PASTA_RECURSOS
        if not pasta_recursos.is_dir():
            continue
        for pasta in sorted(pasta_recursos.iterdir()):
            for arquivo in sorted(pasta.glob("*.yaml")):
                if arquivo.name == rl.ARQUIVO_RECURSO:
                    continue
                texto = arquivo.read_text(encoding="utf-8")
                path = (yaml.safe_load(texto) or {}).get("path")
                metodo = rl.metodo_do_arquivo(arquivo.name)
                assert metodo is not None, f"método não derivado de {arquivo.name}"
                assert (
                    rl.nome_arquivo({"method": metodo, "path": path}) == arquivo.name
                ), f"round-trip divergiu em {repo.name}/{pasta.name}/{arquivo.name}"
                conferidas += 1
    assert conferidas > 0, "nenhuma operação conferida"


# --- descoberta da E1 ------------------------------------------------------


def _arvore_minima(*extras):
    return [rl.ARQUIVO_BASIC_INFO, rl.ARQUIVO_RAIZ, *extras]


def test_descoberta_de_uma_arvore_completa():
    d = rl.descobrir(
        _arvore_minima(
            "resources/tarefas/resource.yaml",
            "resources/tarefas/get_tarefas.yaml",
            "resources/tarefas/get_tarefas_{id}.yaml",
            "resources/letras/resource.yaml",
            "resources/letras/delete_letras_{id}.yaml",
        )
    )
    assert d.completo
    assert [r.slug for r in d.recursos] == ["letras", "tarefas"]
    assert d.total_operacoes == 3
    assert {o.metodo for o in d.recursos[1].operacoes} == {"GET"}


def test_all_yaml_ausente_impede_a_publicacao():
    """A raiz não herda de ninguém: publicar sem ela apaga o fluxo da revision."""
    d = rl.descobrir([rl.ARQUIVO_BASIC_INFO])
    assert not d.completo
    assert rl.ARQUIVO_RAIZ in d.faltando


def test_erro_de_digitacao_no_arquivo_base_vira_ausencia():
    """A proteção vem da obrigatoriedade do nome, não da proibição do desconhecido."""
    d = rl.descobrir([rl.ARQUIVO_BASIC_INFO, "alll.yaml"])
    assert rl.ARQUIVO_RAIZ in d.faltando
    # o quase-acerto continua visível, e serve para a mensagem de erro
    assert "alll.yaml" in d.ignorados


def test_arquivo_nao_relacionado_nao_derruba_a_descoberta():
    d = rl.descobrir(_arvore_minima("notas.yaml", "resources/x/resource.yaml"))
    assert d.completo
    assert d.ignorados == ["notas.yaml"]


def test_pasta_de_recurso_sem_resource_yaml_e_apontada():
    d = rl.descobrir(_arvore_minima("resources/x/get_x.yaml"))
    assert not d.completo
    assert "resources/x/resource.yaml" in d.faltando


def test_yaml_sem_metodo_dentro_do_recurso_e_ignorado_nao_e_operacao():
    d = rl.descobrir(
        _arvore_minima("resources/x/resource.yaml", "resources/x/rascunho.yaml")
    )
    assert d.completo
    assert d.total_operacoes == 0
    assert "resources/x/rascunho.yaml" in d.ignorados


def test_descoberta_e_estavel_na_ordem():
    entrada = _arvore_minima(
        "resources/b/resource.yaml",
        "resources/a/resource.yaml",
        "resources/a/post_a.yaml",
        "resources/a/get_a.yaml",
    )
    uma = rl.descobrir(entrada)
    outra = rl.descobrir(list(reversed(entrada)))
    assert [r.slug for r in uma.recursos] == [r.slug for r in outra.recursos]
    assert [o.arquivo for o in uma.recursos[0].operacoes] == [
        o.arquivo for o in outra.recursos[0].operacoes
    ]


def test_separador_do_windows_e_aceito():
    d = rl.descobrir(
        [rl.ARQUIVO_BASIC_INFO, rl.ARQUIVO_RAIZ, r"resources\tarefas\resource.yaml"]
    )
    assert d.completo
    assert d.recursos[0].slug == "tarefas"


@pytest.mark.skipif(not RAIZ_EXEMPLOS.is_dir(), reason="exemplos gerados ausentes")
def test_descoberta_contra_os_repositorios_reais():
    esperado = {"api-417-rev2": (4, 7), "api-400-rev4": (2, 4)}
    for repo in sorted(RAIZ_EXEMPLOS.iterdir()):
        if repo.name not in esperado:
            continue
        caminhos = [str(p.relative_to(repo)) for p in repo.rglob("*.yaml")]
        d = rl.descobrir(caminhos)
        recursos, operacoes = esperado[repo.name]
        assert d.completo, f"{repo.name}: faltando {d.faltando}"
        assert len(d.recursos) == recursos
        assert d.total_operacoes == operacoes
