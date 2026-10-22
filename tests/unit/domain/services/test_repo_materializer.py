"""Materialização do layout canônico a partir do wire (V-18, V-22, V-25, V-26).

As fixtures espelham o shape REAL lido da API 417 / revisão 9175, incluindo o
tombstone com `parent.id`.
"""

import yaml

from apiops_orchestrator.domain.services import repo_layout as layout
from apiops_orchestrator.domain.services.repo_materializer import materializar

API = {
    "id": 417,
    "name": "Servico de Letras 2.0.0",
    "version": "1.0.0",
    "basePath": "/letras/v2",
    "description": "API de teste",
    "apiResponsible": {"username": "paulo.silva", "groupName": ""},
    "apiTags": [{"attributeName": "My new", "tags": ["Tag1"]}],
}

# Fluxo da raiz; o XSS (id 19422) é o que o tombstone suprime.
RAIZ = [
    {"id": 19504, "type": "Custom", "customInterceptorId": 32, "executionPoint": "FIRST", "position": 0},
    {"id": 19426, "type": "Log", "executionPoint": "FIRST", "position": 2, "content": '{"acceptedTerms": true}'},
    {"id": 19422, "type": "XSS threat protection", "executionPoint": "FIRST", "position": 6, "content": '{"regexList": []}'},
    {"id": 19420, "type": "Log", "executionPoint": "SECOND", "position": 8, "content": '{"acceptedTerms": true}'},
    # não governado: volta intacto e NÃO entra no YAML (V-22)
    {"id": 19999, "type": "Custom", "customInterceptorId": 178, "executionPoint": "THIRD", "position": 9},
]

TOMBSTONE = {
    "id": 19430,
    "type": "XSS threat protection",
    "executionPoint": "FIRST",
    "position": 6,
    "status": "REMOVED",
    "parent": {"id": 19422, "idTemp": 19422},
    "parentType": "REVISION",
    "content": '{"regexList": []}',
}


def _revision(operacoes):
    return {
        "id": 9175,
        "revisionNumber": 2,
        "destination": "https://teste.com",
        "timeout": "30",
        "interceptors": list(RAIZ),
        "resources": [
            {
                "name": "Tarefas",
                "description": "Gerenciamento",
                "destination": "https://google.com",
                "interceptors": [],
                "operations": operacoes,
            }
        ],
    }


def _ler(resultado, sufixo):
    arquivo = next(a for a in resultado.arquivos if a.caminho.endswith(sufixo))
    return yaml.safe_load(arquivo.texto), arquivo.texto


def test_arvore_canonica_completa():
    r = materializar(API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}]))
    caminhos = set(r.caminhos)
    assert layout.ARQUIVO_BASIC_INFO in caminhos
    assert layout.ARQUIVO_RAIZ in caminhos
    assert "resources/tarefas/resource.yaml" in caminhos
    assert "resources/tarefas/get_tarefas.yaml" in caminhos


def test_todo_arquivo_gerado_e_yaml_valido():
    r = materializar(API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}]))
    for arquivo in r.arquivos:
        yaml.safe_load(arquivo.texto)


def test_materializacao_e_deterministica():
    rev = _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}])
    a, b = materializar(API, rev), materializar(API, rev)
    assert [(x.caminho, x.texto) for x in a.arquivos] == [
        (x.caminho, x.texto) for x in b.arquivos
    ]


def test_estado_nao_governado_fica_fora_do_yaml(_=None):
    """V-22: o que está fora de FIRST/SECOND volta intacto, mas não é versionado."""
    r = materializar(API, _revision([]))
    raiz, texto = _ler(r, layout.ARQUIVO_RAIZ)
    ids = [i.get("id") for i in raiz.get("interceptors_request") or []]
    assert 178 not in ids
    assert "não governado" in texto


def test_basic_info_declara_template_vazio_porque_o_wire_nao_tem():
    """D-12: a plataforma não tem a chave `template` (8 confirmações de ausência)."""
    r = materializar(API, _revision([]))
    dados, _ = _ler(r, layout.ARQUIVO_BASIC_INFO)
    assert dados["spec"]["template"] == ""
    assert "creationDate" not in dados["spec"]
    assert "lastUpdate" not in dados["spec"]


# --- V-25: o tombstone vira lista completa ---------------------------------


def test_tombstone_vira_lista_completa_sem_o_item_suprimido():
    r = materializar(
        API,
        _revision(
            [{"method": "GET", "path": "/tarefas", "interceptors": [TOMBSTONE]}]
        ),
    )
    dados, texto = _ler(r, "get_tarefas.yaml")

    assert dados["inherit"] is False
    tipos = [i["type"] for i in dados["interceptors_request"]]
    assert "XSS threat protection" not in tipos
    # o restante do fluxo herdado continua lá, explícito
    assert tipos == ["Custom", "Log"]
    # O comentário explica a regra, sem citar documento interno (T1).
    assert "deixa de executar, do herdado: XSS threat protection" in texto
    assert "fluxo completo que vale aqui" in texto


