"""Montagem do payload: o fluxo resolvido no repositório (V-27).

A V-27 tirou a resolução da herança da plataforma. O que estes testes travam é
que o payload passou a ser consequência do **repositório inteiro** — do
`all.yaml` até o arquivo da operação — e não do que a plataforma guardava.
"""

import json

from apiops_orchestrator.domain.services import revision_payload
from apiops_orchestrator.domain.services.revision_payload import _avisos_do_escopo
from apiops_orchestrator.domain.services.interceptor_flow import (
    resolver_fluxo_declarado,
)


def _remoto_com(*tipos):
    return {
        "interceptors": [
            {"id": i, "type": t, "executionPoint": "FIRST", "position": i}
            for i, t in enumerate(tipos, start=1)
        ]
    }


class _Op:
    def __init__(self, metodo, dados, arquivo="op.yaml"):
        self.metodo, self.dados, self.arquivo = metodo, dados, arquivo
        self.caminho = f"resources/r/{arquivo}"


class _Rec:
    def __init__(self, dados, operacoes=(), slug="r"):
        self.dados, self.operacoes = dados, list(operacoes)
        self.slug, self.caminho = slug, f"resources/{slug}/resource.yaml"


def _montar(raiz, recursos=(), draft=None):
    return revision_payload.montar(
        draft=draft if draft is not None else {"id": 1, "interceptors": [], "resources": [], "api": {}},
        basic_info={"spec": {}},
        raiz=raiz,
        recursos=list(recursos),
    )


def _tipos(itens):
    return [i["type"] for i in itens]


# --- o caso que motivou a V-27 ---------------------------------------------


def test_inherit_true_com_item_envia_o_herdado_mais_o_declarado():
    """O defeito do T11: o append publicava só o item novo e apagava a herança.

    A rota tinha 0 itens próprios na plataforma — ou seja, herdava os 2 da raiz.
    Declarar um `Payload size` com `inherit: true` mandava uma lista de 1, e pela
    W-4 essa lista passa a ser o fluxo INTEIRO da rota: os 2 herdados somem.
    """
    raiz = {
        "interceptors_request": [
            {"type": "Log", "content": {"acceptedTerms": True}},
            {"type": "Rate limit", "content": {"quota": 10}},
        ]
    }
    op = _Op("POST", {
        "path": "/x",
        "inherit": True,
        "interceptors_request": [{"type": "Payload size", "content": {"maxSize": 1}}],
    })
    montado = _montar(raiz, [_Rec({"name": "R"}, [op])])

    publicados = montado.corpo["resources"][0]["operations"][0]["interceptors"]
    assert _tipos(publicados) == ["Log", "Rate limit", "Payload size"]


def test_restaurar_heranca_e_acrescentar_item_na_mesma_declaracao():
    """O pedido do usuário: `inherit: true` + item sobre um escopo que tinha
    lista própria divergente. O que vale é o pai SEGUNDO O REPOSITÓRIO."""
    raiz = {"interceptors_request": [{"type": "Log"}, {"type": "Rate limit"}]}
    op = _Op("POST", {
        "path": "/x",
        "inherit": True,
        "interceptors_request": [{"type": "Payload size"}],
    })
    draft = {
        "id": 1,
        "api": {},
        "interceptors": [],
        "resources": [{
            "name": "R",
            "interceptors": [],
            "operations": [{
                "method": "POST", "path": "/x",
                # A plataforma guardava uma lista própria obsoleta.
                "interceptors": [
                    {"id": 9, "type": "XSS threat protection",
                     "executionPoint": "FIRST", "position": 1}
                ],
            }],
        }],
    }
    montado = _montar(raiz, [_Rec({"name": "R"}, [op])], draft=draft)

    publicados = montado.corpo["resources"][0]["operations"][0]["interceptors"]
    assert _tipos(publicados) == ["Log", "Rate limit", "Payload size"]
    assert "XSS threat protection" not in _tipos(publicados)


def test_a_resolucao_desce_tres_niveis():
    """raiz → recurso → operação, cada um somando ao efetivo do anterior."""
    raiz = {"interceptors_request": [{"type": "Log"}]}
    op = _Op("GET", {"path": "/x", "inherit": True,
                     "interceptors_request": [{"type": "Payload size"}]})
    recurso = _Rec(
        {"name": "R", "inherit": True, "interceptors_request": [{"type": "Rate limit"}]},
        [op],
    )
    montado = _montar(raiz, [recurso])

    assert _tipos(montado.corpo["resources"][0]["interceptors"]) == ["Log", "Rate limit"]
    assert _tipos(montado.corpo["resources"][0]["operations"][0]["interceptors"]) == [
        "Log", "Rate limit", "Payload size"
    ]


