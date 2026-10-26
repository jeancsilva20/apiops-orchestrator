"""Materialização do layout canônico a partir do wire (V-18, V-22, V-25, V-26).

As fixtures espelham o shape REAL lido da API 417 / revisão 9175, incluindo o
tombstone com `parent.id`.
"""

import yaml

from apiops_orchestrator.domain.services import repo_layout as layout
from apiops_orchestrator.domain.services.repo_materializer import materialize

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


def _revision(operations):
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
                "operations": operations,
            }
        ],
    }


def _read(resultado, suffix):
    file = next(a for a in resultado.files if a.file_path.endswith(suffix))
    return yaml.safe_load(file.text), file.text


def test_arvore_canonica_completa():
    r = materialize(API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}]))
    paths = set(r.paths)
    assert layout.BASIC_INFO_FILE in paths
    assert layout.ROOT_FILE in paths
    assert "resources/tarefas/resource.yaml" in paths
    assert "resources/tarefas/get_tarefas.yaml" in paths


def test_todo_arquivo_gerado_e_yaml_valido():
    r = materialize(API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}]))
    for file in r.files:
        yaml.safe_load(file.text)


def test_materializacao_e_deterministica():
    rev = _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}])
    a, b = materialize(API, rev), materialize(API, rev)
    assert [(x.file_path, x.text) for x in a.files] == [
        (x.file_path, x.text) for x in b.files
    ]


def test_estado_nao_governado_fica_fora_do_yaml(_=None):
    """V-22: o que está fora de FIRST/SECOND volta intacto, mas não é versionado."""
    r = materialize(API, _revision([]))
    root, text = _read(r, layout.ROOT_FILE)
    ids = [i.get("id") for i in root.get("interceptors_request") or []]
    assert 178 not in ids
    assert "não governado" in text


def test_basic_info_declara_template_vazio_porque_o_wire_nao_tem():
    """D-12: a plataforma não tem a chave `template` (8 confirmações de ausência)."""
    r = materialize(API, _revision([]))
    data, _ = _read(r, layout.BASIC_INFO_FILE)
    assert data["spec"]["template"] == ""
    assert "creationDate" not in data["spec"]
    assert "lastUpdate" not in data["spec"]


# --- V-25: o tombstone vira lista completa ---------------------------------


def test_tombstone_vira_lista_completa_sem_o_item_suprimido():
    r = materialize(
        API,
        _revision(
            [{"method": "GET", "path": "/tarefas", "interceptors": [TOMBSTONE]}]
        ),
    )
    data, text = _read(r, "get_tarefas.yaml")

    assert data["inherit"] is False
    tipos = [i["type"] for i in data["interceptors_request"]]
    assert "XSS threat protection" not in tipos
    # o restante do fluxo herdado continua lá, explícito
    assert tipos == ["Custom", "Log"]
    # O comentário explica a regra, sem citar documento interno (T1).
    assert "deixa de executar, do herdado: XSS threat protection" in text
    assert "fluxo completo que vale aqui" in text


def test_tudo_marcado_e_nada_proprio_vira_rota_sem_interceptors():
    tombstones = [
        dict(TOMBSTONE, id=60 + n, type=i["type"], parent={"id": i["id"], "idTemp": i["id"]})
        for n, i in enumerate(RAIZ)
        if i["executionPoint"] in ("FIRST", "SECOND")
    ]
    r = materialize(
        API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": tombstones}])
    )
    data, text = _read(r, "get_tarefas.yaml")
    assert data["inherit"] is False
    assert "interceptors_request" not in data and "interceptors_response" not in data
    assert "não executa nenhum interceptor" in text


def test_tombstone_nao_vira_apenas_comentario():
    """O comentário não é publicável: republicar traria o item de volta."""
    r = materialize(
        API,
        _revision(
            [{"method": "GET", "path": "/tarefas", "interceptors": [TOMBSTONE]}]
        ),
    )
    data, _ = _read(r, "get_tarefas.yaml")
    assert data.get("interceptors_request"), "a lista não pode estar vazia"
    assert data["inherit"] is False


