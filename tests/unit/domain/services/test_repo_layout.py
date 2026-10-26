"""Nomenclatura do layout canônico (D-005 §4, V-16/V-17, V-18).

Oracle: os nomes produzidos aqui têm de reproduzir exatamente os dos
repositórios materializados em `exemplos-gerados/output/`, gerados a partir de
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
    "entrada,expected",
    [
        ("Tarefas", "tarefas"),
        ("Atribuicao Responsavel", "atribuicao-responsavel"),
        ("Serviço de Letras", "servico-de-letras"),
        ("/tarefas/{id}", "tarefas-id"),
        ("  espaços  ", "espacos"),
        ("a---b", "a-b"),
    ],
)
def test_slug_normaliza(entrada, expected):
    assert rl.slug(entrada) == expected


def test_slug_trunca_em_fronteira_de_palavra():
    name = "recurso-com-nome-bastante-longo-que-passa-do-teto-estabelecido-aqui"
    resultado = rl.slug(name, limit=30)
    assert len(resultado) <= 30
    assert not resultado.endswith("-")
    assert name.startswith(resultado)


# --- nome de pasta ---------------------------------------------------------


def test_pasta_sem_colisao_usa_o_slug_puro():
    resource = {"name": "Tarefas", "operations": [{"path": "/tarefas", "method": "GET"}]}
    assert rl.folder_name(resource, [resource]) == "tarefas"


def test_nome_reservado_do_windows_recebe_sufixo():
    """Uma pasta chamada `con` ou `aux` é incriável no Windows."""
    resource = {"name": "CON", "operations": [{"path": "/x", "method": "GET"}]}
    assert rl.folder_name(resource, [resource]) == "con-recurso"


def test_homonimos_sao_desambiguados_por_sufixo_legivel():
    a = {"name": "Itens", "operations": [{"path": "/pedidos/itens", "method": "GET"}]}
    b = {"name": "Itens", "operations": [{"path": "/notas/itens", "method": "GET"}]}
    names = {rl.folder_name(r, [a, b]) for r in (a, b)}
    assert names == {"itens-pedidos-itens", "itens-notas-itens"}
    assert len(names) == 2


def test_aviso_distingue_nome_identico_de_truncamento():
    """São problemas diferentes para quem lê o repositório."""
    a = {"name": "Itens", "operations": [{"path": "/a/itens", "method": "GET"}]}
    b = {"name": "Itens", "operations": [{"path": "/b/itens", "method": "GET"}]}
    warnings = []
    rl.folder_name(a, [a, b], warnings)
    assert any("MESMO nome" in x for x in warnings)


def test_marca_e_deterministica_e_derivada_das_operacoes():
    r1 = {"name": "X", "operations": [{"path": "/a", "method": "GET"}]}
    r2 = {"name": "X", "operations": [{"path": "/a", "method": "GET"}]}
    assert rl.fingerprint(r1) == rl.fingerprint(r2)
    r3 = {"name": "X", "operations": [{"path": "/b", "method": "GET"}]}
    assert rl.fingerprint(r1) != rl.fingerprint(r3)


def test_marca_ignora_ordem_das_operacoes():
    r1 = {"name": "X", "operations": [{"path": "/a", "method": "GET"}, {"path": "/b", "method": "POST"}]}
    r2 = {"name": "X", "operations": [{"path": "/b", "method": "POST"}, {"path": "/a", "method": "GET"}]}
    assert rl.fingerprint(r1) == rl.fingerprint(r2)


# --- nome de arquivo da operação -------------------------------------------


@pytest.mark.parametrize(
    "method,path,expected",
    [
        ("GET", "/tarefas", "get_tarefas.yaml"),
        ("GET", "/letras/{id}", "get_letras_{id}.yaml"),
        ("POST", "/tarefas/{id}/atribuicao-responsavel", "post_tarefas_{id}_atribuicao-responsavel.yaml"),
        ("DELETE", "/letras/{id}", "delete_letras_{id}.yaml"),
    ],
)
def test_nome_de_arquivo_e_legivel_como_a_rota(method, path, expected):
    """O `{param}` é preservado: o nome do arquivo tem de ser lido como a rota."""
    assert rl.file_name({"method": method, "path": path}) == expected


def test_nome_longo_e_truncado_com_marca_e_avisa():
    op = {"method": "GET", "path": "/" + "/".join(f"segmento-{i}" for i in range(20))}
    warnings = []
    name = rl.file_name(op, warnings)
    assert len(name) <= rl.MAX_FILE + len(".yaml")
    assert re.search(r"-[0-9a-f]{6}\.yaml$", name)
    assert any("truncado" in a for a in warnings)


# --- método derivado do nome do arquivo ------------------------------------


@pytest.mark.parametrize(
    "file,expected",
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
def test_metodo_vem_do_nome_do_arquivo(file, expected):
    """O YAML da operação NÃO declara `method` (D-005 §4)."""
    assert rl.method_from_file(file) == expected


def test_metodo_sobrevive_ao_truncamento():
    """O método é prefixo, então o truncamento não o alcança."""
    op = {"method": "PATCH", "path": "/" + "/".join(f"seg-{i}" for i in range(20))}
    assert rl.method_from_file(rl.file_name(op)) == "PATCH"


# --- execution points governados -------------------------------------------


@pytest.mark.parametrize("point,governado", [("FIRST", True), ("SECOND", True), ("THIRD", False), (None, False)])
def test_particao_do_estado_governado(point, governado):
    """V-22: o que está fora de FIRST/SECOND volta intacto e não entra na conformidade."""
    assert rl.is_governed(point) is governado


# --- oracle: os repositórios reais -----------------------------------------


@pytest.mark.skipif(not RAIZ_EXEMPLOS.is_dir(), reason="exemplos gerados ausentes")
def test_round_trip_dos_nomes_contra_os_repositorios_reais():
    """Para cada operação materializada, (método do nome + path do conteúdo)
    tem de reproduzir exatamente o nome do arquivo."""
    conferidas = 0
    for repo in sorted(RAIZ_EXEMPLOS.iterdir()):
        pasta_recursos = repo / rl.RESOURCES_FOLDER
        if not pasta_recursos.is_dir():
            continue
        for folder in sorted(pasta_recursos.iterdir()):
            for file in sorted(folder.glob("*.yaml")):
                if file.name == rl.RESOURCE_FILE:
                    continue
                text = file.read_text(encoding="utf-8")
                path = (yaml.safe_load(text) or {}).get("path")
                method = rl.method_from_file(file.name)
                assert method is not None, f"método não derivado de {file.name}"
                assert (
                    rl.file_name({"method": method, "path": path}) == file.name
                ), f"round-trip divergiu em {repo.name}/{folder.name}/{file.name}"
                conferidas += 1
    assert conferidas > 0, "nenhuma operação conferida"


# --- descoberta da E1 ------------------------------------------------------


def _arvore_minima(*extras):
    return [rl.BASIC_INFO_FILE, rl.ROOT_FILE, *extras]


def test_descoberta_de_uma_arvore_completa():
    d = rl.discover(
        _arvore_minima(
            "resources/tarefas/resource.yaml",
            "resources/tarefas/get_tarefas.yaml",
            "resources/tarefas/get_tarefas_{id}.yaml",
            "resources/letras/resource.yaml",
            "resources/letras/delete_letras_{id}.yaml",
        )
    )
    assert d.complete
    assert [r.slug for r in d.resources] == ["letras", "tarefas"]
    assert d.total_operations == 3
    assert {o.method for o in d.resources[1].operations} == {"GET"}


def test_all_yaml_ausente_impede_a_publicacao():
    """A raiz não herda de ninguém: publicar sem ela apaga o fluxo da revision."""
    d = rl.discover([rl.BASIC_INFO_FILE])
    assert not d.complete
    assert rl.ROOT_FILE in d.missing


def test_erro_de_digitacao_no_arquivo_base_vira_ausencia():
    """A proteção vem da obrigatoriedade do nome, não da proibição do desconhecido."""
    d = rl.discover([rl.BASIC_INFO_FILE, "alll.yaml"])
    assert rl.ROOT_FILE in d.missing
    # o quase-acerto continua visível, e serve para a mensagem de erro
    assert "alll.yaml" in d.ignored


def test_arquivo_nao_relacionado_nao_derruba_a_descoberta():
    d = rl.discover(_arvore_minima("notas.yaml", "resources/x/resource.yaml"))
    assert d.complete
    assert d.ignored == ["notas.yaml"]


def test_pasta_de_recurso_sem_resource_yaml_e_apontada():
    d = rl.discover(_arvore_minima("resources/x/get_x.yaml"))
    assert not d.complete
    assert "resources/x/resource.yaml" in d.missing


def test_yaml_sem_metodo_dentro_do_recurso_e_ignorado_nao_e_operacao():
    d = rl.discover(
        _arvore_minima("resources/x/resource.yaml", "resources/x/rascunho.yaml")
    )
    assert d.complete
    assert d.total_operations == 0
    assert "resources/x/rascunho.yaml" in d.ignored


def test_descoberta_e_estavel_na_ordem():
    entrada = _arvore_minima(
        "resources/b/resource.yaml",
        "resources/a/resource.yaml",
        "resources/a/post_a.yaml",
        "resources/a/get_a.yaml",
    )
    uma = rl.discover(entrada)
    outra = rl.discover(list(reversed(entrada)))
    assert [r.slug for r in uma.resources] == [r.slug for r in outra.resources]
    assert [o.file for o in uma.resources[0].operations] == [
        o.file for o in outra.resources[0].operations
    ]


def test_separador_do_windows_e_aceito():
    d = rl.discover(
        [rl.BASIC_INFO_FILE, rl.ROOT_FILE, r"resources\tarefas\resource.yaml"]
    )
    assert d.complete
    assert d.resources[0].slug == "tarefas"


@pytest.mark.skipif(not RAIZ_EXEMPLOS.is_dir(), reason="exemplos gerados ausentes")
def test_descoberta_contra_os_repositorios_reais():
    expected = {"api-417-rev2": (4, 7), "api-400-rev4": (2, 4)}
    for repo in sorted(RAIZ_EXEMPLOS.iterdir()):
        if repo.name not in expected:
            continue
        paths = [str(p.relative_to(repo)) for p in repo.rglob("*.yaml")]
        d = rl.discover(paths)
        resources, operations = expected[repo.name]
        assert d.complete, f"{repo.name}: faltando {d.missing}"
        assert len(d.resources) == resources
        assert d.total_operations == operations


# --- components.yaml ---------------------------------------------------------


def test_components_file_is_recognized_at_the_root():
    d = rl.discover(_arvore_minima(rl.COMPONENTS_FILE))

    assert d.components_path == rl.COMPONENTS_FILE
    assert rl.COMPONENTS_FILE not in d.ignored
    assert d.complete


def test_components_file_is_optional():
    d = rl.discover(_arvore_minima())

    assert d.components_path is None
    assert d.complete


def test_components_yml_is_not_the_components_file():
    d = rl.discover(_arvore_minima("components.yml"))

    assert d.components_path is None
    assert "components.yml" in d.ignored