def test_heranca_pura_vai_vazia_no_wire():
    """A codificação compacta: `[]` mantém a propagação viva (V-27 §2)."""
    raiz = {"interceptors_request": [{"type": "Log"}]}
    op = _Op("GET", {"path": "/x", "inherit": True})
    montado = _montar(raiz, [_Rec({"name": "R", "inherit": True}, [op])])

    assert montado.corpo["resources"][0]["interceptors"] == []
    assert montado.corpo["resources"][0]["operations"][0]["interceptors"] == []


def test_inherit_false_publica_so_o_declarado():
    raiz = {"interceptors_request": [{"type": "Log"}, {"type": "Rate limit"}]}
    op = _Op("GET", {"path": "/x", "inherit": False,
                     "interceptors_request": [{"type": "Payload size"}]})
    montado = _montar(raiz, [_Rec({"name": "R"}, [op])])

    publicados = montado.corpo["resources"][0]["operations"][0]["interceptors"]
    assert _tipos(publicados) == ["Payload size"]


_RAIZ_NO_MANAGER = [
    {"id": 10, "type": "Log", "executionPoint": "FIRST", "position": 0,
     "status": "REFERENCE", "parentType": "REVISION"},
    {"id": 11, "type": "Rate limit", "executionPoint": "FIRST", "position": 1,
     "status": "REFERENCE", "parentType": "REVISION"},
]
_RAIZ_NO_REPO = {"interceptors_request": [{"type": "Log"}, {"type": "Rate limit"}]}


def _draft_com(raiz, recursos=()):
    return {"id": 1, "api": {}, "interceptors": list(raiz), "resources": list(recursos)}


def _marcados(itens):
    return sorted(i["parent"]["id"] for i in itens if i.get("status") == "REMOVED")


def _vivos(itens):
    return [i["type"] for i in itens if i.get("status") != "REMOVED"]


def test_inherit_false_marca_o_herdado_da_raiz_como_removido():
    op = _Op("GET", {"path": "/x", "inherit": False,
                     "interceptors_request": [{"type": "Payload size"}]})
    montado = _montar(
        _RAIZ_NO_REPO, [_Rec({"name": "R", "inherit": True}, [op])],
        draft=_draft_com(_RAIZ_NO_MANAGER),
    )

    publicados = montado.corpo["resources"][0]["operations"][0]["interceptors"]
    assert _vivos(publicados) == ["Payload size"]
    assert _marcados(publicados) == [10, 11]
    assert montado.avisos == []


def test_rota_abaixo_de_recurso_que_substitui_marca_so_o_do_recurso():
    """O recurso já tirou a raiz; a rota herda só o que o recurso executa."""
    recurso_remoto = {
        "name": "R",
        "interceptors": [{"id": 20, "type": "XSS threat protection",
                          "executionPoint": "FIRST", "position": 2,
                          "status": "REFERENCE", "parentType": "REVISION"}],
        "operations": [{"id": 5, "method": "GET", "path": "/x", "interceptors": []}],
    }
    op = _Op("GET", {"path": "/x", "inherit": False,
                     "interceptors_request": [{"type": "Payload size"}]})
    recurso = _Rec(
        {"name": "R", "inherit": False,
         "interceptors_request": [{"type": "XSS threat protection"}]},
        [op],
    )
    montado = _montar(
        _RAIZ_NO_REPO, [recurso], draft=_draft_com(_RAIZ_NO_MANAGER, [recurso_remoto])
    )

    bloco = montado.corpo["resources"][0]
    assert _marcados(bloco["interceptors"]) == [10, 11]
    assert _marcados(bloco["operations"][0]["interceptors"]) == [20]


def test_inherit_false_avisa_o_herdado_que_nasce_na_mesma_publicacao():
    op = _Op("GET", {"path": "/x", "inherit": False,
                     "interceptors_request": [{"type": "Payload size"}]})
    montado = _montar(
        {"interceptors_request": [{"type": "Log"}, {"type": "OAuth"}]},
        [_Rec({"name": "R", "inherit": True}, [op])],
        draft=_draft_com(_RAIZ_NO_MANAGER[:1]),
    )

    publicados = montado.corpo["resources"][0]["operations"][0]["interceptors"]
    assert _marcados(publicados) == [10]
    assert any(
        "GET /x" in a and "OAuth" in a and "ainda não podem ser removidos" in a
        for a in montado.avisos
    )


