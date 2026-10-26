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

from apiops_orchestrator.domain.services.interceptor_flow import composed_flow
from apiops_orchestrator.domain.services.template_conformance import (
    SEVERITY_INFO,
    SEVERITY_WARNING,
    compare,
)

FIXTURES = pathlib.Path(__file__).parents[3] / "fixtures" / "manager"

LOG = {"acceptedTerms": True, "encryptContent": False}


def _item(kind, point="FIRST", **extra):
    return {"type": kind, "executionPoint": point, **extra}


# --- regras do comparador --------------------------------------------------


def test_conforme_nao_produz_achado():
    flow = [_item("Log", content=LOG), _item("Payload size", content={"maxSize": 2048})]
    assert compare(flow, list(flow), "raiz") == []


def test_item_alem_da_regua_e_info():
    ruler = [_item("Log", content=LOG)]
    flow = ruler + [_item("Payload size", content={"maxSize": 2048})]
    findings = compare(flow, ruler, "raiz")
    assert [a.severity for a in findings] == [SEVERITY_INFO]
    assert "Payload size" in findings[0].message


def test_item_da_regua_ausente_e_warning():
    ruler = [_item("Log", content=LOG), _item("XSS threat protection", content={})]
    flow = [_item("Log", content=LOG)]
    findings = compare(flow, ruler, "GET /tarefas")
    assert [a.severity for a in findings] == [SEVERITY_WARNING]
    assert "XSS threat protection" in findings[0].message


def test_content_divergente_e_warning_e_nomeia_o_campo():
    """O caso real: um `Log` que a régua também tem, diferindo só no `content`."""
    ruler = [_item("Log", content={"acceptedTerms": True, "encryptContent": False})]
    flow = [_item("Log", content={"acceptedTerms": True, "encryptContent": True})]
    findings = compare(flow, ruler, "POST /x")
    assert [a.severity for a in findings] == [SEVERITY_WARNING]
    assert "encryptContent" in findings[0].message


def test_comparacao_e_por_sequencia_nao_por_conjunto():
    """V-11 §4.1: um `Log` a mais some numa comparação por conjunto."""
    ruler = [_item("Log", content=LOG)]
    flow = [_item("Log", content=LOG), _item("Log", content=LOG)]
    findings = compare(flow, ruler, "raiz")
    assert len(findings) == 1 and findings[0].severity == SEVERITY_INFO


def test_custom_casa_por_id_sem_comparar_content():
    """Mesmo id, mesmo objeto no tenant: comparar o script seria ruído."""
    ruler = [_item("Custom", customInterceptorId=125, content="script A")]
    flow = [_item("Custom", customInterceptorId=125, content="script B")]
    assert compare(flow, ruler, "raiz") == []


def test_custom_de_id_diferente_e_divergencia():
    ruler = [_item("Custom", customInterceptorId=125)]
    flow = [_item("Custom", customInterceptorId=32)]
    findings = compare(flow, ruler, "raiz")
    assert {a.severity for a in findings} == {SEVERITY_WARNING, SEVERITY_INFO}


def test_escalar_numerico_normalizado_nao_produz_achado_falso():
    """O wire devolve `"quota": "1000"`; o repositório pode trazer o inteiro."""
    ruler = [_item("Rate limit", content={"quota": "1000"})]
    flow = [_item("Rate limit", content={"quota": 1000})]
    assert compare(flow, ruler, "raiz") == []


def test_content_como_json_serializado_e_aceito():
    ruler = [_item("Log", content='{"acceptedTerms": true}')]
    flow = [_item("Log", content={"acceptedTerms": True})]
    assert compare(flow, ruler, "raiz") == []


def test_nao_governado_e_ignorado():
    """V-22: fora de FIRST/SECOND nada é comparado."""
    ruler = [_item("Log", content=LOG)]
    flow = [_item("Log", content=LOG), _item("Custom", point="THIRD", customInterceptorId=178)]
    assert compare(flow, ruler, "raiz") == []


def test_pontos_de_execucao_sao_comparados_separadamente():
    ruler = [_item("Log", "FIRST", content=LOG), _item("Log", "SECOND", content=LOG)]
    flow = [_item("Log", "FIRST", content=LOG)]
    findings = compare(flow, ruler, "raiz")
    assert len(findings) == 1 and "Log" in findings[0].message


