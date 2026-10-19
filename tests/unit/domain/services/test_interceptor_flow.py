"""Partição e aritmética de identidade dos fluxos (V-22, W-9)."""

import json

import pytest

from apiops_orchestrator.domain.services.interceptor_flow import (
    chave_interceptor,
    construir_item_novo,
    maior_identificador,
    FluxoDoEscopo,
    montar_fluxo_do_escopo,
    resolver_fluxo_declarado,
    particionar,
    preparar_contador_idtemp,
)

REMOTOS = [
    {"type": "Custom", "customInterceptorId": 32, "executionPoint": "FIRST", "position": 1},
    {"type": "Log", "executionPoint": "FIRST", "position": 2, "content": {"acceptedTerms": True}},
    {"type": "Custom", "customInterceptorId": 178, "executionPoint": "THIRD", "position": 3},
    {"type": "Log", "executionPoint": "SECOND", "position": 4},
    {"type": "Rate limit", "executionPoint": None, "position": 5},
]


def test_particao_separa_governado_de_preservado():
    governados, preservados = particionar(REMOTOS)
    assert [g["position"] for g in governados] == [1, 2, 4]
    assert [p["position"] for p in preservados] == [3, 5]


def test_preservado_volta_intacto_e_sem_copia():
    """V-22: o repositório não é autoridade sobre o não governado."""
    _, preservados = particionar(REMOTOS)
    assert preservados[0] is REMOTOS[2]
    assert preservados[0]["customInterceptorId"] == 178


def test_particao_preserva_a_ordem_relativa():
    governados, _ = particionar(REMOTOS)
    assert governados == [REMOTOS[0], REMOTOS[1], REMOTOS[3]]


def test_particao_tolera_lista_vazia_e_none():
    assert particionar([]) == ([], [])
    assert particionar(None) == ([], [])


def test_execution_point_e_case_insensitive():
    governados, _ = particionar([{"type": "Log", "executionPoint": "first"}])
    assert len(governados) == 1


# --- chave de casamento ----------------------------------------------------


def test_custom_casa_pelo_id_do_catalogo():
    """Mesmo id, mesmo objeto no tenant — o `content` não entra na chave."""
    do_wire = {"type": "Custom", "customInterceptorId": 32, "executionPoint": "FIRST"}
    do_repo = {"type": "Custom", "id": 32, "executionPoint": "FIRST"}
    assert chave_interceptor(do_wire) == chave_interceptor(do_repo)


def test_nativos_de_tipos_diferentes_nao_casam():
    a = {"type": "Log", "executionPoint": "FIRST"}
    b = {"type": "Payload size", "executionPoint": "FIRST"}
    assert chave_interceptor(a) != chave_interceptor(b)


def test_mesmo_tipo_em_pontos_diferentes_nao_casa():
    a = {"type": "Log", "executionPoint": "FIRST"}
    b = {"type": "Log", "executionPoint": "SECOND"}
    assert chave_interceptor(a) != chave_interceptor(b)


# --- piso do contador global de idTemp (W-9) -------------------------------


def test_maior_identificador_varre_a_arvore_inteira():
    """W-9: o `idTemp` é do PAYLOAD, não do escopo.

    O contador precisa enxergar raiz, recursos e operações de uma vez — foi a
    contagem por escopo que fez o Manager descartar um item com HTTP 200.
    """
    payload = {
        "interceptors": [{"id": 3, "idTemp": 3, "position": 1}],
        "resources": [
            {
                "id": 9179,
                "interceptors": [{"id": 7, "idTemp": 7, "position": 2}],
                "operations": [
                    {"id": 9183, "interceptors": [{"id": 12, "idTemp": 12, "position": 3}]}
                ],
            }
        ],
    }
    assert maior_identificador(payload) == 9183


def test_maior_identificador_aceita_numero_em_string():
    assert maior_identificador({"position": "42"}) == 42


def test_maior_identificador_ignora_booleano():
    """`True` é `int` em Python — contá-lo como 1 seria um erro silencioso."""
    assert maior_identificador({"soft": True, "id": 0}) == 0


def test_maior_identificador_de_arvore_vazia():
    assert maior_identificador({}) == 0
    assert maior_identificador([]) == 0


# --- contador global de idTemp (W-1, W-9) ----------------------------------