def test_o_nao_governado_volta_intacto_mesmo_na_heranca_pura():
    """V-22: `[]` na lista governada não pode levar o preservado junto."""
    preservado = {"id": 7, "type": "Custom", "executionPoint": "THIRD", "position": 9}
    draft = {
        "id": 1, "api": {}, "interceptors": [], "resources": [
            {"name": "R", "interceptors": [preservado], "operations": []}
        ],
    }
    montado = _montar({}, [_Rec({"name": "R", "inherit": True})], draft=draft)
    assert montado.corpo["resources"][0]["interceptors"] == [preservado]


# --- avisos (V-27 §5 e §8) --------------------------------------------------


def test_avisa_que_a_lista_propria_sera_removida():
    """O escopo volta a herdar — e isso APAGA o que ele tinha. Não pode ser calado."""
    fluxo = resolver_fluxo_declarado([], [{"type": "Log"}], inherit=True)
    avisos = _avisos_do_escopo(fluxo, _remoto_com("Rate limit"), "POST /x")

    assert len(avisos) == 1
    assert "esses interceptors saem" in avisos[0]
    assert "Rate limit" in avisos[0]


def test_nao_avisa_quando_o_escopo_ja_herdava():
    fluxo = resolver_fluxo_declarado([], [{"type": "Log"}], inherit=True)
    assert _avisos_do_escopo(fluxo, {"interceptors": []}, "POST /x") == []
    assert _avisos_do_escopo(fluxo, None, "POST /x") == []


def test_nao_avisa_por_item_nao_governado():
    """V-22: o preservado não é fluxo que o repositório governe."""
    fluxo = resolver_fluxo_declarado([], [{"type": "Log"}], inherit=True)
    remoto = {"interceptors": [{"id": 1, "type": "Custom", "executionPoint": "THIRD"}]}
    assert _avisos_do_escopo(fluxo, remoto, "POST /x") == []


def test_tombstone_sozinho_nao_conta_como_lista_propria():
    fluxo = resolver_fluxo_declarado([], [{"type": "Log"}], inherit=True)
    remoto = {"interceptors": [
        {"id": 1, "type": "XSS threat protection", "executionPoint": "FIRST",
         "status": "REMOVED", "parent": {"id": 9}}
    ]}
    assert _avisos_do_escopo(fluxo, remoto, "POST /x") == []


def test_inherit_false_sem_itens_avisa_a_contradicao():
    """T06: a plataforma não representa escopo sem fluxo."""
    fluxo = resolver_fluxo_declarado([], [{"type": "Log"}], inherit=False)
    avisos = _avisos_do_escopo(fluxo, None, "POST /x")

    assert len(avisos) == 1
    assert "não lista nenhum interceptor" in avisos[0]
    assert "continuar herdando" in avisos[0]


def test_raiz_sem_interceptors_com_fluxo_remoto_avisa_remocao():
    """V-27 §8 (E-1): a raiz não herda de ninguém — `[]` ali é remoção."""
    fluxo = resolver_fluxo_declarado([], raiz=True)
    avisos = _avisos_do_escopo(fluxo, _remoto_com("Log", "Rate limit"), "raiz", raiz=True)

    assert len(avisos) == 1
    assert "esses interceptors saem" in avisos[0]
    assert "a API tem 2 hoje no Manager" in avisos[0]


def test_raiz_que_declara_fluxo_nao_avisa():
    fluxo = resolver_fluxo_declarado([{"type": "Log"}], raiz=True)
    assert _avisos_do_escopo(fluxo, _remoto_com("Log"), "raiz", raiz=True) == []


def test_o_aviso_da_raiz_chega_ao_payload_montado():
    draft = {"id": 1, "api": {}, "resources": [], **_remoto_com("Log")}
    montado = _montar({}, [], draft=draft)
    assert any("esses interceptors saem" in a for a in montado.avisos)


# --- tombstone (V-27 §8, E-2) ----------------------------------------------


def test_tombstone_remoto_nao_e_reaproveitado_como_item_vivo():
    """Ele tem a MESMA chave do item que suprime: casá-lo publicaria o
    `status: REMOVED` no lugar do item que o repositório declara."""
    draft = {
        "id": 1, "api": {}, "interceptors": [], "resources": [{
            "name": "R",
            "interceptors": [
                {"id": 9, "type": "Log", "executionPoint": "FIRST", "position": 1,
                 "status": "REMOVED", "parent": {"id": 4}}
            ],
            "operations": [],
        }],
    }
    recurso = _Rec({"name": "R", "inherit": False,
                    "interceptors_request": [{"type": "Log"}]})
    publicados = _montar({}, [recurso], draft=draft).corpo["resources"][0]["interceptors"]

    assert len(publicados) == 1
    assert publicados[0].get("status") != "REMOVED"
    assert publicados[0]["id"] is None  # nasceu novo, não reusou o tombstone


