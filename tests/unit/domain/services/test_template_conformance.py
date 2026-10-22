"""Conformidade com a régua (V-11 · D-13).

O oracle da V-11 §3 previa **4 achados** na API 417 contra a régua 414. Ele foi
escrito em 2026-10-14 e descreve um estado que **não existe mais** — e o estado
seguiu se movendo durante a implementação:

* a 417 trocou `Custom#125` por `#32` (o caderno §5 registra a troca);
* em 2026-10-15, durante a própria sessão de implementação, a **régua 414**
  passou a pedir `#32`/`#33` no lugar de `#125`/`#178`, com ids de interceptor
  novos (`19768`, `19769`).

A revisão 9175 da 417, que estas fixtures congelam, ainda executa `#125`/`#178`,
então a divergência é real e se propaga a todo escopo que herda da raiz. É
exatamente o caso que o **snapshot da régua** (D-4/P-3) existe para tornar
rastreável: sem `id`, `revisionNumber` e hash gravados junto com o achado, um
relatório destes envelhece sem aviso.

Os quatro achados originais continuam sendo produzidos; o que mudou foi o estado
medido, não a regra. É exatamente o caso que o **snapshot da régua** (D-4/P-3)
existe para tornar rastreável.
"""

import json
import pathlib

import pytest

from apiops_orchestrator.domain.services.interceptor_flow import fluxo_composto
from apiops_orchestrator.domain.services.template_conformance import (
    SEVERIDADE_INFO,
    SEVERIDADE_WARNING,
    comparar,
)

FIXTURES = pathlib.Path(__file__).parents[3] / "fixtures" / "manager"

LOG = {"acceptedTerms": True, "encryptContent": False}


def _item(tipo, ponto="FIRST", **extra):
    return {"type": tipo, "executionPoint": ponto, **extra}


# --- regras do comparador --------------------------------------------------


def test_conforme_nao_produz_achado():
    fluxo = [_item("Log", content=LOG), _item("Payload size", content={"maxSize": 2048})]
    assert comparar(fluxo, list(fluxo), "raiz") == []


def test_item_alem_da_regua_e_info():
    regua = [_item("Log", content=LOG)]
    fluxo = regua + [_item("Payload size", content={"maxSize": 2048})]
    achados = comparar(fluxo, regua, "raiz")
    assert [a.severidade for a in achados] == [SEVERIDADE_INFO]
    assert "Payload size" in achados[0].mensagem


def test_item_da_regua_ausente_e_warning():
    regua = [_item("Log", content=LOG), _item("XSS threat protection", content={})]
    fluxo = [_item("Log", content=LOG)]
    achados = comparar(fluxo, regua, "GET /tarefas")
    assert [a.severidade for a in achados] == [SEVERIDADE_WARNING]
    assert "XSS threat protection" in achados[0].mensagem


def test_content_divergente_e_warning_e_nomeia_o_campo():
    """O caso real: um `Log` que a régua também tem, diferindo só no `content`."""
    regua = [_item("Log", content={"acceptedTerms": True, "encryptContent": False})]
    fluxo = [_item("Log", content={"acceptedTerms": True, "encryptContent": True})]
    achados = comparar(fluxo, regua, "POST /x")
    assert [a.severidade for a in achados] == [SEVERIDADE_WARNING]
    assert "encryptContent" in achados[0].mensagem


def test_comparacao_e_por_sequencia_nao_por_conjunto():
    """V-11 §4.1: um `Log` a mais some numa comparação por conjunto."""
    regua = [_item("Log", content=LOG)]
    fluxo = [_item("Log", content=LOG), _item("Log", content=LOG)]
    achados = comparar(fluxo, regua, "raiz")
    assert len(achados) == 1 and achados[0].severidade == SEVERIDADE_INFO


def test_custom_casa_por_id_sem_comparar_content():
    """Mesmo id, mesmo objeto no tenant: comparar o script seria ruído."""
    regua = [_item("Custom", customInterceptorId=125, content="script A")]
    fluxo = [_item("Custom", customInterceptorId=125, content="script B")]
    assert comparar(fluxo, regua, "raiz") == []


def test_custom_de_id_diferente_e_divergencia():
    regua = [_item("Custom", customInterceptorId=125)]
    fluxo = [_item("Custom", customInterceptorId=32)]
    achados = comparar(fluxo, regua, "raiz")
    assert {a.severidade for a in achados} == {SEVERIDADE_WARNING, SEVERIDADE_INFO}


def test_escalar_numerico_normalizado_nao_produz_achado_falso():
    """O wire devolve `"quota": "1000"`; o repositório pode trazer o inteiro."""
    regua = [_item("Rate limit", content={"quota": "1000"})]
    fluxo = [_item("Rate limit", content={"quota": 1000})]
    assert comparar(fluxo, regua, "raiz") == []