def test_contador_comeca_acima_de_tudo_que_existe():
    payload = {"interceptors": [{"id": 19504, "idTemp": 19504, "position": 8}]}
    contador = preparar_contador_idtemp(payload)
    assert next(contador) == 19505
    assert next(contador) == 19506


def test_contador_e_unico_entre_escopos():
    """W-9: o erro real foi cada escopo calcular 'a próxima posição livre'."""
    contador = preparar_contador_idtemp({"id": 7})
    raiz = [next(contador) for _ in range(2)]
    recurso = [next(contador) for _ in range(2)]
    assert len(set(raiz + recurso)) == 4


def test_item_novo_vai_com_id_nulo_e_idtemp_preenchido():
    item = construir_item_novo(
        tipo="Log", execution_point="FIRST", idtemp=42, position=3, content={"a": 1}
    )
    assert item["id"] is None
    assert item["idTemp"] == 42
    assert item["status"] == "REFERENCE"


def test_item_novo_sem_idtemp_e_recusado():
    """W-1: sem `idTemp` o Manager devolve 500 com `errors: []`."""
    with pytest.raises(ValueError, match="idTemp"):
        construir_item_novo(
            tipo="Log", execution_point="FIRST", idtemp=None, position=1
        )


def test_item_novo_preserva_o_custom_interceptor_id():
    item = construir_item_novo(
        tipo="Custom",
        execution_point="FIRST",
        idtemp=5,
        position=1,
        custom_interceptor_id=32,
    )
    assert item["customInterceptorId"] == 32


# --- resolucao do fluxo a partir do repositorio (V-27) ---------------------


HERDADO = [{"type": "Log", "executionPoint": "FIRST"},
           {"type": "Rate limit", "executionPoint": "FIRST"}]
PROPRIO = [{"type": "Payload size", "executionPoint": "FIRST"}]


def test_raiz_nao_herda_de_ninguem():
    """O efetivo da raiz e exatamente o que o `all.yaml` declara."""
    fluxo = resolver_fluxo_declarado(PROPRIO, HERDADO, raiz=True)
    assert [i["type"] for i in fluxo.efetivo] == ["Payload size"]
    assert not fluxo.heranca_pura and not fluxo.contraditorio


def test_inherit_true_sem_itens_e_heranca_pura():
    fluxo = resolver_fluxo_declarado([], HERDADO, inherit=True)
    assert [i["type"] for i in fluxo.efetivo] == ["Log", "Rate limit"]
    assert fluxo.heranca_pura and not fluxo.contraditorio


def test_inherit_true_com_itens_soma_ao_fluxo_do_pai():
    """O caso que a V-26 nao expressava: restaurar heranca E acrescentar."""
    fluxo = resolver_fluxo_declarado(PROPRIO, HERDADO, inherit=True)
    assert [i["type"] for i in fluxo.efetivo] == ["Log", "Rate limit", "Payload size"]
    assert not fluxo.heranca_pura


def test_inherit_false_com_itens_substitui():
    fluxo = resolver_fluxo_declarado(PROPRIO, HERDADO, inherit=False)
    assert [i["type"] for i in fluxo.efetivo] == ["Payload size"]
    assert not fluxo.heranca_pura


def test_inherit_false_sem_itens_e_contraditorio():
    """T06: a plataforma nao representa escopo sem fluxo. O efetivo real e o do
    pai, porque e isso que vai acontecer — mas a declaracao fica marcada."""
    fluxo = resolver_fluxo_declarado([], HERDADO, inherit=False)
    assert [i["type"] for i in fluxo.efetivo] == ["Log", "Rate limit"]
    assert fluxo.heranca_pura and fluxo.contraditorio


def test_o_resolvedor_nao_altera_as_listas_recebidas():
    declarados, herdado = list(PROPRIO), list(HERDADO)
    resolver_fluxo_declarado(declarados, herdado, inherit=True)
    assert declarados == PROPRIO and herdado == HERDADO


# --- montagem do fluxo no wire (W-3, W-9, V-22) ----------------------------


REMOTO_RESOLVIDO = [
    {"id": 1, "type": "Custom", "customInterceptorId": 32, "executionPoint": "FIRST", "position": 0},
    {"id": 2, "type": "Log", "executionPoint": "FIRST", "position": 2},
    {"id": 3, "type": "XSS threat protection", "executionPoint": "FIRST", "position": 6},
]