def test_conferir_reporta_tombstone_remanescente():
    enviado = {"interceptors": [], "resources": []}
    publicado = {
        "interceptors": [
            {"id": 1, "type": "XSS threat protection", "executionPoint": "FIRST",
             "status": "REMOVED", "parent": {"id": 9}}
        ],
        "resources": [],
    }
    divergencias = revision_payload.conferir(enviado, publicado)
    assert any("marcação(ões) de interceptor removido" in d for d in divergencias)


_MARCACAO = {"id": None, "idTemp": 30, "type": "Log", "executionPoint": "FIRST",
             "position": 0, "status": "REMOVED", "parent": {"id": 10, "idTemp": 10}}


def _com_rota(itens):
    return {
        "interceptors": [],
        "resources": [{"name": "R", "interceptors": [], "operations": [
            {"method": "GET", "path": "/x", "interceptors": itens}
        ]}],
    }


def test_conferir_aceita_a_marcacao_enviada_e_gravada():
    gravada = {**_MARCACAO, "id": 31}
    assert revision_payload.conferir(_com_rota([_MARCACAO]), _com_rota([gravada])) == []


def test_conferir_reporta_marcacao_enviada_e_nao_gravada():
    divergencias = revision_payload.conferir(_com_rota([_MARCACAO]), _com_rota([]))
    assert any(
        d.startswith("GET /x:") and "que o Manager não gravou" in d for d in divergencias
    )


def test_conferir_nao_conta_tombstone_como_fluxo():
    """8 itens mais 1 supressão não são 9 — a contagem olha só os vivos."""
    vivos = [
        {"id": i, "type": "Log", "executionPoint": "FIRST", "position": i}
        for i in range(1, 9)
    ]
    enviado = {"interceptors": vivos, "resources": []}
    publicado = {"interceptors": vivos, "resources": []}
    assert revision_payload.conferir(enviado, publicado) == []


# --- content como string JSON ----------------------------------------------


def test_content_de_item_novo_sai_serializado():
    """O wire recusa dict com HTTP 400."""
    op = _Op("GET", {
        "path": "/x",
        "inherit": False,
        "interceptors_request": [{"type": "Payload size", "content": {"maxSize": 2048}}],
    }, arquivo="get_x.yaml")
    montado = _montar({}, [_Rec({"name": "R"}, [op])])

    item = montado.corpo["resources"][0]["operations"][0]["interceptors"][0]
    assert isinstance(item["content"], str)
    assert json.loads(item["content"]) == {"maxSize": 2048}


def test_custom_novo_recebe_o_content_do_catalogo():
    recurso = _Rec({
        "name": "R",
        "inherit": False,
        "interceptors_request": [{"type": "Custom", "id": 32}],
    })
    montado = revision_payload.montar(
        draft={"id": 1, "interceptors": [], "resources": [], "api": {}},
        basic_info={"spec": {}},
        raiz={},
        recursos=[recurso],
        resolver_custom=lambda c: {"id": c, "name": "Release Notes", "script": "x"},
    )
    item = montado.corpo["resources"][0]["interceptors"][0]
    assert item["customInterceptorId"] == 32
    assert json.loads(item["content"])["name"] == "Release Notes"


def test_custom_herdado_da_raiz_tambem_resolve_o_content():
    """O herdado atravessa a hierarquia como item declarado — e um `Custom`
    materializado num filho precisa do `{id, name, script}` igualmente."""
    op = _Op("GET", {"path": "/x", "inherit": True,
                     "interceptors_request": [{"type": "Log"}]})
    montado = revision_payload.montar(
        draft={"id": 1, "interceptors": [], "resources": [], "api": {}},
        basic_info={"spec": {}},
        raiz={"interceptors_request": [{"type": "Custom", "id": 33}]},
        recursos=[_Rec({"name": "R"}, [op])],
        resolver_custom=lambda c: {"id": c, "name": "CyberArk", "script": "y"},
    )
    publicados = montado.corpo["resources"][0]["operations"][0]["interceptors"]
    assert [i["type"] for i in publicados] == ["Custom", "Log"]
    assert json.loads(publicados[0]["content"])["name"] == "CyberArk"


# --- Conferência do `api` aninhado (W-8) --------------------------------------

_TAGS_ENVIADAS = [
    {"attributeName": "teste giroto", "tags": ["teste giroto"]},
    {"attributeName": "My new", "tags": ["Tag1"]},
]


def _com_api(**api):
    return {"api": dict(api), "resources": [], "interceptors": []}


