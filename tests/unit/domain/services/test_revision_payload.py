"""Montagem do payload: o que cada escopo guarda, decidido pelo repositório (V-28).

O payload é consequência do **repositório inteiro** — do `all.yaml` até o arquivo
da operação: cada escopo leva os itens que declara e, quando quebra a herança,
uma marcação para cada item que o pai executa.
"""

import json

from apiops_orchestrator.domain.services import revision_payload
from apiops_orchestrator.domain.services.revision_payload import _scope_warnings
from apiops_orchestrator.domain.services.interceptor_flow import (
    resolve_declared_flow,
)


def _remoto_com(*tipos):
    return {
        "interceptors": [
            {"id": i, "type": t, "executionPoint": "FIRST", "position": i}
            for i, t in enumerate(tipos, start=1)
        ]
    }


class _Op:
    def __init__(self, method, data, file="op.yaml"):
        self.method, self.data, self.file = method, data, file
        self.file_path = f"resources/r/{file}"


class _Rec:
    def __init__(self, data, operations=(), slug="r"):
        self.data, self.operations = data, list(operations)
        self.slug, self.file_path = slug, f"resources/{slug}/resource.yaml"


def _montar(root, resources=(), draft=None):
    return revision_payload.assemble(
        draft=draft if draft is not None else {"id": 1, "interceptors": [], "resources": [], "api": {}},
        basic_info={"spec": {}},
        root=root,
        resources=list(resources),
    )


def _tipos(items):
    return [i["type"] for i in items]


# --- append: o escopo guarda só o que declara -------------------------------


