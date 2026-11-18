"""Materialização do layout canônico a partir do wire (V-18, V-22, V-25, V-26).

As fixtures espelham o shape REAL lido da API 417 / revisão 9175, incluindo o
tombstone com `parent.id`.
"""

import yaml

from apiops_orchestrator.domain.models.api_model import Api, Revision
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
    return Revision.model_validate(_revision_wire(operations))


def _revision_wire(operations):
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
    r = materialize(Api.model_validate(API), _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}]))
    paths = set(r.paths)
    assert layout.BASIC_INFO_FILE in paths
    assert layout.ROOT_FILE in paths
    assert "resources/tarefas/resource.yaml" in paths
    assert "resources/tarefas/get_tarefas.yaml" in paths


def test_todo_arquivo_gerado_e_yaml_valido():
    r = materialize(Api.model_validate(API), _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}]))
    for file in r.files:
        yaml.safe_load(file.text)


def test_materializacao_e_deterministica():
    rev = _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}])
    a, b = materialize(Api.model_validate(API), rev), materialize(Api.model_validate(API), rev)
    assert [(x.file_path, x.text) for x in a.files] == [
        (x.file_path, x.text) for x in b.files
    ]


def test_estado_nao_governado_fica_fora_do_yaml(_=None):
    """V-22: o que está fora de FIRST/SECOND volta intacto, mas não é versionado."""
    r = materialize(Api.model_validate(API), _revision([]))
    root, text = _read(r, layout.ROOT_FILE)
    ids = [i.get("id") for i in root.get("interceptors_request") or []]
    assert 178 not in ids
    assert "178" not in text


def test_all_yaml_nao_cita_a_revisao():
    """O cabeçalho é fixo: o id da revisão muda por branch e conflitaria em todo merge."""
    r = materialize(Api.model_validate(API), _revision([]))
    _, text = _read(r, layout.ROOT_FILE)
    assert text.startswith("# escopo raiz da API")
    assert "9175" not in text and "revisionNumber" not in text


def test_basic_info_declara_template_vazio_porque_o_wire_nao_tem():
    """D-12: a plataforma não tem a chave `template` (8 confirmações de ausência)."""
    r = materialize(Api.model_validate(API), _revision([]))
    data, _ = _read(r, layout.BASIC_INFO_FILE)
    assert data["spec"]["template"] == ""
    assert "creationDate" not in data["spec"]
    assert "lastUpdate" not in data["spec"]


def test_basic_info_grava_o_template_recebido():
    """O `template` vem do arquivo que já existe no repositório, nunca do Manager."""
    r = materialize(Api.model_validate(API), _revision([]), template=414)
    data, _ = _read(r, layout.BASIC_INFO_FILE)
    assert data["spec"]["template"] == 414
    assert data["spec"]["id"] == 417


def test_basic_info_com_apitags_vazia_declara_lista_vazia():
    r = materialize(Api.model_validate(dict(API, apiTags=[])), _revision([]))
    data, _ = _read(r, layout.BASIC_INFO_FILE)
    assert data["spec"]["apiTags"] == []


def test_basic_info_sem_apitags_nao_declara_a_chave():
    api = {k: v for k, v in API.items() if k != "apiTags"}
    r = materialize(Api.model_validate(api), _revision([]))
    data, text = _read(r, layout.BASIC_INFO_FILE)
    assert "apiTags" not in data["spec"] and "apiTags" not in text


# --- V-25: o tombstone vira lista completa ---------------------------------


