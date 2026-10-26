"""Partição e aritmética de identidade dos fluxos (V-22, W-9)."""

import json

import pytest

from apiops_orchestrator.domain.services.interceptor_flow import (
    IDTEMP_FLOOR,
    tombstone_target,
    interceptor_key,
    build_new_item,
    composed_flow,
    identity,
    largest_identifier,
    ScopeFlow,
    assemble_scope_flow,
    resolve_declared_flow,
    partition,
    prepare_idtemp_counter,
)

REMOTOS = [
    {"type": "Custom", "customInterceptorId": 32, "executionPoint": "FIRST", "position": 1},
    {"type": "Log", "executionPoint": "FIRST", "position": 2, "content": {"acceptedTerms": True}},
    {"type": "Custom", "customInterceptorId": 178, "executionPoint": "THIRD", "position": 3},
    {"type": "Log", "executionPoint": "SECOND", "position": 4},
    {"type": "Rate limit", "executionPoint": None, "position": 5},
]


def test_particao_separa_governado_de_preservado():
    governed, preserved = partition(REMOTOS)
    assert [g["position"] for g in governed] == [1, 2, 4]
    assert [p["position"] for p in preserved] == [3, 5]


def test_preservado_volta_intacto_e_sem_copia():
    """V-22: o repositório não é autoridade sobre o não governado."""
    _, preserved = partition(REMOTOS)
    assert preserved[0] is REMOTOS[2]
    assert preserved[0]["customInterceptorId"] == 178


def test_particao_preserva_a_ordem_relativa():
    governed, _ = partition(REMOTOS)
    assert governed == [REMOTOS[0], REMOTOS[1], REMOTOS[3]]


def test_particao_tolera_lista_vazia_e_none():
    assert partition([]) == ([], [])
    assert partition(None) == ([], [])


def test_execution_point_e_case_insensitive():
    governed, _ = partition([{"type": "Log", "executionPoint": "first"}])
    assert len(governed) == 1


# --- chave de casamento ----------------------------------------------------


def test_custom_casa_pelo_id_do_catalogo():
    """Mesmo id, mesmo objeto no tenant — o `content` não entra na chave."""
    do_wire = {"type": "Custom", "customInterceptorId": 32, "executionPoint": "FIRST"}
    from_repo = {"type": "Custom", "id": 32, "executionPoint": "FIRST"}
    assert interceptor_key(do_wire) == interceptor_key(from_repo)


def test_nativos_de_tipos_diferentes_nao_casam():
    a = {"type": "Log", "executionPoint": "FIRST"}
    b = {"type": "Payload size", "executionPoint": "FIRST"}
    assert interceptor_key(a) != interceptor_key(b)


def test_mesmo_tipo_em_pontos_diferentes_nao_casa():
    a = {"type": "Log", "executionPoint": "FIRST"}
    b = {"type": "Log", "executionPoint": "SECOND"}
    assert interceptor_key(a) != interceptor_key(b)


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
    assert largest_identifier(payload) == 9183


def test_maior_identificador_aceita_numero_em_string():
    assert largest_identifier({"position": "42"}) == 42


def test_maior_identificador_ignora_booleano():
    """`True` é `int` em Python — contá-lo como 1 seria um erro silencioso."""
    assert largest_identifier({"soft": True, "id": 0}) == 0


def test_maior_identificador_de_arvore_vazia():
    assert largest_identifier({}) == 0
    assert largest_identifier([]) == 0


# --- contador global de idTemp (W-1, W-9) ----------------------------------


def test_contador_comeca_no_piso_longe_dos_ids_que_o_manager_gera():
    """Logo acima do maior id, o `idTemp` coincidia com ids gerados no mesmo PUT,
    e o Manager descartou uma marcação (bateria da 425)."""
    payload = {"interceptors": [{"id": 19504, "idTemp": 19504, "position": 8}]}
    counter = prepare_idtemp_counter(payload)
    assert next(counter) == IDTEMP_FLOOR
    assert next(counter) == IDTEMP_FLOOR + 1


