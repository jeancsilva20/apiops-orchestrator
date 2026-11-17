"""Diff semântico de duas árvores materializadas (`sen sync --check`)."""

from apiops_orchestrator.domain.services.repo_materializer import MaterializedFile
from apiops_orchestrator.domain.services.revision_diff import ABSENT, Difference, compare


def _file(path, text):
    return MaterializedFile(file_path=path, text=text)


def test_arvores_iguais_nao_tem_diferenca():
    a = [_file("all.yaml", "destination:\n  url: x\n  timeout: '30'\n")]
    assert compare(a, a) == []


def test_comentarios_ordem_de_chaves_e_aspas_nao_contam():
    repo = [_file("all.yaml", "# comentário\ntimeout: 30\ndestination:\n  url: \"x\"\n")]
    manager = [_file("all.yaml", "destination:\n  url: x\ntimeout: '30'\n")]
    assert compare(repo, manager) == []


def test_campo_diferente_aponta_arquivo_campo_e_os_dois_valores():
    repo = [_file("resources/a/get_a.yaml", "destination:\n  url: x\n  timeout: '30'\n")]
    manager = [_file("resources/a/get_a.yaml", "destination:\n  url: x\n  timeout: '99'\n")]
    assert compare(repo, manager) == [
        Difference("resources/a/get_a.yaml", "destination.timeout", "30", "99")
    ]


def test_item_de_lista_e_apontado_pelo_indice():
    repo = [_file("all.yaml", "interceptors_request:\n  - type: Log\n  - type: Rate limit\n")]
    manager = [_file("all.yaml", "interceptors_request:\n  - type: Log\n")]
    assert compare(repo, manager) == [
        Difference("all.yaml", "interceptors_request[1]", {"type": "Rate limit"}, ABSENT)
    ]


def test_chave_so_de_um_lado():
    repo = [_file("all.yaml", "destination:\n  url: x\n")]
    manager = [_file("all.yaml", "destination:\n  url: x\n  timeout: '30'\n")]
    assert compare(repo, manager) == [
        Difference("all.yaml", "destination.timeout", ABSENT, "30")
    ]


def test_arquivo_so_de_um_lado():
    repo = [_file("all.yaml", "a: 1\n"), _file("resources/x/resource.yaml", "name: X\n")]
    manager = [_file("all.yaml", "a: 1\n"), _file("resources/y/resource.yaml", "name: Y\n")]
    assert compare(repo, manager) == [
        Difference("resources/x/resource.yaml", None, "arquivo presente", ABSENT),
        Difference("resources/y/resource.yaml", None, ABSENT, "arquivo presente"),
    ]


def test_booleano_nao_vira_numero():
    repo = [_file("a.yaml", "inherit: true\n")]
    manager = [_file("a.yaml", "inherit: 1\n")]
    assert compare(repo, manager) == [Difference("a.yaml", "inherit", True, 1)]


# --- apiTags: conjunto, não lista ------------------------------------------------

def _basic_info(api_tags):
    body = "spec:\n  id: 425\n  apiTags:\n"
    for name, tags in api_tags:
        body += f"  - attributeName: {name}\n    tags:\n" + "".join(f"    - {t}\n" for t in tags)
    return [_file("api-basic-info.yaml", body)]


def test_apitags_na_mesma_ordem_ou_em_outra_sao_iguais():
    repo = _basic_info([("Autenticação", ["CyberArk"]), ("Produto", ["B", "A"]), ("Deploy", ["PRD"])])
    manager = _basic_info([("Produto", ["A", "B"]), ("Deploy", ["PRD"]), ("Autenticação", ["CyberArk"])])
    assert compare(repo, manager) == []


def test_apitags_com_atributo_a_mais_ou_tag_diferente_aponta_o_atributo():
    repo = _basic_info([("Produto", ["A"]), ("Deploy", ["PRD"])])
    manager = _basic_info([("Produto", ["A", "B"]), ("Setor", ["Arquitetura"])])
    assert compare(repo, manager) == [
        Difference("api-basic-info.yaml", "spec.apiTags.Deploy", "PRD", ABSENT),
        Difference("api-basic-info.yaml", "spec.apiTags.Produto", "A", "A, B"),
        Difference("api-basic-info.yaml", "spec.apiTags.Setor", ABSENT, "Arquitetura"),
    ]


def test_apitags_vazia_contra_ausente_continua_diferenca():
    repo = [_file("api-basic-info.yaml", "spec:\n  id: 425\n  apiTags: []\n")]
    manager = [_file("api-basic-info.yaml", "spec:\n  id: 425\n")]
    assert compare(repo, manager) == [
        Difference("api-basic-info.yaml", "spec.apiTags", [], ABSENT)
    ]