def test_conferir_acusa_apitags_apagadas_pela_plataforma():
    """A tag inexistente foi aceita com 200 e o Manager zerou as apiTags."""
    enviado = _com_api(apiTags=_TAGS_ENVIADAS)
    publicado = _com_api(apiTags=[])

    divergencias = revision_payload.conferir(enviado, publicado)

    assert any("`My new` foi enviado em `apiTags`" in d for d in divergencias)
    assert any("`teste giroto` foi enviado em `apiTags`" in d for d in divergencias)


def test_conferir_acusa_tags_diferentes_no_mesmo_atributo():
    enviado = _com_api(apiTags=[{"attributeName": "My new", "tags": ["Tag1"]}])
    publicado = _com_api(apiTags=[{"attributeName": "My new", "tags": ["Tag2"]}])

    divergencias = revision_payload.conferir(enviado, publicado)

    assert divergencias == [
        "o atributo `My new` foi enviado com as tags ['Tag1'] e gravado com ['Tag2']"
    ]


def test_conferir_acusa_atributo_que_sobrou_no_manager():
    enviado = _com_api(apiTags=[])
    publicado = _com_api(apiTags=[{"attributeName": "Velho", "tags": ["x"]}])

    assert revision_payload.conferir(enviado, publicado) == [
        "o atributo `Velho` está nas `apiTags` do Manager mas não foi enviado"
    ]


def test_conferir_ignora_a_ordem_das_apitags_e_das_tags():
    enviado = _com_api(apiTags=[
        {"attributeName": "A", "tags": ["1", "2"]},
        {"attributeName": "B", "tags": ["3"]},
    ])
    publicado = _com_api(apiTags=[
        {"attributeName": "B", "tags": ["3"]},
        {"attributeName": "A", "tags": ["2", "1"]},
    ])

    assert revision_payload.conferir(enviado, publicado) == []


def test_conferir_sem_apitags_no_envio_nao_confere_tags():
    """Ausente preserva: o que não foi enviado não é veredito."""
    enviado = _com_api(name="X")
    publicado = _com_api(name="X", apiTags=[{"attributeName": "A", "tags": ["1"]}])

    assert revision_payload.conferir(enviado, publicado) == []


def test_conferir_acusa_name_e_description_divergentes():
    enviado = _com_api(name="Novo", description="depois")
    publicado = _com_api(name="Antigo", description="depois")

    assert revision_payload.conferir(enviado, publicado) == [
        "o campo `name` foi enviado como 'Novo' e gravado como 'Antigo'"
    ]


# --- o repositório prevalece: content e ordem (regressão do S10) -------------

DRAFT_COM_CONTENT = {
    "id": 1,
    "api": {},
    "resources": [],
    "interceptors": [
        {"id": 10, "idTemp": 10, "type": "Log", "executionPoint": "FIRST", "position": 2,
         "status": "REFERENCE", "content": '{"encryptContent": false}'},
        {"id": 11, "idTemp": 11, "type": "Rate limit", "executionPoint": "FIRST", "position": 4,
         "status": "REFERENCE", "content": '{"quota": "1000"}'},
    ],
}

RAIZ_ALTERADA = {
    "interceptors_request": [
        {"type": "Log", "content": {"encryptContent": False}},
        {"type": "Rate limit", "content": {"quota": "500"}},
    ]
}


def test_payload_leva_o_content_alterado_no_repositorio():
    montado = _montar(RAIZ_ALTERADA, draft=DRAFT_COM_CONTENT)
    rate = next(i for i in montado.corpo["interceptors"] if i["type"] == "Rate limit")
    assert json.loads(rate["content"]) == {"quota": "500"}
    assert rate["id"] == 11


def test_esperado_carrega_o_fluxo_declarado_por_escopo():
    op = _Op("GET", {"path": "/x", "inherit": False,
                     "interceptors_request": [{"type": "Payload size", "content": {"maxSize": 1}}]})
    montado = _montar(RAIZ_ALTERADA, [_Rec({"name": "R"}, [op])], draft=DRAFT_COM_CONTENT)

    assert _tipos(montado.esperado["raiz"]) == ["Log", "Rate limit"]
    assert _tipos(montado.esperado["GET /x"]) == ["Payload size"]
    # herança pura vai como `[]`: não há lista própria para conferir
    assert "resource R" not in montado.esperado


def _publicado_com(*itens):
    return {"interceptors": list(itens), "resources": [], "api": {}}


def test_conferir_acusa_content_que_nao_foi_gravado_como_declarado():
    """O caso do S10: o 200 e a comparação com o payload davam verde."""
    montado = _montar(RAIZ_ALTERADA, draft=DRAFT_COM_CONTENT)
    publicado = _publicado_com(
        {"id": 10, "type": "Log", "executionPoint": "FIRST", "position": 2,
         "content": '{"encryptContent": false}'},
        {"id": 11, "type": "Rate limit", "executionPoint": "FIRST", "position": 4,
         "content": '{"quota": "1000"}'},
    )
    divergencias = revision_payload.conferir(
        montado.corpo, publicado, esperado=montado.esperado
    )
    assert any("Rate limit" in d and "`quota` declarado" in d for d in divergencias)