def test_tombstone_vira_lista_completa_sem_o_item_suprimido():
    r = materialize(
        Api.model_validate(API),
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
    # O comentário é fixo: explica os dois valores e não cita o que foi removido.
    assert "# inherit: false ignora o fluxo herdado" in text
    assert "XSS" not in text.split("inherit: false")[0]


def test_tudo_marcado_e_nada_proprio_vira_rota_sem_interceptors():
    tombstones = [
        dict(TOMBSTONE, id=60 + n, type=i["type"], parent={"id": i["id"], "idTemp": i["id"]})
        for n, i in enumerate(RAIZ)
        if i["executionPoint"] in ("FIRST", "SECOND")
    ]
    r = materialize(
        Api.model_validate(API), _revision([{"method": "GET", "path": "/tarefas", "interceptors": tombstones}])
    )
    data, _ = _read(r, "get_tarefas.yaml")
    assert data["inherit"] is False
    assert "interceptors_request" not in data and "interceptors_response" not in data


def test_tombstone_nao_vira_apenas_comentario():
    """O comentário não é publicável: republicar traria o item de volta."""
    r = materialize(
        Api.model_validate(API),
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
        Api.model_validate(API), _revision([{"method": "GET", "path": "/tarefas", "interceptors": [orfao]}])
    )
    _, text = _read(r, "get_tarefas.yaml")
    assert "999999" not in text
    assert any(
        "GET /tarefas: REMOVED aponta para interceptor fora do fluxo herdado: 999999" == w
        for w in r.warnings
    )


def test_parent_com_status_desconhecido_vira_proprio_com_aviso():
    estranho = dict(TOMBSTONE, status="PENDING")
    r = materialize(
        Api.model_validate(API), _revision([{"method": "GET", "path": "/tarefas", "interceptors": [estranho]}])
    )
    data, _ = _read(r, "get_tarefas.yaml")
    assert data["inherit"] is True
    assert [i["type"] for i in data["interceptors_request"]] == ["XSS threat protection"]
    assert any("status 'PENDING' não reconhecido" in w for w in r.warnings)


def test_proprio_identico_ao_herdado_e_avisado():
    copia = {"id": 50, "type": "Log", "executionPoint": "FIRST", "content": '{"acceptedTerms": true}'}
    r = materialize(
        Api.model_validate(API), _revision([{"method": "GET", "path": "/tarefas", "interceptors": [copia]}])
    )
    assert any("Log próprio repete um herdado idêntico" in w for w in r.warnings)


# --- V-26: herança declarada -----------------------------------------------


def test_sem_item_proprio_declara_heranca_pura():
    r = materialize(Api.model_validate(API), _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}]))
    data, text = _read(r, "get_tarefas.yaml")
    assert data["inherit"] is True
    assert "# inherit: true  executa o fluxo herdado" in text
    assert "interceptors_request" not in data


def test_lista_propria_sem_marcacao_vira_append():
    """Sem marcações, a rota executa o herdado e depois os próprios (V-28):
    `inherit: true` com os itens fecha o round-trip."""
    new = {"id": 1, "type": "Payload size", "executionPoint": "FIRST", "content": '{"maxSize": 2048}'}
    r = materialize(
        Api.model_validate(API), _revision([{"method": "GET", "path": "/tarefas", "interceptors": [new]}])
    )
    data, text = _read(r, "get_tarefas.yaml")
    assert data["inherit"] is True
    assert [i["type"] for i in data["interceptors_request"]] == ["Payload size"]
    assert "# inherit: true  executa o fluxo herdado" in text


def test_copia_do_herdado_sem_marcacao_tambem_e_append():
    """A cópia executa de novo, depois do herdado: é o que a rota faz no Manager."""
    reproduz = [
        {"id": 50, "type": "Custom", "customInterceptorId": 32, "executionPoint": "FIRST"},
    ]
    r = materialize(
        Api.model_validate(API),
        _revision([{"method": "GET", "path": "/tarefas", "interceptors": reproduz}]),
    )
    data, _ = _read(r, "get_tarefas.yaml")
    assert data["inherit"] is True
    assert data["interceptors_request"] == [{"type": "Custom", "id": 32}]


# --- reparos de serialização ------------------------------------------------


def test_string_numerica_do_wire_continua_string():
    item = {"id": 1, "type": "Rate limit", "executionPoint": "FIRST", "content": '{"quota": "1000"}'}
    r = materialize(
        Api.model_validate(API), _revision([{"method": "GET", "path": "/tarefas", "interceptors": [item]}])
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
        Api.model_validate(API), _revision([{"method": "GET", "path": "/tarefas", "interceptors": [item]}])
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


# --- contrato OpenAPI ---------------------------------------------------------


SWAGGER = {
    "openapi": "3.0.1",
    "info": {"contact": {"name": "Time"}},
    "tags": [{"name": "Tarefas"}],
    "components": {"schemas": {"Tarefa": {"type": "object"}}},
    "paths": {
        "/tarefas": {
            "get": {
                "summary": "Lista as tarefas",
                "responses": {"200": {"description": "OK"}},
                "x-interceptors": {},
            }
        }
    },
}


def test_sem_swagger_nao_escreve_components_nem_contrato():
    r = materialize(Api.model_validate(API), _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}]))
    assert layout.COMPONENTS_FILE not in r.paths
    _, text = _read(r, "get_tarefas.yaml")
    assert "contrato" not in text


def test_com_swagger_escreve_components_basic_info_e_rota():
    r = materialize(
        Api.model_validate(API),
        _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}]),
        swagger=SWAGGER,
    )
    components, text = _read(r, layout.COMPONENTS_FILE)
    assert components == {"schemas": {"Tarefa": {"type": "object"}}}
    assert text.startswith("# componentes OpenAPI")

    basic, _ = _read(r, layout.BASIC_INFO_FILE)
    assert basic["spec"]["contact"] == {"name": "Time"}
    assert basic["spec"]["tags"] == [{"name": "Tarefas"}]
    assert "security" not in basic["spec"]

    op, text = _read(r, "get_tarefas.yaml")
    assert op["summary"] == "Lista as tarefas"
    assert op["responses"] == {"200": {"description": "OK"}}
    assert "x-interceptors" not in text
    assert text.index("inherit:") < text.index("# contrato OpenAPI da rota")
    assert r.warnings == []