def test_content_como_json_serializado_e_aceito():
    regua = [_item("Log", content='{"acceptedTerms": true}')]
    fluxo = [_item("Log", content={"acceptedTerms": True})]
    assert comparar(fluxo, regua, "raiz") == []


def test_nao_governado_e_ignorado():
    """V-22: fora de FIRST/SECOND nada é comparado."""
    regua = [_item("Log", content=LOG)]
    fluxo = [_item("Log", content=LOG), _item("Custom", ponto="THIRD", customInterceptorId=178)]
    assert comparar(fluxo, regua, "raiz") == []


def test_pontos_de_execucao_sao_comparados_separadamente():
    regua = [_item("Log", "FIRST", content=LOG), _item("Log", "SECOND", content=LOG)]
    fluxo = [_item("Log", "FIRST", content=LOG)]
    achados = comparar(fluxo, regua, "raiz")
    assert len(achados) == 1 and "Log" in achados[0].mensagem


# --- oracle contra o estado real congelado ---------------------------------


def _achados_da_417():
    regua = json.loads((FIXTURES / "regua-414.json").read_text(encoding="utf-8"))[
        "interceptors"
    ]
    rev = json.loads((FIXTURES / "api-417-rev2.json").read_text(encoding="utf-8"))[
        "revision"
    ]
    raiz = fluxo_composto(rev.get("interceptors"))
    saida = {"raiz da revision": comparar(raiz, regua, "raiz da revision")}
    for recurso in rev.get("resources") or []:
        efetivo = fluxo_composto(recurso.get("interceptors"), raiz)
        saida[f"resource {recurso.get('name')}"] = comparar(
            efetivo, regua, f"resource {recurso.get('name')}"
        )
        for op in recurso.get("operations") or []:
            rotulo = f"{op.get('method')} {op.get('path')}"
            saida[rotulo] = comparar(
                fluxo_composto(op.get("interceptors"), efetivo), regua, rotulo
            )
    return saida


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_oracle_a_raiz_diverge_da_regua_em_exatamente_um_custom():
    """A deriva real: a régua pede `Custom#125`, a 417 executa `#32`."""
    achados = _achados_da_417()["raiz da revision"]
    assert len(achados) == 2
    # A régua pede #33, a revisão 9175 ainda executa #178 — o MESMO interceptor
    # sob dois ids, o que só fica visível porque o rótulo traz o nome (V-11 §5).
    ausente = next(a for a in achados if a.severidade == SEVERIDADE_WARNING)
    alem = next(a for a in achados if a.severidade == SEVERIDADE_INFO)
    assert "Custom #33" in ausente.mensagem
    assert "Custom #178" in alem.mensagem
    assert "CyberArk and OAuth Autentication" in ausente.mensagem
    assert "CyberArk and OAuth Autentication" in alem.mensagem


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_oracle_supressao_do_tombstone_aparece_na_conformidade():
    """V-11 §3, achado do `GET /tarefas`: tombstone removendo o XSS."""
    achados = _achados_da_417()["GET /tarefas"]
    assert any(
        "XSS threat protection" in a.mensagem and a.severidade == SEVERIDADE_WARNING
        for a in achados
    )


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_oracle_append_de_additional_info_no_recurso_de_atribuicao():
    """V-11 §3: append de `Additional Info` (SECOND) — INFO."""
    achados = _achados_da_417()["resource Atribuicao Responsavel"]
    assert any(
        "Additional Info" in a.mensagem and a.severidade == SEVERIDADE_INFO
        for a in achados
    )


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_oracle_log_proprio_da_rota_executa_depois_do_herdado():
    """O `Log` com `encryptContent: true` da rota não substitui o `Log` da raiz:
    roda depois do herdado (V-28), e aparece como acréscimo, não como alteração."""
    achados = _achados_da_417()["POST /tarefas/{id}/atribuicao-responsavel"]
    assert not any("encryptContent" in a.mensagem for a in achados)
    assert achados[-1].severidade == SEVERIDADE_INFO and '"Log"' in achados[-1].mensagem


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_oracle_copia_do_health_check_nao_tira_o_custom_178():
    """A rota reproduz o fluxo sem marcar nada: segue executando a raiz inteira,
    `Custom #178` incluído, e a cópia roda de novo depois (V-28 §6)."""
    mensagens = [a.mensagem for a in _achados_da_417()["GET /health-check"]]
    assert any("Custom #178" in m for m in mensagens)
    assert sum('"Log" não existe na template' in m for m in mensagens) == 3


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_oracle_conjunto_congelado_do_estado_de_2026_10_15():
    """Trava o conjunto inteiro: qualquer mudança de regra aparece aqui.

    Composto como o Manager executa (V-28): as cópias do herdado no
    `/health-check` e no `Atribuicao Responsavel` rodam de novo e contam como
    acréscimo."""
    todos = [a for lista in _achados_da_417().values() for a in lista]
    assert len(todos) == 60
    assert sum(1 for a in todos if a.severidade == SEVERIDADE_WARNING) == 13
    assert sum(1 for a in todos if a.severidade == SEVERIDADE_INFO) == 47


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_nenhum_achado_bloqueia():
    """V-11 §3: nenhum deles impede a publicação."""
    for lista in _achados_da_417().values():
        for achado in lista:
            assert achado.severidade in (SEVERIDADE_INFO, SEVERIDADE_WARNING)