def test_conferir_acusa_ordem_diferente_da_declarada():
    montado = _montar(RAIZ_ALTERADA, draft=DRAFT_COM_CONTENT)
    publicado = _publicado_com(
        {"id": 11, "type": "Rate limit", "executionPoint": "FIRST", "position": 2,
         "content": '{"quota": "500"}'},
        {"id": 10, "type": "Log", "executionPoint": "FIRST", "position": 4,
         "content": '{"encryptContent": false}'},
    )
    divergencias = revision_payload.conferir(
        montado.corpo, publicado, esperado=montado.esperado
    )
    assert any("declarado como [Log, Rate limit]" in d for d in divergencias)


def test_conferir_normaliza_escalar_e_ignora_content_de_custom():
    """`"500"` e `500` são o mesmo valor (V-11 §4); Custom casa só pelo id."""
    raiz = {"interceptors_request": [
        {"type": "Rate limit", "content": {"quota": 500}},
        {"type": "Custom", "id": 32},
    ]}
    montado = _montar(raiz)
    publicado = _publicado_com(
        {"id": 1, "type": "Rate limit", "executionPoint": "FIRST", "position": 1,
         "content": '{"quota": "500"}'},
        {"id": 2, "type": "Custom", "customInterceptorId": 32, "executionPoint": "FIRST",
         "position": 2, "content": '{"id": 32, "script": "qualquer"}'},
    )
    assert revision_payload.conferir(montado.corpo, publicado, esperado=montado.esperado) == []


# --- avisos de remoção: o PUT grava a revisão inteira -------------------------

DRAFT_COM_ROTAS = {
    "id": 1,
    "api": {},
    "interceptors": [],
    "resources": [
        {"name": "Letras", "operations": [
            {"id": 1, "method": "POST", "path": "/letras"},
            {"id": 2, "method": "DELETE", "path": "/letras/{id}"},
        ]},
        {"name": "Saude", "operations": [{"id": 3, "method": "GET", "path": "/health"}]},
    ],
}


def test_rota_que_saiu_do_repositorio_e_avisada():
    letras = _Rec({"name": "Letras"}, [_Op("POST", {"path": "/letras"})])
    saude = _Rec({"name": "Saude"}, [_Op("GET", {"path": "/health"})])
    avisos = _montar({}, [letras, saude], draft=DRAFT_COM_ROTAS).avisos

    rotas = [a for a in avisos if a.startswith("As rotas abaixo")]
    assert rotas == [
        "As rotas abaixo existem no Manager mas não estão no repositório. Ao "
        "publicar, elas serão apagadas do Manager:\n"
        "  - DELETE /letras/{id} (recurso Letras)\n\n"
        "Se não era essa a intenção, adicione-as ao repositório antes de publicar."
    ]


def test_recurso_que_saiu_e_avisado_sem_repetir_as_rotas_dele():
    letras = _Rec({"name": "Letras"}, [
        _Op("POST", {"path": "/letras"}),
        _Op("DELETE", {"path": "/letras/{id}"}),
    ])
    avisos = _montar({}, [letras], draft=DRAFT_COM_ROTAS).avisos

    assert avisos == [
        "Os recursos abaixo existem no Manager mas não estão no repositório. Ao "
        "publicar, eles serão apagados do Manager:\n"
        "  - Saude\n\n"
        "Se não era essa a intenção, adicione-os ao repositório antes de publicar."
    ]


def test_nada_removido_nada_avisado():
    letras = _Rec({"name": "Letras"}, [
        _Op("POST", {"path": "/letras"}),
        _Op("DELETE", {"path": "/letras/{id}"}),
    ])
    saude = _Rec({"name": "Saude"}, [_Op("GET", {"path": "/health"})])
    assert _montar({}, [letras, saude], draft=DRAFT_COM_ROTAS).avisos == []


# --- identidade do recurso pelas rotas (V-12a) -------------------------------
#
# O Manager aceita recursos homônimos e o repositório não versiona `id`: o elo
# entre pasta e recurso remoto são as rotas. Ligar pelo nome fazia dois
# homônimos caírem no mesmo remoto — aviso falso, `id` repetido e um recurso
# apagado sem aviso.

DRAFT_TAREFAS = {
    "id": 1, "api": {}, "interceptors": [],
    "resources": [{"id": 50, "name": "Tarefas", "operations": [
        {"id": 501, "method": "GET", "path": "/tarefas"},
        {"id": 502, "method": "GET", "path": "/tarefas/{id}"},
    ]}],
}