def test_contador_comeca_acima_de_tudo_que_existe():
    payload = {"interceptors": [{"id": IDTEMP_FLOOR + 7, "position": 8}]}
    assert next(prepare_idtemp_counter(payload)) == IDTEMP_FLOOR + 8


def test_contador_e_unico_entre_escopos():
    """W-9: o erro real foi cada escopo calcular 'a próxima posição livre'."""
    counter = prepare_idtemp_counter({"id": 7})
    root = [next(counter) for _ in range(2)]
    resource = [next(counter) for _ in range(2)]
    assert len(set(root + resource)) == 4


def test_item_novo_vai_com_id_igual_ao_idtemp():
    """Formato da UI: com `id` nulo, a marcação de rota para item novo do recurso
    some quando o recurso também marca item novo da raiz (bateria da 425)."""
    item = build_new_item(
        kind="Log", execution_point="FIRST", idtemp=42, position=3, content={"a": 1}
    )
    assert item["id"] == 42
    assert item["idTemp"] == 42
    assert item["status"] == "REFERENCE"


def test_item_novo_sem_idtemp_e_recusado():
    """W-1: sem `idTemp` o Manager devolve 500 com `errors: []`."""
    with pytest.raises(ValueError, match="idTemp"):
        build_new_item(
            kind="Log", execution_point="FIRST", idtemp=None, position=1
        )


def test_item_novo_preserva_o_custom_interceptor_id():
    item = build_new_item(
        kind="Custom",
        execution_point="FIRST",
        idtemp=5,
        position=1,
        custom_interceptor_id=32,
    )
    assert item["customInterceptorId"] == 32


# --- o que cada escopo guarda e executa (V-28) -----------------------------


HERDADO = [{"type": "Log", "executionPoint": "FIRST"},
           {"type": "Rate limit", "executionPoint": "FIRST"}]
PROPRIO = [{"type": "Payload size", "executionPoint": "FIRST"}]


def test_raiz_nao_herda_de_ninguem():
    """A raiz guarda e executa exatamente o que o `all.yaml` declara."""
    flow = resolve_declared_flow(PROPRIO, HERDADO, root=True)
    assert [i["type"] for i in flow.own] == ["Payload size"]
    assert [i["type"] for i in flow.effective] == ["Payload size"]
    assert not flow.pure_inheritance and not flow.breaks_inheritance


def test_inherit_true_sem_itens_e_heranca_pura():
    flow = resolve_declared_flow([], HERDADO, inherit=True)
    assert [i["type"] for i in flow.effective] == ["Log", "Rate limit"]
    assert flow.pure_inheritance and not flow.breaks_inheritance


def test_inherit_true_com_itens_guarda_so_o_declarado():
    """A plataforma soma o herdado sozinha: copiá-lo no escopo o executaria
    duas vezes (V-28, rota `s3`)."""
    flow = resolve_declared_flow(PROPRIO, HERDADO, inherit=True)
    assert [i["type"] for i in flow.own] == ["Payload size"]
    assert [i["type"] for i in flow.effective] == ["Log", "Rate limit", "Payload size"]
    assert not flow.pure_inheritance and not flow.breaks_inheritance


def test_inherit_false_com_itens_quebra():
    flow = resolve_declared_flow(PROPRIO, HERDADO, inherit=False)
    assert [i["type"] for i in flow.own] == ["Payload size"]
    assert [i["type"] for i in flow.effective] == ["Payload size"]
    assert flow.breaks_inheritance and not flow.pure_inheritance


def test_so_inherit_false_quebra_o_herdado():
    assert resolve_declared_flow(PROPRIO, HERDADO, inherit=False).breaks_inheritance
    assert resolve_declared_flow([], HERDADO, inherit=False).breaks_inheritance
    assert not resolve_declared_flow(PROPRIO, HERDADO, inherit=True).breaks_inheritance
    assert not resolve_declared_flow(PROPRIO, HERDADO, root=True).breaks_inheritance


def test_inherit_false_sem_itens_nao_executa_nada():
    """Marcar todo o herdado sem itens próprios dá rota sem interceptors (V-28, `s7`)."""
    flow = resolve_declared_flow([], HERDADO, inherit=False)
    assert flow.own == [] and flow.effective == []
    assert flow.breaks_inheritance and not flow.pure_inheritance


