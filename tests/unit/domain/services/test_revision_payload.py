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
