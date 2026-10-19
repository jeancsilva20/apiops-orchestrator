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
    def __init__(self, dados, operacoes=()):
        self.dados, self.operacoes = dados, list(operacoes)
        self.slug, self.caminho = "r", "resources/r/resource.yaml"


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
    assert _tipos(montado.esperado["R/GET /x"]) == ["Payload size"]
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