def _resolvido(*tipos):
    return FluxoDoEscopo(
        efetivo=[{"type": t, "executionPoint": "FIRST"} for t in tipos]
    )


def test_heranca_pura_manda_a_lista_governada_vazia():
    """V-27 2: `[]` e a codificacao compacta de "o fluxo do pai", e mantem a
    propagacao viva quando o `all.yaml` muda."""
    fluxo = montar_fluxo_do_escopo(
        FluxoDoEscopo(efetivo=list(HERDADO), heranca_pura=True),
        REMOTO_RESOLVIDO,
        gerar_idtemp=preparar_contador_idtemp({}),
    )
    assert fluxo == []


def test_position_nao_e_renumerada_e_segue_a_ordem_declarada():
    """W-3: as posicoes reais nem sao contiguas — a raiz da 417 usa 0,2,...,8.

    O escopo reusa os numeros que ja ocupa (2 e 6) e o item novo estende a
    faixa (7); o conjunto e redistribuido na ordem do YAML, sem virar 1..N.
    """
    fluxo = montar_fluxo_do_escopo(
        _resolvido("Custom", "Log", "XSS threat protection"),
        REMOTO_RESOLVIDO,
        gerar_idtemp=preparar_contador_idtemp({}),
    )
    # O `Custom` do resolvido nao traz id: nasce novo, mas fica onde foi declarado.
    assert [(i["type"], i["position"]) for i in fluxo] == [
        ("Custom", 2),
        ("Log", 6),
        ("XSS threat protection", 7),
    ]


def test_item_ja_presente_no_remoto_reusa_a_identidade():
    fluxo = montar_fluxo_do_escopo(
        _resolvido("Log"),
        REMOTO_RESOLVIDO,
        gerar_idtemp=preparar_contador_idtemp({}),
    )
    assert len(fluxo) == 1
    assert fluxo[0]["id"] == 2 and fluxo[0]["position"] == 2


# --- o repositorio prevalece no que declara (V-22 §3, V-11 §4, D14) ------------

REMOTO_COM_CONTENT = [
    {"id": 10, "idTemp": 10, "type": "Log", "executionPoint": "FIRST", "position": 2,
     "status": "REFERENCE", "content": '{"encryptContent": false}'},
    {"id": 11, "idTemp": 11, "type": "Rate limit", "executionPoint": "FIRST", "position": 4,
     "status": "REFERENCE", "content": '{"quota": "1000", "interval": "SECOND"}'},
    {"id": 12, "idTemp": 12, "type": "Payload size", "executionPoint": "FIRST", "position": 5,
     "status": "REFERENCE", "content": '{"maxSize": "2048"}'},
    {"id": 13, "idTemp": 13, "type": "Custom", "customInterceptorId": 32, "executionPoint": "FIRST",
     "position": 7, "status": "REFERENCE", "content": '{"id": 32, "name": "Release Notes"}'},
]


def _declarado(tipo, content=None, custom_id=None, ponto="FIRST"):
    return {
        "type": tipo,
        "executionPoint": ponto,
        "content": content,
        "customInterceptorId": custom_id,
    }


def _montar(*declarados, remotos=REMOTO_COM_CONTENT):
    return montar_fluxo_do_escopo(
        FluxoDoEscopo(efetivo=list(declarados)),
        remotos,
        gerar_idtemp=preparar_contador_idtemp({"id": 100}),
    )


def test_content_de_nativo_existente_vem_do_yaml():
    """Regressao do S10: quota 1000 -> 500 era descartada e o Manager mantinha 1000."""
    fluxo = _montar(
        _declarado("Log", {"encryptContent": False}),
        _declarado("Rate limit", {"quota": "500", "interval": "SECOND"}),
        _declarado("Payload size", {"maxSize": "2048"}),
        _declarado("Custom", custom_id=32),
    )
    rate = next(i for i in fluxo if i["type"] == "Rate limit")
    assert json.loads(rate["content"]) == {"quota": "500", "interval": "SECOND"}
    # identidade tecnica reaproveitada
    assert rate["id"] == 11 and rate["idTemp"] == 11 and rate["status"] == "REFERENCE"


def test_custom_existente_mantem_o_content_do_manager():
    """V-11 §4: mesmo id e o mesmo objeto no tenant."""
    fluxo = _montar(_declarado("Custom", custom_id=32))
    assert fluxo[0]["content"] == '{"id": 32, "name": "Release Notes"}'