DRAFT_LETRAS_HOMONIMOS = {
    "id": 1, "api": {}, "interceptors": [],
    "resources": [
        {"id": 101, "name": "Letras", "operations": [
            {"id": 1, "method": "GET", "path": "/letras/{id}"},
        ]},
        {"id": 102, "name": "Letras", "operations": [
            {"id": 2, "method": "POST", "path": "/tarefas/{id}/letras"},
        ]},
    ],
}


def _letras_homonimos():
    return [
        _Rec({"name": "Letras"}, [_Op("GET", {"path": "/letras/{id}"})],
             slug="letras-letras-id"),
        _Rec({"name": "Letras"}, [_Op("POST", {"path": "/tarefas/{id}/letras"})],
             slug="letras-tarefas-id-letras"),
    ]


def _aviso_de_homonimos(pastas, nome):
    return (
        f"As pastas {pastas} declaram recursos com o mesmo nome, \"{nome}\". O "
        "Manager aceita, mas quem olha a API vê recursos iguais e não sabe qual é "
        "qual.\n"
        "Se são o mesmo recurso, junte as rotas em uma pasta só. Se não são, dê a "
        "cada um um nome diferente no `resource.yaml`."
    )


def test_rota_movida_para_pasta_homonima_nao_e_avisada_como_apagada():
    """O caso da 417 rev3: a pasta copiada manteve o `name`."""
    recursos = [
        _Rec({"name": "Tarefas"}, [_Op("GET", {"path": "/tarefas/{id}"})], slug="tarefas"),
        _Rec({"name": "Tarefas"}, [_Op("GET", {"path": "/tarefas"})], slug="tarefas 2"),
    ]
    montado = _montar({}, recursos, draft=DRAFT_TAREFAS)

    assert montado.avisos == [
        _aviso_de_homonimos("`tarefas` e `tarefas 2`", "Tarefas"),
        "As rotas abaixo estão no repositório em um recurso diferente do que têm "
        "hoje no Manager. Ao publicar, elas saem do recurso de origem e passam "
        "para o de destino:\n"
        "  - GET /tarefas: sai do recurso Tarefas e vai para o recurso Tarefas "
        "(pasta `tarefas 2`), que será criado\n\n"
        "Se não era essa a intenção, devolva-as à pasta do recurso de origem.",
    ]
    fica, nova = montado.corpo["resources"]
    # empate (1 rota cada, mesmo nome): fica com o `id` a primeira pasta
    assert fica["id"] == 50
    assert [o["id"] for o in fica["operations"]] == [502]
    assert "id" not in nova
    assert "id" not in nova["operations"][0]  # W-6: operação que muda de recurso vai nova


def test_homonimos_vindos_do_manager_voltam_intactos():
    """A 409 rev1: puxar e publicar de volta sem mudança não altera nada."""
    montado = _montar({}, _letras_homonimos(), draft=DRAFT_LETRAS_HOMONIMOS)

    assert montado.avisos == [
        _aviso_de_homonimos("`letras-letras-id` e `letras-tarefas-id-letras`", "Letras")
    ]
    assert [r["id"] for r in montado.corpo["resources"]] == [101, 102]
    assert [r["operations"][0]["id"] for r in montado.corpo["resources"]] == [1, 2]


def test_ligacao_independe_da_ordem_dos_recursos_no_manager():
    draft = dict(DRAFT_LETRAS_HOMONIMOS,
                 resources=list(reversed(DRAFT_LETRAS_HOMONIMOS["resources"])))
    montado = _montar({}, _letras_homonimos(), draft=draft)
    assert [r["id"] for r in montado.corpo["resources"]] == [101, 102]


def test_homonimo_que_sai_e_avisado_mesmo_com_o_nome_ainda_presente():
    """Antes, o aviso comparava nomes: `Letras` continuava lá e nada era dito."""
    avisos = _montar({}, _letras_homonimos()[:1], draft=DRAFT_LETRAS_HOMONIMOS).avisos

    assert avisos == [
        "Os recursos abaixo existem no Manager mas não estão no repositório. Ao "
        "publicar, eles serão apagados do Manager:\n"
        "  - Letras (rota POST /tarefas/{id}/letras)\n\n"
        "Se não era essa a intenção, adicione-os ao repositório antes de publicar."
    ]