def test_o_resolvedor_nao_altera_as_listas_recebidas():
    declared, inherited = list(PROPRIO), list(HERDADO)
    resolve_declared_flow(declared, inherited, inherit=True)
    assert declared == PROPRIO and inherited == HERDADO


# --- montagem do fluxo no wire (W-3, W-9, V-22) ----------------------------


REMOTO_RESOLVIDO = [
    {"id": 1, "type": "Custom", "customInterceptorId": 32, "executionPoint": "FIRST", "position": 0},
    {"id": 2, "type": "Log", "executionPoint": "FIRST", "position": 2},
    {"id": 3, "type": "XSS threat protection", "executionPoint": "FIRST", "position": 6},
]


def _resolvido(*tipos):
    return ScopeFlow(
        own=[{"type": t, "executionPoint": "FIRST"} for t in tipos]
    )


def test_heranca_pura_manda_a_lista_governada_vazia():
    """`[]` herda, e mantém a propagação viva quando o `all.yaml` muda."""
    flow = assemble_scope_flow(
        ScopeFlow(effective=list(HERDADO)),
        REMOTO_RESOLVIDO,
        generate_idtemp=prepare_idtemp_counter({}),
    )
    assert flow == []


def test_position_nao_e_renumerada_e_segue_a_ordem_declarada():
    """W-3: as posicoes reais nem sao contiguas — a raiz da 417 usa 0,2,...,8.

    O escopo reusa os numeros que ja ocupa (2 e 6) e o item novo estende a
    faixa (7); o conjunto e redistribuido na ordem do YAML, sem virar 1..N.
    """
    flow = assemble_scope_flow(
        _resolvido("Custom", "Log", "XSS threat protection"),
        REMOTO_RESOLVIDO,
        generate_idtemp=prepare_idtemp_counter({}),
    )
    # O `Custom` do resolvido nao traz id: nasce novo, mas fica onde foi declarado.
    assert [(i["type"], i["position"]) for i in flow] == [
        ("Custom", 2),
        ("Log", 6),
        ("XSS threat protection", 7),
    ]


def test_item_ja_presente_no_remoto_reusa_a_identidade():
    flow = assemble_scope_flow(
        _resolvido("Log"),
        REMOTO_RESOLVIDO,
        generate_idtemp=prepare_idtemp_counter({}),
    )
    assert len(flow) == 1
    assert flow[0]["id"] == 2 and flow[0]["position"] == 2


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


def _declarado(kind, content=None, custom_id=None, point="FIRST"):
    return {
        "type": kind,
        "executionPoint": point,
        "content": content,
        "customInterceptorId": custom_id,
    }


def _montar(*declared, remote_resources=REMOTO_COM_CONTENT):
    return assemble_scope_flow(
        ScopeFlow(own=list(declared)),
        remote_resources,
        generate_idtemp=prepare_idtemp_counter({"id": 100}),
    )


def test_content_de_nativo_existente_vem_do_yaml():
    """Regressao do S10: quota 1000 -> 500 era descartada e o Manager mantinha 1000."""
    flow = _montar(
        _declarado("Log", {"encryptContent": False}),
        _declarado("Rate limit", {"quota": "500", "interval": "SECOND"}),
        _declarado("Payload size", {"maxSize": "2048"}),
        _declarado("Custom", custom_id=32),
    )
    rate = next(i for i in flow if i["type"] == "Rate limit")
    assert json.loads(rate["content"]) == {"quota": "500", "interval": "SECOND"}
    # identidade tecnica reaproveitada
    assert rate["id"] == 11 and rate["idTemp"] == 11 and rate["status"] == "REFERENCE"


def test_custom_existente_mantem_o_content_do_manager():
    """V-11 §4: mesmo id e o mesmo objeto no tenant."""
    flow = _montar(_declarado("Custom", custom_id=32))
    assert flow[0]["content"] == '{"id": 32, "name": "Release Notes"}'


def test_remoto_nao_e_alterado_pela_montagem():
    remote_resources = json.loads(json.dumps(REMOTO_COM_CONTENT))
    _montar(_declarado("Rate limit", {"quota": "1"}), remote_resources=remote_resources)
    assert remote_resources == REMOTO_COM_CONTENT