# --- rótulo legível (V-11 §5) ----------------------------------------------


def test_rotulo_de_custom_traz_o_nome():
    """O id sozinho não diz nada a quem lê o relatório.

    `Custom #33` e `Custom #178` parecem interceptors diferentes; com o nome,
    vê-se que são o MESMO sob ids distintos — que é a deriva real do tenant.
    """
    regua = [
        _item("Custom", customInterceptorId=33,
              content='{"id": 33, "name": "CyberArk and OAuth Autentication"}')
    ]
    achados = comparar([], regua, "GET /x")
    assert "Custom #33 — CyberArk and OAuth Autentication" in achados[0].mensagem


def test_rotulo_degrada_para_o_id_quando_o_nome_e_desconhecido():
    regua = [_item("Custom", customInterceptorId=99)]
    achados = comparar([], regua, "GET /x")
    assert "Custom #99" in achados[0].mensagem


def test_rotulo_de_nativo_e_o_proprio_tipo():
    regua = [_item("XSS threat protection", content={})]
    achados = comparar([], regua, "GET /x")
    assert '"XSS threat protection"' in achados[0].mensagem


def test_content_ilegivel_nao_quebra_o_rotulo():
    regua = [_item("Custom", customInterceptorId=7, content="nao e json")]
    achados = comparar([], regua, "GET /x")
    assert "Custom #7" in achados[0].mensagem


# --- item que só mudou de posição -------------------------------------------


def _custom(cid, nome):
    return _item("Custom", customInterceptorId=cid,
                 content=json.dumps({"id": cid, "name": nome}))


def test_item_que_mudou_de_posicao_vira_um_achado_so():
    """O caso real da 417: o Custom #32 é o 1º na template e o 7º na API.

    Antes saíam dois achados falsos: "não é executado aqui" e "não existe na
    template". O item existe dos dois lados; o que mudou foi a ordem.
    """
    regua = [_custom(32, "Release Notes"), _item("Log", content=LOG), _custom(33, "CyberArk"),
             _item("Rate limit"), _item("Payload size"), _item("XSS threat protection"),
             _item("Log", content=LOG)]
    efetivo = [_item("Log", content=LOG), _custom(33, "CyberArk"), _item("Rate limit"),
               _item("Payload size"), _item("XSS threat protection"), _item("Log", content=LOG),
               _custom(32, "Release Notes")]

    achados = comparar(efetivo, regua, "raiz")

    assert [(a.severidade, a.mensagem) for a in achados] == [(
        SEVERIDADE_WARNING,
        '"Custom #32 — Release Notes" executa em outra posição: na template é o 1º do '
        "request, aqui é o 7º",
    )]


def test_item_movido_com_content_diferente_gera_posicao_e_configuracao():
    regua = [_item("Payload size", content={"maxSize": 10}), _item("Log", content=LOG)]
    efetivo = [_item("Log", content=LOG), _item("Payload size", content={"maxSize": 99})]

    mensagens = [a.mensagem for a in comparar(efetivo, regua, "raiz")]

    assert any("executa em outra posição" in m for m in mensagens)
    assert any("configurado diferente" in m and "maxSize" in m for m in mensagens)
    assert not any("não é executado aqui" in m or "acréscimo" in m for m in mensagens)


def test_ausencia_e_acrescimo_de_verdade_continuam_reportados():
    regua = [_item("Log", content=LOG), _custom(33, "CyberArk")]
    efetivo = [_item("Log", content=LOG), _custom(32, "Release Notes")]

    mensagens = [a.mensagem for a in comparar(efetivo, regua, "raiz")]

    assert any("Custom #33" in m and "não é executado aqui" in m for m in mensagens)
    assert any("Custom #32" in m and "acréscimo" in m for m in mensagens)
    assert not any("outra posição" in m for m in mensagens)


def test_posicao_no_response_nomeia_o_response():
    regua = [_item("Log", "SECOND", content=LOG), _item("Payload size", "SECOND")]
    efetivo = [_item("Payload size", "SECOND"), _item("Log", "SECOND", content=LOG)]

    mensagens = [a.mensagem for a in comparar(efetivo, regua, "raiz")]
    assert any("do response" in m for m in mensagens)