def test_inherit_true_com_item_envia_so_o_declarado():
    """A plataforma soma o herdado sozinha; copiá-lo no escopo o executaria
    duas vezes (V-28, rota `s3`)."""
    root = {
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
    assembled = _montar(root, [_Rec({"name": "R"}, [op])])

    published_by_scope = assembled.body["resources"][0]["operations"][0]["interceptors"]
    assert _tipos(published_by_scope) == ["Payload size"]


def test_restaurar_heranca_e_acrescentar_item_na_mesma_declaracao():
    """`inherit: true` + item sobre um escopo com lista própria obsoleta: o
    obsoleto sai e o escopo volta a executar o herdado, mais o item."""
    root = {"interceptors_request": [{"type": "Log"}, {"type": "Rate limit"}]}
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
    assembled = _montar(root, [_Rec({"name": "R"}, [op])], draft=draft)

    published_by_scope = assembled.body["resources"][0]["operations"][0]["interceptors"]
    assert _tipos(published_by_scope) == ["Payload size"]


def test_cada_nivel_guarda_so_o_que_declara():
    """raiz → recurso → operação: cada um leva só os próprios itens."""
    root = {"interceptors_request": [{"type": "Log"}]}
    op = _Op("GET", {"path": "/x", "inherit": True,
                     "interceptors_request": [{"type": "Payload size"}]})
    resource = _Rec(
        {"name": "R", "inherit": True, "interceptors_request": [{"type": "Rate limit"}]},
        [op],
    )
    assembled = _montar(root, [resource])

    assert _tipos(assembled.body["interceptors"]) == ["Log"]
    assert _tipos(assembled.body["resources"][0]["interceptors"]) == ["Rate limit"]
    assert _tipos(assembled.body["resources"][0]["operations"][0]["interceptors"]) == [
        "Payload size"
    ]


def test_heranca_pura_vai_vazia_no_wire():
    """A codificação compacta: `[]` mantém a propagação viva (V-27 §2)."""
    root = {"interceptors_request": [{"type": "Log"}]}
    op = _Op("GET", {"path": "/x", "inherit": True})
    assembled = _montar(root, [_Rec({"name": "R", "inherit": True}, [op])])

    assert assembled.body["resources"][0]["interceptors"] == []
    assert assembled.body["resources"][0]["operations"][0]["interceptors"] == []


def test_inherit_false_publica_o_declarado_e_marca_a_raiz_nova_pelo_idtemp():
    """A raiz inteira entra no Manager nesta publicação: as marcações apontam
    os itens pelo `idTemp` (V-28 §5)."""
    root = {"interceptors_request": [{"type": "Log"}, {"type": "Rate limit"}]}
    op = _Op("GET", {"path": "/x", "inherit": False,
                     "interceptors_request": [{"type": "Payload size"}]})
    assembled = _montar(root, [_Rec({"name": "R"}, [op])])

    idtemps_da_raiz = sorted(i["idTemp"] for i in assembled.body["interceptors"])
    published_by_scope = assembled.body["resources"][0]["operations"][0]["interceptors"]
    assert _live(published_by_scope) == ["Payload size"]
    tombstones = [i for i in published_by_scope if i.get("status") == "REMOVED"]
    # Formato da UI: o número temporário vai em `id` e em `idTemp`.
    assert sorted(m["parent"]["idTemp"] for m in tombstones) == idtemps_da_raiz
    assert all(m["parent"]["id"] == m["parent"]["idTemp"] for m in tombstones)


def test_inherit_false_sem_itens_manda_so_as_marcacoes_e_nao_avisa():
    """Rota sem interceptors (V-28, `s7`): não há mais "não representável"."""
    op = _Op("GET", {"path": "/x", "inherit": False})
    assembled = _montar(
        _RAIZ_NO_REPO, [_Rec({"name": "R", "inherit": True}, [op])],
        draft=_draft_com(_RAIZ_NO_MANAGER),
    )

    published_by_scope = assembled.body["resources"][0]["operations"][0]["interceptors"]
    assert _live(published_by_scope) == []
    assert _marcados(published_by_scope) == [10, 11]
    assert assembled.warnings == []
    assert assembled.expected["GET /x"] == []


_RAIZ_NO_MANAGER = [
    {"id": 10, "type": "Log", "executionPoint": "FIRST", "position": 0,
     "status": "REFERENCE", "parentType": "REVISION"},
    {"id": 11, "type": "Rate limit", "executionPoint": "FIRST", "position": 1,
     "status": "REFERENCE", "parentType": "REVISION"},
]
_RAIZ_NO_REPO = {"interceptors_request": [{"type": "Log"}, {"type": "Rate limit"}]}


def _draft_com(root, resources=()):
    return {"id": 1, "api": {}, "interceptors": list(root), "resources": list(resources)}


def _marcados(items):
    return sorted(i["parent"]["id"] for i in items if i.get("status") == "REMOVED")


def _live(items):
    return [i["type"] for i in items if i.get("status") != "REMOVED"]


def test_inherit_false_marca_o_herdado_da_raiz_como_removido():
    op = _Op("GET", {"path": "/x", "inherit": False,
                     "interceptors_request": [{"type": "Payload size"}]})
    assembled = _montar(
        _RAIZ_NO_REPO, [_Rec({"name": "R", "inherit": True}, [op])],
        draft=_draft_com(_RAIZ_NO_MANAGER),
    )

    published_by_scope = assembled.body["resources"][0]["operations"][0]["interceptors"]
    assert _live(published_by_scope) == ["Payload size"]
    assert _marcados(published_by_scope) == [10, 11]
    assert assembled.warnings == []


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
    resource = _Rec(
        {"name": "R", "inherit": False,
         "interceptors_request": [{"type": "XSS threat protection"}]},
        [op],
    )
    assembled = _montar(
        _RAIZ_NO_REPO, [resource], draft=_draft_com(_RAIZ_NO_MANAGER, [recurso_remoto])
    )

    block = assembled.body["resources"][0]
    assert _marcados(block["interceptors"]) == [10, 11]
    assert _marcados(block["operations"][0]["interceptors"]) == [20]


def test_inherit_false_marca_o_herdado_que_nasce_na_mesma_publicacao():
    """Sem esperar a próxima publicação: o OAuth novo é marcado pelo `idTemp`."""
    op = _Op("GET", {"path": "/x", "inherit": False,
                     "interceptors_request": [{"type": "Payload size"}]})
    assembled = _montar(
        {"interceptors_request": [{"type": "Log"}, {"type": "OAuth"}]},
        [_Rec({"name": "R", "inherit": True}, [op])],
        draft=_draft_com(_RAIZ_NO_MANAGER[:1]),
    )

    oauth = next(i for i in assembled.body["interceptors"] if i["type"] == "OAuth")
    published_by_scope = assembled.body["resources"][0]["operations"][0]["interceptors"]
    tombstones = {m["type"]: m["parent"] for m in published_by_scope if m.get("status") == "REMOVED"}
    assert tombstones["Log"]["id"] == 10
    assert tombstones["OAuth"] == {"id": oauth["idTemp"], "idTemp": oauth["idTemp"]}
    assert assembled.warnings == []


def test_item_novo_no_recurso_e_marcado_na_rota_pelo_idtemp():
    recurso_remoto = {
        "name": "R", "interceptors": [],
        "operations": [{"id": 5, "method": "GET", "path": "/x", "interceptors": []}],
    }
    op = _Op("GET", {"path": "/x", "inherit": False,
                     "interceptors_request": [{"type": "Payload size"}]})
    resource = _Rec(
        {"name": "R", "inherit": False, "interceptors_request": [{"type": "Rate limit"}]},
        [op],
    )
    assembled = _montar(
        _RAIZ_NO_REPO, [resource], draft=_draft_com(_RAIZ_NO_MANAGER, [recurso_remoto])
    )

    block = assembled.body["resources"][0]
    new = next(i for i in block["interceptors"] if i.get("status") != "REMOVED")
    tombstones = [i for i in block["operations"][0]["interceptors"] if i.get("status") == "REMOVED"]
    assert [m["parent"] for m in tombstones] == [{"id": new["idTemp"], "idTemp": new["idTemp"]}]


def test_o_nao_governado_volta_intacto_mesmo_na_heranca_pura():
    """V-22: `[]` na lista governada não pode levar o preservado junto."""
    preservado = {"id": 7, "type": "Custom", "executionPoint": "THIRD", "position": 9}
    draft = {
        "id": 1, "api": {}, "interceptors": [], "resources": [
            {"name": "R", "interceptors": [preservado], "operations": []}
        ],
    }
    assembled = _montar({}, [_Rec({"name": "R", "inherit": True})], draft=draft)
    assert assembled.body["resources"][0]["interceptors"] == [preservado]


# --- avisos -----------------------------------------------------------------


def test_avisa_que_a_lista_propria_sera_removida():
    """O escopo volta a herdar — e isso APAGA o que ele tinha. Não pode ser calado."""
    flow = resolve_declared_flow([], [{"type": "Log"}], inherit=True)
    warnings = _scope_warnings(flow, _remoto_com("Rate limit"), "POST /x")

    assert len(warnings) == 1
    assert "esses interceptors saem" in warnings[0]
    assert "Rate limit" in warnings[0]
    assert warnings[0].endswith("Se a intenção era mantê-los, liste-os no arquivo.")


def test_nao_avisa_quando_o_escopo_ja_herdava():
    flow = resolve_declared_flow([], [{"type": "Log"}], inherit=True)
    assert _scope_warnings(flow, {"interceptors": []}, "POST /x") == []
    assert _scope_warnings(flow, None, "POST /x") == []


def test_nao_avisa_por_item_nao_governado():
    """V-22: o preservado não é fluxo que o repositório governe."""
    flow = resolve_declared_flow([], [{"type": "Log"}], inherit=True)
    remote = {"interceptors": [{"id": 1, "type": "Custom", "executionPoint": "THIRD"}]}
    assert _scope_warnings(flow, remote, "POST /x") == []


def test_tombstone_sozinho_nao_conta_como_lista_propria():
    flow = resolve_declared_flow([], [{"type": "Log"}], inherit=True)
    remote = {"interceptors": [
        {"id": 1, "type": "XSS threat protection", "executionPoint": "FIRST",
         "status": "REMOVED", "parent": {"id": 9}}
    ]}
    assert _scope_warnings(flow, remote, "POST /x") == []


def _rota_remota(*items):
    return {"name": "R", "interceptors": [], "operations": [
        {"id": 5, "method": "GET", "path": "/x", "interceptors": list(items)}
    ]}


def _cortados(repo_raiz, draft, op_dados):
    op = _Op("GET", {"path": "/x", **op_dados})
    assembled = _montar(repo_raiz, [_Rec({"name": "R", "inherit": True}, [op])], draft=draft)
    return [a for a in assembled.warnings if "deixa de executar" in a]


def test_avisa_o_herdado_que_o_escopo_deixa_de_executar():
    """O repositório importado pela W-4 diz `inherit: false` onde o Manager faz
    append: publicar corta o herdado, e isso não pode sair calado."""
    warnings = _cortados(
        _RAIZ_NO_REPO,
        _draft_com(_RAIZ_NO_MANAGER, [_rota_remota()]),
        {"inherit": False, "interceptors_request": [{"type": "Payload size"}]},
    )
    assert warnings == [
        "GET /x: o arquivo declara `inherit: false`, e ao publicar este ponto deixa de "
        "executar 2 interceptor(es) herdado(s) que executa hoje (Log, Rate limit).\n"
        "Se a intenção era mantê-los, use `inherit: true` para seguir herdando, ou "
        "liste-os no arquivo."
    ]


def test_nao_avisa_o_herdado_que_o_escopo_ja_nao_executava():
    tombstones = [
        {"id": 30 + i["id"], "type": i["type"], "executionPoint": "FIRST", "position": i["position"],
         "status": "REMOVED", "parent": {"id": i["id"], "idTemp": i["id"]}}
        for i in _RAIZ_NO_MANAGER
    ]
    warnings = _cortados(
        _RAIZ_NO_REPO,
        _draft_com(_RAIZ_NO_MANAGER, [_rota_remota(*tombstones)]),
        {"inherit": False, "interceptors_request": [{"type": "Payload size"}]},
    )
    assert warnings == []


def test_nao_avisa_o_item_que_sai_do_proprio_pai():
    """O `Rate limit` sai do `all.yaml`: é mudança do pai, não da rota."""
    warnings = _cortados(
        {"interceptors_request": [{"type": "Log"}]},
        _draft_com(_RAIZ_NO_MANAGER, [_rota_remota()]),
        {"inherit": False, "interceptors_request": [{"type": "Payload size"}]},
    )
    assert len(warnings) == 1 and "deixa de executar 1 interceptor(es)" in warnings[0]
    assert "(Log)" in warnings[0]


def test_nao_avisa_rota_nova_nem_rota_que_herda():
    assert _cortados(
        _RAIZ_NO_REPO, _draft_com(_RAIZ_NO_MANAGER),
        {"inherit": False, "interceptors_request": [{"type": "Payload size"}]},
    ) == []
    assert _cortados(
        _RAIZ_NO_REPO, _draft_com(_RAIZ_NO_MANAGER, [_rota_remota()]),
        {"inherit": True, "interceptors_request": [{"type": "Payload size"}]},
    ) == []


def test_nao_avisa_quando_marcacoes_saem_e_o_herdado_volta():
    """Decisão de 22/10/2026: herdado que volta não é avisado."""
    tombstone = {"id": 40, "type": "Log", "executionPoint": "FIRST", "position": 0,
                "status": "REMOVED", "parent": {"id": 10, "idTemp": 10}}
    op = _Op("GET", {"path": "/x", "inherit": True})
    assembled = _montar(
        _RAIZ_NO_REPO, [_Rec({"name": "R", "inherit": True}, [op])],
        draft=_draft_com(_RAIZ_NO_MANAGER, [_rota_remota(tombstone)]),
    )
    assert assembled.warnings == []


def test_raiz_sem_interceptors_com_fluxo_remoto_avisa_remocao():
    """V-27 §8 (E-1): a raiz não herda de ninguém — `[]` ali é remoção."""
    flow = resolve_declared_flow([], root=True)
    warnings = _scope_warnings(flow, _remoto_com("Log", "Rate limit"), "raiz", root=True)

    assert len(warnings) == 1
    assert "esses interceptors saem" in warnings[0]
    assert "a API tem 2 hoje no Manager" in warnings[0]


def test_raiz_que_declara_fluxo_nao_avisa():
    flow = resolve_declared_flow([{"type": "Log"}], root=True)
    assert _scope_warnings(flow, _remoto_com("Log"), "raiz", root=True) == []


def test_o_aviso_da_raiz_chega_ao_payload_montado():
    draft = {"id": 1, "api": {}, "resources": [], **_remoto_com("Log")}
    assembled = _montar({}, [], draft=draft)
    assert any("esses interceptors saem" in a for a in assembled.warnings)


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
    resource = _Rec({"name": "R", "inherit": False,
                    "interceptors_request": [{"type": "Log"}]})
    published_by_scope = _montar({}, [resource], draft=draft).body["resources"][0]["interceptors"]

    assert len(published_by_scope) == 1
    assert published_by_scope[0].get("status") != "REMOVED"
    assert published_by_scope[0]["id"] != 9  # nasceu novo, não reusou o tombstone


def test_conferir_reporta_tombstone_remanescente():
    sent = {"interceptors": [], "resources": []}
    published = {
        "interceptors": [
            {"id": 1, "type": "XSS threat protection", "executionPoint": "FIRST",
             "status": "REMOVED", "parent": {"id": 9}}
        ],
        "resources": [],
    }
    divergences = revision_payload.verify(sent, published)
    assert any("marcação(ões) de interceptor removido" in d for d in divergences)


_MARCACAO = {"id": None, "idTemp": 30, "type": "Log", "executionPoint": "FIRST",
             "position": 0, "status": "REMOVED", "parent": {"id": 10, "idTemp": 10}}


def _com_rota(items):
    return {
        "interceptors": [],
        "resources": [{"name": "R", "interceptors": [], "operations": [
            {"method": "GET", "path": "/x", "interceptors": items}
        ]}],
    }


def test_conferir_aceita_a_marcacao_enviada_e_gravada():
    gravada = {**_MARCACAO, "id": 31}
    assert revision_payload.verify(_com_rota([_MARCACAO]), _com_rota([gravada])) == []


def test_conferir_reporta_marcacao_enviada_e_nao_gravada():
    divergences = revision_payload.verify(_com_rota([_MARCACAO]), _com_rota([]))
    assert any(
        d.startswith("GET /x:") and "que o Manager não gravou" in d for d in divergences
    )


_OAUTH_NOVO = {"id": None, "idTemp": 40, "type": "OAuth", "executionPoint": "FIRST",
               "position": 1, "content": '{"grantTypes": []}'}
_LOG_EXISTENTE = {"id": 10, "type": "Log", "executionPoint": "FIRST", "position": 0,
                  "content": '{"acceptedTerms": true}'}


def _arvore(root, route):
    return {"interceptors": list(root), "resources": [{"name": "R", "interceptors": [], "operations": [
        {"method": "GET", "path": "/x", "interceptors": list(route)}
    ]}]}


def _marcacao_de(target, **field_names):
    return {"id": None, "idTemp": 41, "type": target["type"], "executionPoint": "FIRST",
            "position": target["position"], "status": "REMOVED", "content": target["content"],
            **field_names}


def test_conferir_casa_a_marcacao_por_idtemp_com_o_id_gravado():
    """A marcação enviada por `idTemp` volta com o id que o Manager gerou."""
    enviada = _marcacao_de(_OAUTH_NOVO, parent={"id": None, "idTemp": 40})
    oauth_gravado = {**_OAUTH_NOVO, "id": 900, "idTemp": None}
    gravada = {**enviada, "id": 901, "idTemp": None, "parent": {"id": 900, "idTemp": 900}}

    sent = _arvore([_LOG_EXISTENTE, _OAUTH_NOVO], [enviada])
    published = _arvore([_LOG_EXISTENTE, oauth_gravado], [gravada])
    assert revision_payload.verify(sent, published) == []


def test_conferir_acusa_marcacao_gravada_para_outro_item():
    enviada = _marcacao_de(_OAUTH_NOVO, parent={"id": None, "idTemp": 40})
    oauth_gravado = {**_OAUTH_NOVO, "id": 900, "idTemp": None}
    trocada = {**_marcacao_de(_LOG_EXISTENTE), "id": 901, "parent": {"id": 10, "idTemp": 10}}

    divergences = revision_payload.verify(
        _arvore([_LOG_EXISTENTE, _OAUTH_NOVO], [enviada]),
        _arvore([_LOG_EXISTENTE, oauth_gravado], [trocada]),
    )
    assert any("GET /x" in d and "(Log)" in d and "não foram enviadas" in d for d in divergences)
    assert any("GET /x" in d and "(OAuth)" in d and "não gravou" in d for d in divergences)


def test_conferir_nao_conta_tombstone_como_fluxo():
    """8 itens mais 1 supressão não são 9 — a contagem olha só os vivos."""
    vivos = [
        {"id": i, "type": "Log", "executionPoint": "FIRST", "position": i}
        for i in range(1, 9)
    ]
    sent = {"interceptors": vivos, "resources": []}
    published = {"interceptors": vivos, "resources": []}
    assert revision_payload.verify(sent, published) == []


# --- content como string JSON ----------------------------------------------


def test_content_de_item_novo_sai_serializado():
    """O wire recusa dict com HTTP 400."""
    op = _Op("GET", {
        "path": "/x",
        "inherit": False,
        "interceptors_request": [{"type": "Payload size", "content": {"maxSize": 2048}}],
    }, file="get_x.yaml")
    assembled = _montar({}, [_Rec({"name": "R"}, [op])])

    item = assembled.body["resources"][0]["operations"][0]["interceptors"][0]
    assert isinstance(item["content"], str)
    assert json.loads(item["content"]) == {"maxSize": 2048}


def test_custom_novo_recebe_o_content_do_catalogo():
    resource = _Rec({
        "name": "R",
        "inherit": False,
        "interceptors_request": [{"type": "Custom", "id": 32}],
    })
    assembled = revision_payload.assemble(
        draft={"id": 1, "interceptors": [], "resources": [], "api": {}},
        basic_info={"spec": {}},
        root={},
        resources=[resource],
        resolver_custom=lambda c: {"id": c, "name": "Release Notes", "script": "x"},
    )
    item = assembled.body["resources"][0]["interceptors"][0]
    assert item["customInterceptorId"] == 32
    assert json.loads(item["content"])["name"] == "Release Notes"


def test_marcacao_de_custom_novo_da_raiz_leva_o_content_do_catalogo():
    """A marcação copia o item que remove — inclusive o `{id, name, script}`."""
    op = _Op("GET", {"path": "/x", "inherit": False,
                     "interceptors_request": [{"type": "Log"}]})
    assembled = revision_payload.assemble(
        draft={"id": 1, "interceptors": [], "resources": [], "api": {}},
        basic_info={"spec": {}},
        root={"interceptors_request": [{"type": "Custom", "id": 33}]},
        resources=[_Rec({"name": "R"}, [op])],
        resolver_custom=lambda c: {"id": c, "name": "CyberArk", "script": "y"},
    )
    published_by_scope = assembled.body["resources"][0]["operations"][0]["interceptors"]
    tombstone = next(i for i in published_by_scope if i.get("status") == "REMOVED")
    assert tombstone["customInterceptorId"] == 33
    assert json.loads(tombstone["content"])["name"] == "CyberArk"


# --- Conferência do `api` aninhado (W-8) --------------------------------------

_TAGS_ENVIADAS = [
    {"attributeName": "teste giroto", "tags": ["teste giroto"]},
    {"attributeName": "My new", "tags": ["Tag1"]},
]


def _com_api(**api):
    return {"api": dict(api), "resources": [], "interceptors": []}


def test_conferir_acusa_apitags_apagadas_pela_plataforma():
    """A tag inexistente foi aceita com 200 e o Manager zerou as apiTags."""
    sent = _com_api(apiTags=_TAGS_ENVIADAS)
    published = _com_api(apiTags=[])

    divergences = revision_payload.verify(sent, published)

    assert any("`My new` foi enviado em `apiTags`" in d for d in divergences)
    assert any("`teste giroto` foi enviado em `apiTags`" in d for d in divergences)


def test_conferir_acusa_tags_diferentes_no_mesmo_atributo():
    sent = _com_api(apiTags=[{"attributeName": "My new", "tags": ["Tag1"]}])
    published = _com_api(apiTags=[{"attributeName": "My new", "tags": ["Tag2"]}])

    divergences = revision_payload.verify(sent, published)

    assert divergences == [
        "o atributo `My new` foi enviado com as tags ['Tag1'] e gravado com ['Tag2']"
    ]


def test_conferir_acusa_atributo_que_sobrou_no_manager():
    sent = _com_api(apiTags=[])
    published = _com_api(apiTags=[{"attributeName": "Velho", "tags": ["x"]}])

    assert revision_payload.verify(sent, published) == [
        "o atributo `Velho` está nas `apiTags` do Manager mas não foi enviado"
    ]


def test_conferir_ignora_a_ordem_das_apitags_e_das_tags():
    sent = _com_api(apiTags=[
        {"attributeName": "A", "tags": ["1", "2"]},
        {"attributeName": "B", "tags": ["3"]},
    ])
    published = _com_api(apiTags=[
        {"attributeName": "B", "tags": ["3"]},
        {"attributeName": "A", "tags": ["2", "1"]},
    ])

    assert revision_payload.verify(sent, published) == []


def test_conferir_sem_apitags_no_envio_nao_confere_tags():
    """Ausente preserva: o que não foi enviado não é veredito."""
    sent = _com_api(name="X")
    published = _com_api(name="X", apiTags=[{"attributeName": "A", "tags": ["1"]}])

    assert revision_payload.verify(sent, published) == []


def test_conferir_acusa_name_e_description_divergentes():
    sent = _com_api(name="Novo", description="depois")
    published = _com_api(name="Antigo", description="depois")

    assert revision_payload.verify(sent, published) == [
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
    assembled = _montar(RAIZ_ALTERADA, draft=DRAFT_COM_CONTENT)
    rate = next(i for i in assembled.body["interceptors"] if i["type"] == "Rate limit")
    assert json.loads(rate["content"]) == {"quota": "500"}
    assert rate["id"] == 11


def test_esperado_carrega_o_fluxo_declarado_por_escopo():
    op = _Op("GET", {"path": "/x", "inherit": False,
                     "interceptors_request": [{"type": "Payload size", "content": {"maxSize": 1}}]})
    assembled = _montar(RAIZ_ALTERADA, [_Rec({"name": "R"}, [op])], draft=DRAFT_COM_CONTENT)

    assert _tipos(assembled.expected["raiz"]) == ["Log", "Rate limit"]
    assert _tipos(assembled.expected["GET /x"]) == ["Payload size"]
    # herança pura vai como `[]`: não há lista própria para conferir
    assert "resource R" not in assembled.expected


def test_esperado_do_append_e_so_o_declarado():
    op = _Op("GET", {"path": "/x", "inherit": True,
                     "interceptors_request": [{"type": "Payload size", "content": {"maxSize": 1}}]})
    assembled = _montar(RAIZ_ALTERADA, [_Rec({"name": "R"}, [op])], draft=DRAFT_COM_CONTENT)
    assert _tipos(assembled.expected["GET /x"]) == ["Payload size"]


def _publicado_com(*items):
    return {"interceptors": list(items), "resources": [], "api": {}}


def test_conferir_acusa_content_que_nao_foi_gravado_como_declarado():
    """O caso do S10: o 200 e a comparação com o payload davam verde."""
    assembled = _montar(RAIZ_ALTERADA, draft=DRAFT_COM_CONTENT)
    published = _publicado_com(
        {"id": 10, "type": "Log", "executionPoint": "FIRST", "position": 2,
         "content": '{"encryptContent": false}'},
        {"id": 11, "type": "Rate limit", "executionPoint": "FIRST", "position": 4,
         "content": '{"quota": "1000"}'},
    )
    divergences = revision_payload.verify(
        assembled.body, published, expected=assembled.expected
    )
    assert any("Rate limit" in d and "`quota` declarado" in d for d in divergences)


def test_conferir_acusa_ordem_diferente_da_declarada():
    assembled = _montar(RAIZ_ALTERADA, draft=DRAFT_COM_CONTENT)
    published = _publicado_com(
        {"id": 11, "type": "Rate limit", "executionPoint": "FIRST", "position": 2,
         "content": '{"quota": "500"}'},
        {"id": 10, "type": "Log", "executionPoint": "FIRST", "position": 4,
         "content": '{"encryptContent": false}'},
    )
    divergences = revision_payload.verify(
        assembled.body, published, expected=assembled.expected
    )
    assert any("declarado como [Log, Rate limit]" in d for d in divergences)


def test_conferir_normaliza_escalar_e_ignora_content_de_custom():
    """`"500"` e `500` são o mesmo valor (V-11 §4); Custom casa só pelo id."""
    root = {"interceptors_request": [
        {"type": "Rate limit", "content": {"quota": 500}},
        {"type": "Custom", "id": 32},
    ]}
    assembled = _montar(root)
    published = _publicado_com(
        {"id": 1, "type": "Rate limit", "executionPoint": "FIRST", "position": 1,
         "content": '{"quota": "500"}'},
        {"id": 2, "type": "Custom", "customInterceptorId": 32, "executionPoint": "FIRST",
         "position": 2, "content": '{"id": 32, "script": "qualquer"}'},
    )
    assert revision_payload.verify(assembled.body, published, expected=assembled.expected) == []


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
    warnings = _montar({}, [letras, saude], draft=DRAFT_COM_ROTAS).warnings

    routes = [a for a in warnings if a.startswith("As rotas abaixo")]
    assert routes == [
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
    warnings = _montar({}, [letras], draft=DRAFT_COM_ROTAS).warnings

    assert warnings == [
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
    assert _montar({}, [letras, saude], draft=DRAFT_COM_ROTAS).warnings == []


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


def _aviso_de_homonimos(folders, name):
    return (
        f"As pastas {folders} declaram recursos com o mesmo nome, \"{name}\". O "
        "Manager aceita, mas quem olha a API vê recursos iguais e não sabe qual é "
        "qual.\n"
        "Se são o mesmo recurso, junte as rotas em uma pasta só. Se não são, dê a "
        "cada um um nome diferente no `resource.yaml`."
    )


def test_rota_movida_para_pasta_homonima_nao_e_avisada_como_apagada():
    """O caso da 417 rev3: a pasta copiada manteve o `name`."""
    resources = [
        _Rec({"name": "Tarefas"}, [_Op("GET", {"path": "/tarefas/{id}"})], slug="tarefas"),
        _Rec({"name": "Tarefas"}, [_Op("GET", {"path": "/tarefas"})], slug="tarefas 2"),
    ]
    assembled = _montar({}, resources, draft=DRAFT_TAREFAS)

    assert assembled.warnings == [
        _aviso_de_homonimos("`tarefas` e `tarefas 2`", "Tarefas"),
        "As rotas abaixo estão no repositório em um recurso diferente do que têm "
        "hoje no Manager. Ao publicar, elas saem do recurso de origem e passam "
        "para o de destino:\n"
        "  - GET /tarefas: sai do recurso Tarefas e vai para o recurso Tarefas "
        "(pasta `tarefas 2`), que será criado\n\n"
        "Se não era essa a intenção, devolva-as à pasta do recurso de origem.",
    ]
    fica, nova = assembled.body["resources"]
    # empate (1 rota cada, mesmo nome): fica com o `id` a primeira pasta
    assert fica["id"] == 50
    assert [o["id"] for o in fica["operations"]] == [502]
    assert "id" not in nova
    assert "id" not in nova["operations"][0]  # W-6: operação que muda de recurso vai nova


def test_homonimos_vindos_do_manager_voltam_intactos():
    """A 409 rev1: puxar e publicar de volta sem mudança não altera nada."""
    assembled = _montar({}, _letras_homonimos(), draft=DRAFT_LETRAS_HOMONIMOS)

    assert assembled.warnings == [
        _aviso_de_homonimos("`letras-letras-id` e `letras-tarefas-id-letras`", "Letras")
    ]
    assert [r["id"] for r in assembled.body["resources"]] == [101, 102]
    assert [r["operations"][0]["id"] for r in assembled.body["resources"]] == [1, 2]


def test_ligacao_independe_da_ordem_dos_recursos_no_manager():
    draft = dict(DRAFT_LETRAS_HOMONIMOS,
                 resources=list(reversed(DRAFT_LETRAS_HOMONIMOS["resources"])))
    assembled = _montar({}, _letras_homonimos(), draft=draft)
    assert [r["id"] for r in assembled.body["resources"]] == [101, 102]


def test_homonimo_que_sai_e_avisado_mesmo_com_o_nome_ainda_presente():
    """Antes, o aviso comparava nomes: `Letras` continuava lá e nada era dito."""
    warnings = _montar({}, _letras_homonimos()[:1], draft=DRAFT_LETRAS_HOMONIMOS).warnings

    assert warnings == [
        "Os recursos abaixo existem no Manager mas não estão no repositório. Ao "
        "publicar, eles serão apagados do Manager:\n"
        "  - Letras (rota POST /tarefas/{id}/letras)\n\n"
        "Se não era essa a intenção, adicione-os ao repositório antes de publicar."
    ]


def test_renomear_recurso_mantem_o_id():
    resource = _Rec({"name": "Tarefas v2"}, [
        _Op("GET", {"path": "/tarefas"}),
        _Op("GET", {"path": "/tarefas/{id}"}),
    ])
    assembled = _montar({}, [resource], draft=DRAFT_TAREFAS)

    assert assembled.warnings == []
    block = assembled.body["resources"][0]
    assert (block["id"], block["name"]) == (50, "Tarefas v2")
    assert [o["id"] for o in block["operations"]] == [501, 502]


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
    assembled = _montar({}, [junto], draft=draft)

    assert assembled.warnings == [
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
    block = assembled.body["resources"][0]
    assert block["id"] == 10
    assert [o.get("id") for o in block["operations"]] == [1, None]


def test_sem_rota_em_comum_e_recurso_novo_mesmo_com_nome_igual():
    """Decisão: sem ligação pelo nome — sem rota em comum é outro recurso."""
    resource = _Rec({"name": "Tarefas"}, [_Op("GET", {"path": "/outra"})])
    assembled = _montar({}, [resource], draft=DRAFT_TAREFAS)

    assert "id" not in assembled.body["resources"][0]
    assert assembled.warnings[0].startswith("Os recursos abaixo existem no Manager")
    assert "  - Tarefas\n" in assembled.warnings[0]


def test_parear_desempata_por_quantidade_e_depois_pelo_nome():
    remote_resources = [("X", [("GET", "/a"), ("GET", "/b")])]
    # mais rotas em comum vence, mesmo com outro nome
    assert revision_payload.pair_by_routes(
        [("X", [("GET", "/a")]), ("Y", [("GET", "/a"), ("GET", "/b")])], remote_resources
    ) == {1: 0}
    # empatado em rotas, vence o de mesmo nome
    assert revision_payload.pair_by_routes(
        [("Y", [("GET", "/a")]), ("X", [("GET", "/b")])], remote_resources
    ) == {1: 0}


# --- conferência com homônimos ----------------------------------------------


def test_conferir_homonimos_publicados_como_enviados_nao_diverge():
    assembled = _montar({}, _letras_homonimos(), draft=DRAFT_LETRAS_HOMONIMOS)
    published = json.loads(json.dumps(assembled.body))
    published["resources"].reverse()  # a ordem do GET não é contrato

    assert revision_payload.verify(assembled.body, published, expected=assembled.expected) == []


def test_conferir_acusa_rota_descartada_de_um_dos_homonimos():
    assembled = _montar({}, _letras_homonimos(), draft=DRAFT_LETRAS_HOMONIMOS)
    published = json.loads(json.dumps(assembled.body))
    published["resources"][1]["operations"] = []

    divergences = revision_payload.verify(assembled.body, published)
    assert (
        "a operação POST /tarefas/{id}/letras, do recurso Letras (rota POST "
        "/tarefas/{id}/letras), foi enviada mas não está no Manager"
    ) in divergences


def test_conferir_acusa_rota_que_o_manager_nao_moveu():
    """W-6: a mudança de recurso pode ser descartada com 200."""
    resources = [
        _Rec({"name": "Tarefas"}, [_Op("GET", {"path": "/tarefas/{id}"})], slug="tarefas"),
        _Rec({"name": "Tarefas"}, [_Op("GET", {"path": "/tarefas"})], slug="tarefas 2"),
    ]
    assembled = _montar({}, resources, draft=DRAFT_TAREFAS)

    divergences = revision_payload.verify(assembled.body, DRAFT_TAREFAS)
    assert (
        "o recurso Tarefas (rota GET /tarefas) foi enviado mas não está no Manager"
    ) in divergences