def test_reordenar_no_yaml_reordena_as_positions():
    flow = _montar(
        _declarado("Rate limit", {"quota": "1000", "interval": "SECOND"}),
        _declarado("Log", {"encryptContent": False}),
        _declarado("Payload size", {"maxSize": "2048"}),
        _declarado("Custom", custom_id=32),
    )
    por_posicao = sorted(flow, key=lambda i: i["position"])
    assert [i["type"] for i in por_posicao] == ["Rate limit", "Log", "Payload size", "Custom"]
    # mesmos numeros que o escopo ja ocupava
    assert sorted(i["position"] for i in flow) == [2, 4, 5, 7]


def test_inserir_no_meio_fica_no_meio():
    """Antes, o novo ia para o fim e 'roubava' a identidade do existente do mesmo tipo."""
    flow = _montar(
        _declarado("Log", {"encryptContent": False}),
        _declarado("Payload size", {"maxSize": "999"}),
        _declarado("Rate limit", {"quota": "1000", "interval": "SECOND"}),
        _declarado("Payload size", {"maxSize": "2048"}),
        _declarado("Custom", custom_id=32),
    )
    por_posicao = sorted(flow, key=lambda i: i["position"])
    assert [(i["type"], json.loads(i["content"]).get("maxSize")) for i in por_posicao] == [
        ("Log", None),
        ("Payload size", "999"),
        ("Rate limit", None),
        ("Payload size", "2048"),
        ("Custom", None),
    ]


def test_remover_do_meio_mantem_a_ordem_do_restante():
    flow = _montar(
        _declarado("Log", {"encryptContent": False}),
        _declarado("Payload size", {"maxSize": "2048"}),
        _declarado("Custom", custom_id=32),
    )
    por_posicao = sorted(flow, key=lambda i: i["position"])
    assert [i["type"] for i in por_posicao] == ["Log", "Payload size", "Custom"]
    assert all(i["id"] is not None for i in flow)


def test_request_e_response_sao_ordenados_cada_um_no_seu_ponto():
    remote_resources = REMOTO_COM_CONTENT + [
        {"id": 20, "type": "Log", "executionPoint": "SECOND", "position": 0,
         "content": '{"encryptContent": false}'},
    ]
    flow = _montar(
        _declarado("Payload size", {"maxSize": "2048"}),
        _declarado("Log", {"encryptContent": False}),
        _declarado("Log", {"encryptContent": True}, point="SECOND"),
        remote_resources=remote_resources,
    )
    response = [i for i in flow if i["executionPoint"] == "SECOND"]
    assert response[0]["position"] == 0
    assert json.loads(response[0]["content"]) == {"encryptContent": True}
    request = sorted(
        (i for i in flow if i["executionPoint"] == "FIRST"), key=lambda i: i["position"]
    )
    assert [i["type"] for i in request] == ["Payload size", "Log"]


def test_item_que_o_remoto_nao_tem_nasce_novo():
    flow = assemble_scope_flow(
        _resolvido("Payload size"),
        REMOTO_RESOLVIDO,
        generate_idtemp=prepare_idtemp_counter({"id": 100}),
    )
    assert flow[0]["id"] == flow[0]["idTemp"] == IDTEMP_FLOOR


def test_nao_governado_volta_intacto_no_fim():
    """V-22: o repositorio nao e autoridade sobre ele."""
    remote_resources = REMOTO_RESOLVIDO + [
        {"id": 9, "type": "Custom", "customInterceptorId": 178, "executionPoint": "THIRD", "position": 9}
    ]
    flow = assemble_scope_flow(
        _resolvido("Log"), remote_resources, generate_idtemp=prepare_idtemp_counter({})
    )
    assert flow[-1]["executionPoint"] == "THIRD"
    assert flow[-1] is remote_resources[-1]