# --- oracle contra o estado real congelado ---------------------------------


def _achados_da_417():
    ruler = json.loads((FIXTURES / "regua-414.json").read_text(encoding="utf-8"))[
        "interceptors"
    ]
    rev = json.loads((FIXTURES / "api-417-rev2.json").read_text(encoding="utf-8"))[
        "revision"
    ]
    root = composed_flow(rev.get("interceptors"))
    output = {"raiz da revision": compare(root, ruler, "raiz da revision")}
    for resource in rev.get("resources") or []:
        effective = composed_flow(resource.get("interceptors"), root)
        output[f"resource {resource.get('name')}"] = compare(
            effective, ruler, f"resource {resource.get('name')}"
        )
        for op in resource.get("operations") or []:
            label = f"{op.get('method')} {op.get('path')}"
            output[label] = compare(
                composed_flow(op.get("interceptors"), effective), ruler, label
            )
    return output


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_oracle_a_raiz_diverge_da_regua_em_exatamente_um_custom():
    """A deriva real: a régua pede `Custom#125`, a 417 executa `#32`."""
    findings = _achados_da_417()["raiz da revision"]
    assert len(findings) == 2
    # A régua pede #33, a revisão 9175 ainda executa #178 — o MESMO interceptor
    # sob dois ids, o que só fica visível porque o rótulo traz o nome (V-11 §5).
    missing = next(a for a in findings if a.severity == SEVERITY_WARNING)
    alem = next(a for a in findings if a.severity == SEVERITY_INFO)
    assert "Custom #33" in missing.message
    assert "Custom #178" in alem.message
    assert "CyberArk and OAuth Autentication" in missing.message
    assert "CyberArk and OAuth Autentication" in alem.message


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_oracle_supressao_do_tombstone_aparece_na_conformidade():
    """V-11 §3, achado do `GET /tarefas`: tombstone removendo o XSS."""
    findings = _achados_da_417()["GET /tarefas"]
    assert any(
        "XSS threat protection" in a.message and a.severity == SEVERITY_WARNING
        for a in findings
    )


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_oracle_append_de_additional_info_no_recurso_de_atribuicao():
    """V-11 §3: append de `Additional Info` (SECOND) — INFO."""
    findings = _achados_da_417()["resource Atribuicao Responsavel"]
    assert any(
        "Additional Info" in a.message and a.severity == SEVERITY_INFO
        for a in findings
    )


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_oracle_log_proprio_da_rota_executa_depois_do_herdado():
    """O `Log` com `encryptContent: true` da rota não substitui o `Log` da raiz:
    roda depois do herdado (V-28), e aparece como acréscimo, não como alteração."""
    findings = _achados_da_417()["POST /tarefas/{id}/atribuicao-responsavel"]
    assert not any("encryptContent" in a.message for a in findings)
    assert findings[-1].severity == SEVERITY_INFO and '"Log"' in findings[-1].message


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_oracle_copia_do_health_check_nao_tira_o_custom_178():
    """A rota reproduz o fluxo sem marcar nada: segue executando a raiz inteira,
    `Custom #178` incluído, e a cópia roda de novo depois (V-28 §6)."""
    mensagens = [a.message for a in _achados_da_417()["GET /health-check"]]
    assert any("Custom #178" in m for m in mensagens)
    assert sum('"Log" não existe na template' in m for m in mensagens) == 3


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_oracle_conjunto_congelado_do_estado_de_2026_10_15():
    """Trava o conjunto inteiro: qualquer mudança de regra aparece aqui.

    Composto como o Manager executa (V-28): as cópias do herdado no
    `/health-check` e no `Atribuicao Responsavel` rodam de novo e contam como
    acréscimo."""
    all_resources = [a for listing in _achados_da_417().values() for a in listing]
    assert len(all_resources) == 60
    assert sum(1 for a in all_resources if a.severity == SEVERITY_WARNING) == 13
    assert sum(1 for a in all_resources if a.severity == SEVERITY_INFO) == 47


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_nenhum_achado_bloqueia():
    """V-11 §3: nenhum deles impede a publicação."""
    for listing in _achados_da_417().values():
        for finding in listing:
            assert finding.severity in (SEVERITY_INFO, SEVERITY_WARNING)