def test_remoto_nao_e_alterado_pela_montagem():
    remotos = json.loads(json.dumps(REMOTO_COM_CONTENT))
    _montar(_declarado("Rate limit", {"quota": "1"}), remotos=remotos)
    assert remotos == REMOTO_COM_CONTENT


def test_reordenar_no_yaml_reordena_as_positions():
    fluxo = _montar(
        _declarado("Rate limit", {"quota": "1000", "interval": "SECOND"}),
        _declarado("Log", {"encryptContent": False}),
        _declarado("Payload size", {"maxSize": "2048"}),
        _declarado("Custom", custom_id=32),
    )
    por_posicao = sorted(fluxo, key=lambda i: i["position"])
    assert [i["type"] for i in por_posicao] == ["Rate limit", "Log", "Payload size", "Custom"]
    # mesmos numeros que o escopo ja ocupava
    assert sorted(i["position"] for i in fluxo) == [2, 4, 5, 7]


def test_inserir_no_meio_fica_no_meio():
    """Antes, o novo ia para o fim e 'roubava' a identidade do existente do mesmo tipo."""
    fluxo = _montar(
        _declarado("Log", {"encryptContent": False}),
        _declarado("Payload size", {"maxSize": "999"}),
        _declarado("Rate limit", {"quota": "1000", "interval": "SECOND"}),
        _declarado("Payload size", {"maxSize": "2048"}),
        _declarado("Custom", custom_id=32),
    )
    por_posicao = sorted(fluxo, key=lambda i: i["position"])
    assert [(i["type"], json.loads(i["content"]).get("maxSize")) for i in por_posicao] == [
        ("Log", None),
        ("Payload size", "999"),
        ("Rate limit", None),
        ("Payload size", "2048"),
        ("Custom", None),
    ]


def test_remover_do_meio_mantem_a_ordem_do_restante():
    fluxo = _montar(
        _declarado("Log", {"encryptContent": False}),
        _declarado("Payload size", {"maxSize": "2048"}),
        _declarado("Custom", custom_id=32),
    )
    por_posicao = sorted(fluxo, key=lambda i: i["position"])
    assert [i["type"] for i in por_posicao] == ["Log", "Payload size", "Custom"]
    assert all(i["id"] is not None for i in fluxo)


def test_request_e_response_sao_ordenados_cada_um_no_seu_ponto():
    remotos = REMOTO_COM_CONTENT + [
        {"id": 20, "type": "Log", "executionPoint": "SECOND", "position": 0,
         "content": '{"encryptContent": false}'},
    ]
    fluxo = _montar(
        _declarado("Payload size", {"maxSize": "2048"}),
        _declarado("Log", {"encryptContent": False}),
        _declarado("Log", {"encryptContent": True}, ponto="SECOND"),
        remotos=remotos,
    )
    response = [i for i in fluxo if i["executionPoint"] == "SECOND"]
    assert response[0]["position"] == 0
    assert json.loads(response[0]["content"]) == {"encryptContent": True}
    request = sorted(
        (i for i in fluxo if i["executionPoint"] == "FIRST"), key=lambda i: i["position"]
    )
    assert [i["type"] for i in request] == ["Payload size", "Log"]


def test_item_que_o_remoto_nao_tem_nasce_novo():
    fluxo = montar_fluxo_do_escopo(
        _resolvido("Payload size"),
        REMOTO_RESOLVIDO,
        gerar_idtemp=preparar_contador_idtemp({"id": 100}),
    )
    assert fluxo[0]["id"] is None and fluxo[0]["idTemp"] == 101


def test_nao_governado_volta_intacto_no_fim():
    """V-22: o repositorio nao e autoridade sobre ele."""
    remotos = REMOTO_RESOLVIDO + [
        {"id": 9, "type": "Custom", "customInterceptorId": 178, "executionPoint": "THIRD", "position": 9}
    ]
    fluxo = montar_fluxo_do_escopo(
        _resolvido("Log"), remotos, gerar_idtemp=preparar_contador_idtemp({})
    )
    assert fluxo[-1]["executionPoint"] == "THIRD"
    assert fluxo[-1] is remotos[-1]