def test_tombstone_remoto_fica_fora_do_pool_de_casamento():
    """Ele tem a MESMA chave do item que suprime (V-27): reaproveita-lo
    publicaria um `status: REMOVED` no lugar do item vivo."""
    remote_resources = [
        {"id": 4, "type": "Log", "executionPoint": "FIRST", "position": 1,
         "status": "REMOVED", "parent": {"id": 2}}
    ]
    flow = assemble_scope_flow(
        _resolvido("Log"), remote_resources, generate_idtemp=prepare_idtemp_counter({})
    )
    assert len(flow) == 1
    assert flow[0]["id"] != 4 and flow[0].get("status") == "REFERENCE"


def test_itens_novos_de_escopos_diferentes_nao_colidem_em_idtemp():
    """O cenario exato do W-9, que custou um `Custom` sumido sob HTTP 200."""
    counter = prepare_idtemp_counter({"id": 10})
    root = assemble_scope_flow(
        ScopeFlow(own=[{"type": "Custom", "customInterceptorId": 32,
                                 "executionPoint": "FIRST"}]),
        [], generate_idtemp=counter,
    )
    resource = assemble_scope_flow(
        ScopeFlow(own=[{"type": "Custom", "customInterceptorId": 33,
                                 "executionPoint": "FIRST"}]),
        [], generate_idtemp=counter,
    )
    assert root[0]["idTemp"] != resource[0]["idTemp"]


def test_tipo_repetido_no_escopo_nao_e_deduplicado():
    """Regressao: fluxos reais REPETEM tipo.

    `/health-check` tem dois `Log` em FIRST, e a regua tambem. Casar por chave
    num `dict` perderia um deles no payload — perda silenciosa da mesma classe
    que a conferencia pos-publicacao existe para pegar. O ensaio seco da bateria
    detectou isso antes da primeira escrita: 6 enviados contra 7 presentes.
    """
    remote_resources = [
        {"id": 1, "type": "Log", "executionPoint": "FIRST", "position": 1, "content": "A"},
        {"id": 2, "type": "Rate limit", "executionPoint": "FIRST", "position": 2},
        {"id": 3, "type": "Log", "executionPoint": "FIRST", "position": 3, "content": "B"},
    ]
    resolvido = ScopeFlow(own=[
        {"type": "Log", "executionPoint": "FIRST", "content": "A"},
        {"type": "Rate limit", "executionPoint": "FIRST"},
        {"type": "Log", "executionPoint": "FIRST", "content": "B"},
    ])
    flow = assemble_scope_flow(
        resolvido, remote_resources, generate_idtemp=prepare_idtemp_counter({})
    )

    assert len(flow) == 3
    assert [i["id"] for i in flow] == [1, 2, 3]


def test_append_publica_so_o_declarado_e_executa_o_herdado_repetido():
    """Dois `Log` no pai e um item próprio: o escopo guarda um item e executa três."""
    flow = resolve_declared_flow(
        [{"type": "Payload size", "executionPoint": "FIRST"}],
        [{"type": "Log", "executionPoint": "FIRST"},
         {"type": "Log", "executionPoint": "FIRST"}],
        inherit=True,
    )
    published = assemble_scope_flow(
        flow, [], generate_idtemp=prepare_idtemp_counter({"id": 50})
    )
    assert [i["type"] for i in published] == ["Payload size"]
    assert [i["type"] for i in flow.effective] == ["Log", "Log", "Payload size"]


# --- herdado marcado como removido ------------------------------------------


HERDADO_NO_WIRE = [
    {"id": 10, "type": "Log", "executionPoint": "FIRST", "position": 0,
     "content": '{"acceptedTerms": true}', "parentType": "REVISION"},
    {"id": 11, "type": "Custom", "customInterceptorId": 178, "executionPoint": "FIRST",
     "position": 1, "content": '{"id": 178}', "parentType": "REVISION"},
    {"id": 12, "type": "Log", "executionPoint": "SECOND", "position": 2,
     "content": '{"acceptedTerms": true}', "parentType": "REVISION"},
]


def _quebra(*tipos):
    return ScopeFlow(
        own=[{"type": t, "executionPoint": "FIRST"} for t in tipos], breaks_inheritance=True
    )


def _marcacoes(flow):
    return [i for i in flow if i.get("status") == "REMOVED"]