# --- rótulo legível (V-11 §5) ----------------------------------------------


def test_rotulo_de_custom_traz_o_nome():
    """O id sozinho não diz nada a quem lê o relatório.

    `Custom #33` e `Custom #178` parecem interceptors diferentes; com o nome,
    vê-se que são o MESMO sob ids distintos — que é a deriva real do tenant.
    """
    ruler = [
        _item("Custom", customInterceptorId=33,
              content='{"id": 33, "name": "CyberArk and OAuth Autentication"}')
    ]
    findings = compare([], ruler, "GET /x")
    assert "Custom #33 — CyberArk and OAuth Autentication" in findings[0].message


def test_rotulo_degrada_para_o_id_quando_o_nome_e_desconhecido():
    ruler = [_item("Custom", customInterceptorId=99)]
    findings = compare([], ruler, "GET /x")
    assert "Custom #99" in findings[0].message


def test_rotulo_de_nativo_e_o_proprio_tipo():
    ruler = [_item("XSS threat protection", content={})]
    findings = compare([], ruler, "GET /x")
    assert '"XSS threat protection"' in findings[0].message


def test_content_ilegivel_nao_quebra_o_rotulo():
    ruler = [_item("Custom", customInterceptorId=7, content="nao e json")]
    findings = compare([], ruler, "GET /x")
    assert "Custom #7" in findings[0].message


# --- item que só mudou de posição -------------------------------------------


def _custom(cid, name):
    return _item("Custom", customInterceptorId=cid,
                 content=json.dumps({"id": cid, "name": name}))


def test_item_que_mudou_de_posicao_vira_um_achado_so():
    """O caso real da 417: o Custom #32 é o 1º na template e o 7º na API.

    Antes saíam dois achados falsos: "não é executado aqui" e "não existe na
    template". O item existe dos dois lados; o que mudou foi a ordem.
    """
    ruler = [_custom(32, "Release Notes"), _item("Log", content=LOG), _custom(33, "CyberArk"),
             _item("Rate limit"), _item("Payload size"), _item("XSS threat protection"),
             _item("Log", content=LOG)]
    effective = [_item("Log", content=LOG), _custom(33, "CyberArk"), _item("Rate limit"),
               _item("Payload size"), _item("XSS threat protection"), _item("Log", content=LOG),
               _custom(32, "Release Notes")]

    findings = compare(effective, ruler, "raiz")

    assert [(a.severity, a.message) for a in findings] == [(
        SEVERITY_WARNING,
        '"Custom #32 — Release Notes" executa em outra posição: na template é o 1º do '
        "request, aqui é o 7º",
    )]


def test_item_movido_com_content_diferente_gera_posicao_e_configuracao():
    ruler = [_item("Payload size", content={"maxSize": 10}), _item("Log", content=LOG)]
    effective = [_item("Log", content=LOG), _item("Payload size", content={"maxSize": 99})]

    mensagens = [a.message for a in compare(effective, ruler, "raiz")]

    assert any("executa em outra posição" in m for m in mensagens)
    assert any("configurado diferente" in m and "maxSize" in m for m in mensagens)
    assert not any("não é executado aqui" in m or "acréscimo" in m for m in mensagens)


def test_ausencia_e_acrescimo_de_verdade_continuam_reportados():
    ruler = [_item("Log", content=LOG), _custom(33, "CyberArk")]
    effective = [_item("Log", content=LOG), _custom(32, "Release Notes")]

    mensagens = [a.message for a in compare(effective, ruler, "raiz")]

    assert any("Custom #33" in m and "não é executado aqui" in m for m in mensagens)
    assert any("Custom #32" in m and "acréscimo" in m for m in mensagens)
    assert not any("outra posição" in m for m in mensagens)


def test_posicao_no_response_nomeia_o_response():
    ruler = [_item("Log", "SECOND", content=LOG), _item("Payload size", "SECOND")]
    effective = [_item("Payload size", "SECOND"), _item("Log", "SECOND", content=LOG)]

    mensagens = [a.message for a in compare(effective, ruler, "raiz")]
    assert any("do response" in m for m in mensagens)