def test_tudo_marcado_e_nada_proprio_vira_rota_sem_interceptors():
    marcacoes = [
        dict(TOMBSTONE, id=60 + n, type=i["type"], parent={"id": i["id"], "idTemp": i["id"]})
        for n, i in enumerate(RAIZ)
        if i["executionPoint"] in ("FIRST", "SECOND")
    ]
    r = materializar(
        API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": marcacoes}])
    )
    dados, texto = _ler(r, "get_tarefas.yaml")
    assert dados["inherit"] is False
    assert "interceptors_request" not in dados and "interceptors_response" not in dados
    assert "não executa nenhum interceptor" in texto


def test_tombstone_nao_vira_apenas_comentario():
    """O comentário não é publicável: republicar traria o item de volta."""
    r = materializar(
        API,
        _revision(
            [{"method": "GET", "path": "/tarefas", "interceptors": [TOMBSTONE]}]
        ),
    )
    dados, _ = _ler(r, "get_tarefas.yaml")
    assert dados.get("interceptors_request"), "a lista não pode estar vazia"
    assert dados["inherit"] is False


def test_tombstone_com_parent_fora_do_escopo_e_avisado():
    orfao = dict(TOMBSTONE, parent={"id": 999999})
    r = materializar(
        API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": [orfao]}])
    )
    _, texto = _ler(r, "get_tarefas.yaml")
    assert "atenção" in texto
    assert "não está no fluxo herdado" in texto


# --- V-26: herança declarada -----------------------------------------------


def test_sem_item_proprio_declara_heranca_pura():
    r = materializar(API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}]))
    dados, texto = _ler(r, "get_tarefas.yaml")
    assert dados["inherit"] is True
    assert "apenas herda" in texto


def test_lista_propria_sem_marcacao_vira_append():
    """Sem marcações, a rota executa o herdado e depois os próprios (V-28):
    `inherit: true` com os itens fecha o round-trip."""
    novo = {"id": 1, "type": "Payload size", "executionPoint": "FIRST", "content": '{"maxSize": 2048}'}
    r = materializar(
        API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": [novo]}])
    )
    dados, texto = _ler(r, "get_tarefas.yaml")
    assert dados["inherit"] is True
    assert [i["type"] for i in dados["interceptors_request"]] == ["Payload size"]
    assert "executam depois do fluxo herdado" in texto


def test_copia_do_herdado_sem_marcacao_tambem_e_append():
    """A cópia executa de novo, depois do herdado: é o que a rota faz no Manager."""
    reproduz = [
        {"id": 50, "type": "Custom", "customInterceptorId": 32, "executionPoint": "FIRST"},
    ]
    r = materializar(
        API,
        _revision([{"method": "GET", "path": "/tarefas", "interceptors": reproduz}]),
    )
    dados, _ = _ler(r, "get_tarefas.yaml")
    assert dados["inherit"] is True
    assert dados["interceptors_request"] == [{"type": "Custom", "id": 32}]


# --- reparos de serialização ------------------------------------------------


def test_string_numerica_do_wire_continua_string():
    item = {"id": 1, "type": "Rate limit", "executionPoint": "FIRST", "content": '{"quota": "1000"}'}
    r = materializar(
        API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": [item]}])
    )
    dados, _ = _ler(r, "get_tarefas.yaml")
    quota = dados["interceptors_request"][0]["content"]["quota"]
    assert quota == "1000" and isinstance(quota, str)


def test_escalar_com_indicador_yaml_nao_quebra_o_arquivo():
    """O caso real que deixou dois arquivos imparseáveis em `api-400-rev4`."""
    item = {
        "id": 1,
        "type": "Masking",
        "executionPoint": "FIRST",
        "content": '{"replaceChar": "*****"}',
    }
    r = materializar(
        API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": [item]}])
    )
    dados, _ = _ler(r, "get_tarefas.yaml")
    assert dados["interceptors_request"][0]["content"]["replaceChar"] == "*****"


# --- V-01 §6: o vazio padroniza em `null` -----------------------------------


def test_vazio_sempre_publica_null_nunca_string_vazia():
    """Decisão de 2026-10-15: `null` e `""` são distintos no armazenamento mas
    idênticos em significado, então o publisher emite **um só**.

    Trava a regra: qualquer grafia de vazio no YAML vira `None` no wire, e a
    string vazia nunca chega à plataforma.
    """
    from apiops_orchestrator.domain.services.revision_payload import _destino

    # `_destino` recebe o BLOCO do escopo, não o objeto `destination`.
    for bloco in (
        {"destination": {"url": ""}},
        {"destination": {"url": None}},
        {"destination": {}},
        {"destination": None},
        {},
    ):
        assert _destino(bloco)[0] is None, bloco


def test_url_preenchida_passa_intacta():
    from apiops_orchestrator.domain.services.revision_payload import _destino

    bloco = {"destination": {"url": "https://x", "timeout": "30"}}
    assert _destino(bloco) == ("https://x", "30")