def test_identidade_e_id_ou_idtemp():
    assert identity({"id": 7, "idTemp": 7}) == 7
    assert identity({"id": None, "idTemp": 40}) == 40
    assert identity({}) is None
    assert tombstone_target({"parent": {"id": None, "idTemp": 40}}) == 40
    assert tombstone_target({"parent": {"id": 10, "idTemp": 10}}) == 10
    assert tombstone_target({"parent": None}) is None


def test_fluxo_composto_soma_o_herdado_ao_proprio():
    own = [{"id": 20, "type": "Payload size", "executionPoint": "FIRST", "position": 3}]
    composed = composed_flow(own, HERDADO_NO_WIRE)
    assert [i["id"] for i in composed] == [10, 11, 12, 20]


def test_fluxo_composto_tira_o_herdado_marcado_como_removido():
    own = [
        {"id": 20, "type": "Payload size", "executionPoint": "FIRST", "position": 3},
        {"id": 21, "type": "Log", "executionPoint": "FIRST", "position": 0,
         "status": "REMOVED", "parent": {"id": 10}},
    ]
    composed = composed_flow(own, HERDADO_NO_WIRE)
    assert [i["id"] for i in composed] == [11, 12, 20]


def test_fluxo_composto_reconhece_marcacao_por_idtemp():
    """O item que entra no pai no mesmo payload ainda não tem `id`."""
    inherited = HERDADO_NO_WIRE + [
        {"id": None, "idTemp": 40, "type": "OAuth", "executionPoint": "FIRST", "position": 4}
    ]
    own = [{"id": None, "idTemp": 41, "type": "OAuth", "executionPoint": "FIRST",
                 "status": "REMOVED", "parent": {"id": None, "idTemp": 40}}]
    assert [i["type"] for i in composed_flow(own, inherited)] == ["Log", "Custom", "Log"]


def test_fluxo_composto_executa_os_proprios_pela_position_depois_do_herdado():
    """A ordem é por escopo: `position` 0 no próprio não passa à frente do herdado."""
    own = [
        {"id": 21, "type": "Rate limit", "executionPoint": "FIRST", "position": 5},
        {"id": 20, "type": "Payload size", "executionPoint": "FIRST", "position": 0},
    ]
    composed = composed_flow(own, HERDADO_NO_WIRE)
    assert [i["id"] for i in composed] == [10, 11, 12, 20, 21]


def test_fluxo_composto_ignora_o_nao_governado():
    own = [{"id": 30, "type": "Custom", "executionPoint": "THIRD", "position": 1}]
    assert composed_flow(own, HERDADO_NO_WIRE) == HERDADO_NO_WIRE


def test_quebrar_marca_cada_herdado_como_removido():
    flow = assemble_scope_flow(
        _quebra("Payload size"),
        [],
        generate_idtemp=prepare_idtemp_counter({"id": 50}),
        inherited=HERDADO_NO_WIRE,
    )
    vivos = [i for i in flow if i.get("status") != "REMOVED"]
    tombstones = _marcacoes(flow)

    assert [i["type"] for i in vivos] == ["Payload size"]
    assert [m["parent"]["id"] for m in tombstones] == [10, 11, 12]
    for tombstone, inherited in zip(tombstones, HERDADO_NO_WIRE):
        assert tombstone["id"] == tombstone["idTemp"] >= IDTEMP_FLOOR
        assert tombstone["type"] == inherited["type"]
        assert tombstone["executionPoint"] == inherited["executionPoint"]
        assert tombstone["position"] == inherited["position"]
        assert tombstone["content"] == inherited["content"]
        assert tombstone["customInterceptorId"] == inherited.get("customInterceptorId")
    assert len({i["idTemp"] for i in flow}) == len(flow)


def test_marcacao_que_o_escopo_ja_tem_e_reaproveitada():
    remote_resources = [
        {"id": 90, "type": "Log", "executionPoint": "FIRST", "position": 0,
         "status": "REMOVED", "parent": {"id": 10, "idTemp": 10}},
    ]
    flow = assemble_scope_flow(
        _quebra("Payload size"),
        remote_resources,
        generate_idtemp=prepare_idtemp_counter({"id": 50}),
        inherited=HERDADO_NO_WIRE,
    )
    por_pai = {m["parent"]["id"]: m for m in _marcacoes(flow)}
    assert por_pai[10]["id"] == 90
    assert por_pai[11]["id"] == por_pai[11]["idTemp"] >= IDTEMP_FLOOR


