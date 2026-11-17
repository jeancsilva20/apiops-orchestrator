"""Diff semântico de duas árvores materializadas (`sen sync --check`)."""

import yaml

from apiops_orchestrator.domain.services.repo_materializer import MaterializedFile
from apiops_orchestrator.domain.services.revision_diff import (
    ABSENT,
    Difference,
    compare,
    custom_ids,
    equivalent,
)


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


# --- listas de interceptors: por posição -------------------------------------------

LOG = {"type": "Log", "content": {"acceptedTerms": True}}
MOCK = {"type": "Mock", "content": {"status": 200}}
XSS = {"type": "XSS threat protection", "content": {"regexList": []}}


def _rate_limit(quota):
    return {"type": "Rate limit", "content": {"quota": quota, "interval": "SECOND"}}


def _flow(*items, key="interceptors_request"):
    return [_file("all.yaml", yaml.safe_dump({key: list(items)}, allow_unicode=True))]


def test_campo_mudado_no_mesmo_interceptor_aponta_o_campo_e_o_tipo():
    assert compare(_flow(LOG, _rate_limit(1000)), _flow(LOG, _rate_limit(500))) == [
        Difference("all.yaml", "interceptors_request[1].content.quota", 1000, 500, "Rate limit")
    ]


def test_texto_numerico_igual_ao_numero_no_conteudo_nao_e_diferenca():
    assert compare(_flow(_rate_limit(1000)), _flow(_rate_limit("1000"))) == []


def test_interceptor_diferente_numa_posicao_traz_as_duas_listas_inteiras():
    repo = [LOG, MOCK, _rate_limit(1000)]
    manager = [LOG, XSS, _rate_limit(500), LOG]
    assert compare(_flow(*repo), _flow(*manager)) == [
        Difference("all.yaml", "interceptors_request", repo, manager),
        # The field of the same interceptor still comes, below the lists.
        Difference("all.yaml", "interceptors_request[2].content.quota", 1000, 500, "Rate limit"),
    ]


def test_custom_com_outro_id_e_outro_interceptor():
    repo = [{"type": "Custom", "id": 32}, LOG]
    manager = [{"type": "Custom", "id": 125}, LOG]
    assert compare(_flow(*repo), _flow(*manager)) == [
        Difference("all.yaml", "interceptors_request", repo, manager)
    ]


def test_itens_alem_do_fim_da_outra_lista_vem_um_a_um():
    assert compare(_flow(LOG), _flow(LOG, MOCK, XSS)) == [
        Difference("all.yaml", "interceptors_request[1]", ABSENT, MOCK),
        Difference("all.yaml", "interceptors_request[2]", ABSENT, XSS),
    ]


def test_lista_so_de_um_lado_vem_inteira():
    repo = _flow(LOG, MOCK, key="interceptors_response")
    manager = [_file("all.yaml", "destination:\n  url: ''\n")]
    assert compare(repo, manager) == [
        Difference("all.yaml", "destination", ABSENT, {"url": ""}),
        Difference("all.yaml", "interceptors_response", [LOG, MOCK], ABSENT),
    ]


def test_lista_de_interceptors_dentro_de_outro_campo_segue_a_regra_geral():
    repo = [_file("a.yaml", "extra:\n  interceptors_request:\n  - type: Log\n")]
    manager = [_file("a.yaml", "extra:\n  interceptors_request:\n  - type: Mock\n")]
    assert compare(repo, manager) == [
        Difference("a.yaml", "extra.interceptors_request[0].type", "Log", "Mock")
    ]


def test_equivalente_segue_as_regras_do_diff():
    assert equivalent(_rate_limit(1000), _rate_limit("1000"))
    assert not equivalent(_rate_limit(1000), _rate_limit(500))
    assert not equivalent(True, 1)


def test_ids_de_custom_nos_valores_das_diferencas():
    differences = [
        Difference("all.yaml", "interceptors_request", [{"type": "Custom", "id": 32}, LOG], ABSENT),
        Difference("all.yaml", "interceptors_request[3]", ABSENT, {"type": "Custom", "id": "125"}),
        Difference("all.yaml", "destination.url", "x", "y"),
    ]
    assert custom_ids(differences) == {32, 125}
