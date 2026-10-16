"""Pré-check do Adaptive Governance (V-23 §4 · D-020)."""

import pytest

from apiops_orchestrator.application.services.governance_precheck_service import (
    GovernancePrecheckService,
)

# Catálogo e workflow espelham o estado real lido em 2026-10-15.
CATALOGO = [
    {"id": 96, "name": "CLI", "inUse": False},
    {"id": 149, "name": "My new", "inUse": True},
    {"id": 146, "name": "Teste", "inUse": False},
    {"id": 231, "name": "teste giroto", "inUse": True},
]

WORKFLOW_500 = {
    "workflowId": 500,
    "workflowName": "APiOps",
    "stages": [
        {"workflowStageId": 1401, "workflowStageName": "Stage One", "attributesRequisites": []},
        {
            "workflowStageId": 1402,
            "workflowStageName": "Teste",
            "attributesRequisites": [
                {"attributeId": 149, "tagId": None, "mustHave": True},
                {"attributeId": 231, "tagId": None, "mustHave": True},
            ],
        },
    ],
}

REVISAO = {"id": 9161, "workflowId": 500, "workflowStageId": 1402}


class ManagerFake:
    def __init__(self, workflow=None, atributos=None):
        self._workflow = workflow if workflow is not None else WORKFLOW_500
        self._atributos = atributos if atributos is not None else CATALOGO
        self.chamadas = []

    def get_workflow(self, workflow_id):
        self.chamadas.append(("get_workflow", workflow_id))
        return self._workflow

    def list_attributes(self):
        self.chamadas.append(("list_attributes", None))
        return self._atributos


def _tags(*nomes):
    return [{"attributeName": n, "tags": []} for n in nomes]


def test_todos_os_exigidos_presentes_nao_bloqueia():
    r = GovernancePrecheckService(ManagerFake()).avaliar(
        REVISAO, _tags("My new", "teste giroto")
    )
    assert not r.bloqueado
    assert {e.attribute_id for e in r.exigidos} == {149, 231}
    assert r.faltantes == []


def test_atributo_faltante_e_calculado_e_nomeado():
    """O T03 do caderno: removida a tag `My new`, falta exatamente 149."""
    r = GovernancePrecheckService(ManagerFake()).avaliar(REVISAO, _tags("teste giroto"))
    assert r.bloqueado
    assert [f.attribute_id for f in r.faltantes] == [149]
    assert r.faltantes[0].name == "My new"


def test_par_workflow_stage_vem_da_revisao():
    """D-020: lido em runtime, nunca configurado."""
    manager = ManagerFake()
    r = GovernancePrecheckService(manager).avaliar(REVISAO, _tags("My new", "teste giroto"))
    assert (r.workflow_id, r.stage_id) == (500, 1402)
    assert ("get_workflow", 500) in manager.chamadas


def test_stage_sem_requisito_nao_bloqueia():
    """Draft parada num stage sem `attributesRequisites`: nada é exigido ali."""
    revisao = dict(REVISAO, workflowStageId=1401)
    r = GovernancePrecheckService(ManagerFake()).avaliar(revisao, [])
    assert not r.bloqueado and r.exigidos == []


def test_requisito_que_muda_entre_execucoes_e_refletido():
    """Config mutável do tenant: o stage 1402 trocou 96 por 231 em 24h."""
    antes = {
        "workflowId": 500,
        "stages": [
            {
                "workflowStageId": 1402,
                "attributesRequisites": [
                    {"attributeId": 149, "mustHave": True},
                    {"attributeId": 96, "mustHave": True},
                ],
            }
        ],
    }
    servico = GovernancePrecheckService(ManagerFake(workflow=antes))
    r = servico.avaliar(REVISAO, _tags("My new", "teste giroto"))
    assert [f.attribute_id for f in r.faltantes] == [96]
    assert r.faltantes[0].name == "CLI"


def test_requisito_sem_must_have_e_ignorado():
    workflow = {
        "stages": [
            {
                "workflowStageId": 1402,
                "attributesRequisites": [{"attributeId": 149, "mustHave": False}],
            }
        ]
    }
    r = GovernancePrecheckService(ManagerFake(workflow=workflow)).avaliar(REVISAO, [])
    assert not r.bloqueado


def test_stage_fora_do_workflow_degrada_com_aviso():
    """A plataforma já exibiu esse estado (V-23 §3): reportar, não assumir."""
    revisao = dict(REVISAO, workflowStageId=420)
    r = GovernancePrecheckService(ManagerFake()).avaliar(revisao, [])
    assert not r.bloqueado
    assert any("não existe no workflow" in a for a in r.avisos)


def test_revisao_sem_workflow_degrada_com_aviso():
    r = GovernancePrecheckService(ManagerFake()).avaliar({"id": 1}, [])
    assert not r.bloqueado
    assert any("não declara" in a for a in r.avisos)


def test_nome_fora_do_catalogo_nao_satisfaz_requisito():
    r = GovernancePrecheckService(ManagerFake()).avaliar(
        REVISAO, _tags("atributo inventado", "My new")
    )
    assert [f.attribute_id for f in r.faltantes] == [231]


def test_api_tags_ausente_deixa_tudo_faltando():
    r = GovernancePrecheckService(ManagerFake()).avaliar(REVISAO, None)
    assert [f.attribute_id for f in r.faltantes] == [149, 231]


def test_nenhuma_mensagem_de_erro_e_parseada():
    """V-23 §4: o faltante sai da subtração, não do texto da plataforma."""
    servico = GovernancePrecheckService(ManagerFake())
    r = servico.avaliar(REVISAO, _tags("teste giroto"))
    # o cálculo não depende de nenhum payload de erro ter sido visto
    assert r.faltantes and r.faltantes[0].name == "My new"