def test_marcacao_de_item_que_nao_e_mais_herdado_sai():
    remote_resources = [
        {"id": 91, "type": "XSS threat protection", "executionPoint": "FIRST",
         "position": 5, "status": "REMOVED", "parent": {"id": 99}},
    ]
    flow = assemble_scope_flow(
        _quebra("Payload size"),
        remote_resources,
        generate_idtemp=prepare_idtemp_counter({"id": 50}),
        inherited=HERDADO_NO_WIRE,
    )
    assert 99 not in {m["parent"]["id"] for m in _marcacoes(flow)}


def test_posicao_dos_proprios_nao_depende_do_herdado():
    """A `position` só ordena dentro do escopo (V-28): nada de pular o herdado."""
    flow = assemble_scope_flow(
        _quebra("Payload size", "Rate limit"),
        [],
        generate_idtemp=prepare_idtemp_counter({"id": 50}),
        inherited=HERDADO_NO_WIRE,
    )
    vivos = [i for i in flow if i.get("status") != "REMOVED"]
    assert [(i["type"], i["position"]) for i in vivos] == [
        ("Payload size", 1),
        ("Rate limit", 2),
    ]


def test_herdado_novo_e_marcado_pelo_idtemp():
    """O item que entra no pai neste payload ainda não tem `id` (V-28 §5)."""
    inherited = HERDADO_NO_WIRE + [
        {"id": None, "idTemp": 40, "type": "OAuth", "executionPoint": "FIRST", "position": 4}
    ]
    flow = assemble_scope_flow(
        _quebra("Payload size"),
        [],
        generate_idtemp=prepare_idtemp_counter({"id": 50}),
        inherited=inherited,
    )
    oauth = next(m for m in _marcacoes(flow) if m["type"] == "OAuth")
    assert oauth["parent"] == {"id": None, "idTemp": 40}
    assert oauth["idTemp"] not in (40, None)


def test_quebrar_sem_itens_manda_so_as_marcacoes():
    flow = assemble_scope_flow(
        ScopeFlow(breaks_inheritance=True),
        [],
        generate_idtemp=prepare_idtemp_counter({"id": 50}),
        inherited=HERDADO_NO_WIRE,
    )
    assert len(flow) == 3 and all(i["status"] == "REMOVED" for i in flow)


def test_quebrar_com_pai_vazio_manda_lista_vazia():
    flow = assemble_scope_flow(
        ScopeFlow(breaks_inheritance=True), [], generate_idtemp=prepare_idtemp_counter({}), inherited=[]
    )
    assert flow == []


def test_quem_nao_substitui_nao_marca_o_herdado():
    flow = assemble_scope_flow(
        _resolvido("Payload size"),
        [],
        generate_idtemp=prepare_idtemp_counter({"id": 50}),
        inherited=HERDADO_NO_WIRE,
    )
    assert _marcacoes(flow) == []


def test_content_de_item_novo_vai_como_string_json():
    """Regressão: o wire carrega `content` como STRING JSON, não como objeto.

    Um `Log` real chega como '{"acceptedTerms": true, ...}'. Enviar o dict do
    YAML cru faz o Manager recusar com **HTTP 400** — observado nos cenários
    T07, T08 e T11 da bateria contra a API 417.
    """
    import json as _json

    item = build_new_item(
        kind="Payload size", execution_point="FIRST", idtemp=1, position=1,
        content={"maxSize": 2048},
    )
    assert isinstance(item["content"], str)
    assert _json.loads(item["content"]) == {"maxSize": 2048}


def test_content_ja_em_string_nao_e_reserializado():
    item = build_new_item(
        kind="Log", execution_point="FIRST", idtemp=1, position=1,
        content='{"acceptedTerms": true}',
    )
    assert item["content"] == '{"acceptedTerms": true}'


def test_content_nulo_continua_nulo():
    item = build_new_item(kind="X", execution_point="FIRST", idtemp=1, position=1)
    assert item["content"] is None