def test_tombstone_remoto_fica_fora_do_pool_de_casamento():
    """Ele tem a MESMA chave do item que suprime (V-27): reaproveita-lo
    publicaria um `status: REMOVED` no lugar do item vivo."""
    remotos = [
        {"id": 4, "type": "Log", "executionPoint": "FIRST", "position": 1,
         "status": "REMOVED", "parent": {"id": 2}}
    ]
    fluxo = montar_fluxo_do_escopo(
        _resolvido("Log"), remotos, gerar_idtemp=preparar_contador_idtemp({})
    )
    assert len(fluxo) == 1
    assert fluxo[0]["id"] is None and fluxo[0].get("status") == "REFERENCE"


def test_itens_novos_de_escopos_diferentes_nao_colidem_em_idtemp():
    """O cenario exato do W-9, que custou um `Custom` sumido sob HTTP 200."""
    contador = preparar_contador_idtemp({"id": 10})
    raiz = montar_fluxo_do_escopo(
        FluxoDoEscopo(efetivo=[{"type": "Custom", "customInterceptorId": 32,
                                "executionPoint": "FIRST"}]),
        [], gerar_idtemp=contador,
    )
    recurso = montar_fluxo_do_escopo(
        FluxoDoEscopo(efetivo=[{"type": "Custom", "customInterceptorId": 33,
                                "executionPoint": "FIRST"}]),
        [], gerar_idtemp=contador,
    )
    assert raiz[0]["idTemp"] != recurso[0]["idTemp"]


def test_tipo_repetido_no_escopo_nao_e_deduplicado():
    """Regressao: fluxos reais REPETEM tipo.

    `/health-check` tem dois `Log` em FIRST, e a regua tambem. Casar por chave
    num `dict` perderia um deles no payload — perda silenciosa da mesma classe
    que a conferencia pos-publicacao existe para pegar. O ensaio seco da bateria
    detectou isso antes da primeira escrita: 6 enviados contra 7 presentes.
    """
    remotos = [
        {"id": 1, "type": "Log", "executionPoint": "FIRST", "position": 1, "content": "A"},
        {"id": 2, "type": "Rate limit", "executionPoint": "FIRST", "position": 2},
        {"id": 3, "type": "Log", "executionPoint": "FIRST", "position": 3, "content": "B"},
    ]
    resolvido = FluxoDoEscopo(efetivo=[
        {"type": "Log", "executionPoint": "FIRST", "content": "A"},
        {"type": "Rate limit", "executionPoint": "FIRST"},
        {"type": "Log", "executionPoint": "FIRST", "content": "B"},
    ])
    fluxo = montar_fluxo_do_escopo(
        resolvido, remotos, gerar_idtemp=preparar_contador_idtemp({})
    )

    assert len(fluxo) == 3
    assert [i["id"] for i in fluxo] == [1, 2, 3]


def test_repeticoes_do_herdado_sobrevivem_a_resolucao():
    """Dois `Log` no pai e um item proprio devem publicar tres itens."""
    fluxo = resolver_fluxo_declarado(
        [{"type": "Payload size", "executionPoint": "FIRST"}],
        [{"type": "Log", "executionPoint": "FIRST"},
         {"type": "Log", "executionPoint": "FIRST"}],
        inherit=True,
    )
    publicado = montar_fluxo_do_escopo(
        fluxo, [], gerar_idtemp=preparar_contador_idtemp({"id": 50})
    )
    assert [i["type"] for i in publicado] == ["Log", "Log", "Payload size"]


def test_content_de_item_novo_vai_como_string_json():
    """Regressão: o wire carrega `content` como STRING JSON, não como objeto.

    Um `Log` real chega como '{"acceptedTerms": true, ...}'. Enviar o dict do
    YAML cru faz o Manager recusar com **HTTP 400** — observado nos cenários
    T07, T08 e T11 da bateria contra a API 417.
    """
    import json as _json

    item = construir_item_novo(
        tipo="Payload size", execution_point="FIRST", idtemp=1, position=1,
        content={"maxSize": 2048},
    )
    assert isinstance(item["content"], str)
    assert _json.loads(item["content"]) == {"maxSize": 2048}


def test_content_ja_em_string_nao_e_reserializado():
    item = construir_item_novo(
        tipo="Log", execution_point="FIRST", idtemp=1, position=1,
        content='{"acceptedTerms": true}',
    )
    assert item["content"] == '{"acceptedTerms": true}'


def test_content_nulo_continua_nulo():
    item = construir_item_novo(tipo="X", execution_point="FIRST", idtemp=1, position=1)
    assert item["content"] is None