def test_renomear_recurso_mantem_o_id():
    recurso = _Rec({"name": "Tarefas v2"}, [
        _Op("GET", {"path": "/tarefas"}),
        _Op("GET", {"path": "/tarefas/{id}"}),
    ])
    montado = _montar({}, [recurso], draft=DRAFT_TAREFAS)

    assert montado.avisos == []
    bloco = montado.corpo["resources"][0]
    assert (bloco["id"], bloco["name"]) == (50, "Tarefas v2")
    assert [o["id"] for o in bloco["operations"]] == [501, 502]


def test_juntar_dois_recursos_avisa_o_que_sai_e_o_que_muda_de_recurso():
    draft = {
        "id": 1, "api": {}, "interceptors": [],
        "resources": [
            {"id": 10, "name": "A", "operations": [{"id": 1, "method": "GET", "path": "/a"}]},
            {"id": 20, "name": "B", "operations": [{"id": 2, "method": "GET", "path": "/b"}]},
        ],
    }
    junto = _Rec({"name": "A"}, [_Op("GET", {"path": "/a"}), _Op("GET", {"path": "/b"})],
                 slug="a")
    montado = _montar({}, [junto], draft=draft)

    assert montado.avisos == [
        "Os recursos abaixo existem no Manager mas não estão no repositório. Ao "
        "publicar, eles serão apagados do Manager:\n"
        "  - B\n\n"
        "Se não era essa a intenção, adicione-os ao repositório antes de publicar.",
        "As rotas abaixo estão no repositório em um recurso diferente do que têm "
        "hoje no Manager. Ao publicar, elas saem do recurso de origem e passam "
        "para o de destino:\n"
        "  - GET /b: sai do recurso B e vai para o recurso A (pasta `a`)\n\n"
        "Se não era essa a intenção, devolva-as à pasta do recurso de origem.",
    ]
    bloco = montado.corpo["resources"][0]
    assert bloco["id"] == 10
    assert [o.get("id") for o in bloco["operations"]] == [1, None]


def test_sem_rota_em_comum_e_recurso_novo_mesmo_com_nome_igual():
    """Decisão: sem ligação pelo nome — sem rota em comum é outro recurso."""
    recurso = _Rec({"name": "Tarefas"}, [_Op("GET", {"path": "/outra"})])
    montado = _montar({}, [recurso], draft=DRAFT_TAREFAS)

    assert "id" not in montado.corpo["resources"][0]
    assert montado.avisos[0].startswith("Os recursos abaixo existem no Manager")
    assert "  - Tarefas\n" in montado.avisos[0]


def test_parear_desempata_por_quantidade_e_depois_pelo_nome():
    remotos = [("X", [("GET", "/a"), ("GET", "/b")])]
    # mais rotas em comum vence, mesmo com outro nome
    assert revision_payload.parear_por_rotas(
        [("X", [("GET", "/a")]), ("Y", [("GET", "/a"), ("GET", "/b")])], remotos
    ) == {1: 0}
    # empatado em rotas, vence o de mesmo nome
    assert revision_payload.parear_por_rotas(
        [("Y", [("GET", "/a")]), ("X", [("GET", "/b")])], remotos
    ) == {1: 0}


# --- conferência com homônimos ----------------------------------------------


def test_conferir_homonimos_publicados_como_enviados_nao_diverge():
    montado = _montar({}, _letras_homonimos(), draft=DRAFT_LETRAS_HOMONIMOS)
    publicado = json.loads(json.dumps(montado.corpo))
    publicado["resources"].reverse()  # a ordem do GET não é contrato

    assert revision_payload.conferir(montado.corpo, publicado, esperado=montado.esperado) == []


def test_conferir_acusa_rota_descartada_de_um_dos_homonimos():
    montado = _montar({}, _letras_homonimos(), draft=DRAFT_LETRAS_HOMONIMOS)
    publicado = json.loads(json.dumps(montado.corpo))
    publicado["resources"][1]["operations"] = []

    divergencias = revision_payload.conferir(montado.corpo, publicado)
    assert (
        "a operação POST /tarefas/{id}/letras, do recurso Letras (rota POST "
        "/tarefas/{id}/letras), foi enviada mas não está no Manager"
    ) in divergencias


def test_conferir_acusa_rota_que_o_manager_nao_moveu():
    """W-6: a mudança de recurso pode ser descartada com 200."""
    recursos = [
        _Rec({"name": "Tarefas"}, [_Op("GET", {"path": "/tarefas/{id}"})], slug="tarefas"),
        _Rec({"name": "Tarefas"}, [_Op("GET", {"path": "/tarefas"})], slug="tarefas 2"),
    ]
    montado = _montar({}, recursos, draft=DRAFT_TAREFAS)

    divergencias = revision_payload.conferir(montado.corpo, DRAFT_TAREFAS)
    assert (
        "o recurso Tarefas (rota GET /tarefas) foi enviado mas não está no Manager"
    ) in divergencias