def test_tombstone_com_parent_fora_do_escopo_e_avisado():
    orfao = dict(TOMBSTONE, parent={"id": 999999})
    r = materialize(
        API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": [orfao]}])
    )
    _, text = _read(r, "get_tarefas.yaml")
    assert "atenção" in text
    assert "não está no fluxo herdado" in text


# --- V-26: herança declarada -----------------------------------------------


def test_sem_item_proprio_declara_heranca_pura():
    r = materialize(API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}]))
    data, text = _read(r, "get_tarefas.yaml")
    assert data["inherit"] is True
    assert "apenas herda" in text


def test_lista_propria_sem_marcacao_vira_append():
    """Sem marcações, a rota executa o herdado e depois os próprios (V-28):
    `inherit: true` com os itens fecha o round-trip."""
    new = {"id": 1, "type": "Payload size", "executionPoint": "FIRST", "content": '{"maxSize": 2048}'}
    r = materialize(
        API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": [new]}])
    )
    data, text = _read(r, "get_tarefas.yaml")
    assert data["inherit"] is True
    assert [i["type"] for i in data["interceptors_request"]] == ["Payload size"]
    assert "executam depois do fluxo herdado" in text


def test_copia_do_herdado_sem_marcacao_tambem_e_append():
    """A cópia executa de novo, depois do herdado: é o que a rota faz no Manager."""
    reproduz = [
        {"id": 50, "type": "Custom", "customInterceptorId": 32, "executionPoint": "FIRST"},
    ]
    r = materialize(
        API,
        _revision([{"method": "GET", "path": "/tarefas", "interceptors": reproduz}]),
    )
    data, _ = _read(r, "get_tarefas.yaml")
    assert data["inherit"] is True
    assert data["interceptors_request"] == [{"type": "Custom", "id": 32}]


# --- reparos de serialização ------------------------------------------------


def test_string_numerica_do_wire_continua_string():
    item = {"id": 1, "type": "Rate limit", "executionPoint": "FIRST", "content": '{"quota": "1000"}'}
    r = materialize(
        API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": [item]}])
    )
    data, _ = _read(r, "get_tarefas.yaml")
    quota = data["interceptors_request"][0]["content"]["quota"]
    assert quota == "1000" and isinstance(quota, str)


def test_escalar_com_indicador_yaml_nao_quebra_o_arquivo():
    """O caso real que deixou dois arquivos imparseáveis em `api-400-rev4`."""
    item = {
        "id": 1,
        "type": "Masking",
        "executionPoint": "FIRST",
        "content": '{"replaceChar": "*****"}',
    }
    r = materialize(
        API, _revision([{"method": "GET", "path": "/tarefas", "interceptors": [item]}])
    )
    data, _ = _read(r, "get_tarefas.yaml")
    assert data["interceptors_request"][0]["content"]["replaceChar"] == "*****"


# --- V-01 §6: o vazio padroniza em `null` -----------------------------------


def test_vazio_sempre_publica_null_nunca_string_vazia():
    """Decisão de 2026-10-15: `null` e `""` são distintos no armazenamento mas
    idênticos em significado, então o publisher emite **um só**.

    Trava a regra: qualquer grafia de vazio no YAML vira `None` no wire, e a
    string vazia nunca chega à plataforma.
    """
    from apiops_orchestrator.domain.services.revision_payload import _destination

    # `_destination` recebe o BLOCO do escopo, não o objeto `destination`.
    for block in (
        {"destination": {"url": ""}},
        {"destination": {"url": None}},
        {"destination": {}},
        {"destination": None},
        {},
    ):
        assert _destination(block)[0] is None, block


def test_url_preenchida_passa_intacta():
    from apiops_orchestrator.domain.services.revision_payload import _destination

    block = {"destination": {"url": "https://x", "timeout": "30"}}
    assert _destination(block) == ("https://x", "30")