def test_components_vazio_sai_como_mapa_vazio():
    swagger = {"openapi": "3.0.0", "paths": {}}
    r = materialize(Api.model_validate(API), _revision([]), swagger=swagger)
    components, text = _read(r, layout.COMPONENTS_FILE)
    assert components == {} and text.rstrip().endswith("{}")


def test_rota_fora_do_swagger_e_avisada_e_sem_contrato():
    r = materialize(
        Api.model_validate(API),
        _revision([{"method": "DELETE", "path": "/tarefas", "interceptors": []}]),
        swagger=SWAGGER,
    )
    op, _ = _read(r, "delete_tarefas.yaml")
    assert "responses" not in op
    assert any(w.startswith("DELETE /tarefas: rota fora do swagger") for w in r.warnings)


def test_rota_sem_responses_no_swagger_e_avisada():
    swagger = {"openapi": "3.0.0", "paths": {"/tarefas": {"get": {"summary": "Lista"}}}}
    r = materialize(
        Api.model_validate(API), _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}]), swagger=swagger
    )
    op, _ = _read(r, "get_tarefas.yaml")
    assert op["summary"] == "Lista" and "responses" not in op
    assert any("swagger sem responses na rota" in w for w in r.warnings)


def test_texto_multilinha_do_contrato_sai_em_bloco_literal():
    swagger = {
        "openapi": "3.0.0",
        "paths": {"/tarefas": {"get": {"summary": "a", "responses": {"200": {"description": "linha 1\nlinha 2"}}}}},
    }
    r = materialize(
        Api.model_validate(API), _revision([{"method": "GET", "path": "/tarefas", "interceptors": []}]), swagger=swagger
    )
    op, text = _read(r, "get_tarefas.yaml")
    assert op["responses"]["200"]["description"] == "linha 1\nlinha 2"
    assert "description: |" in text


# --- Mock ----------------------------------------------------------------------

MOCK_AS_TEXT = {
    "id": 500, "type": "Mock", "executionPoint": "FIRST", "position": 1,
    "content": '{"body": "{\\"ok\\": true}", "status": "200", "headers": "Content-Type: application/json"}',
}
MOCK_AS_OBJECT = {
    "id": 500, "type": "Mock", "executionPoint": "FIRST", "position": 1,
    "content": '{"body": {"ok": true}, "status": 200, "headers": "Content-Type: application/json"}',
}


def _mock_file(interceptor):
    r = materialize(
        Api.model_validate(API),
        _revision([{"method": "GET", "path": "/mock", "interceptors": [interceptor]}]),
    )
    return _read(r, "get_mock.yaml")


def test_mock_guardado_como_texto_vira_objeto_e_numero():
    """The repository declares `body` as object and `status` as number (the inverse of the PUT)."""
    data, _ = _mock_file(MOCK_AS_TEXT)
    mock = next(i for i in data["interceptors_request"] if i["type"] == "Mock")
    assert mock["content"]["body"] == {"ok": True}
    assert mock["content"]["status"] == 200


def test_mock_guardado_como_objeto_gera_o_mesmo_arquivo():
    """The Manager answers either form depending on who wrote the Mock; the file is one."""
    assert _mock_file(MOCK_AS_TEXT)[1] == _mock_file(MOCK_AS_OBJECT)[1]


def test_content_como_dicionario_nao_quebra_a_comparacao_com_o_herdado():
    item = {"id": 501, "type": "Log", "executionPoint": "FIRST", "position": 1,
            "content": {"acceptedTerms": True}}
    data, _ = _mock_file(item)
    assert {"type": "Log", "content": {"acceptedTerms": True}} in data["interceptors_request"]


def test_content_vazio_do_manager_vira_objeto_vazio_declarado():
    """`'{}'` in the Manager must come back as `'{}'` in the PUT: omitting the key would send null."""
    item = {"id": 502, "type": "XML threat protection", "executionPoint": "FIRST", "position": 1,
            "content": "{}"}
    data, text = _mock_file(item)
    assert {"type": "XML threat protection", "content": {}} in data["interceptors_request"]
    assert "    content: {}" in text


def test_content_nulo_do_manager_nao_declara_a_chave():
    item = {"id": 503, "type": "XML threat protection", "executionPoint": "FIRST", "position": 1,
            "content": None}
    data, _ = _mock_file(item)
    assert {"type": "XML threat protection"} in data["interceptors_request"]
