"""Pré-check do Adaptive Governance (V-23 §4 · D-020)."""

import pytest

from apiops_orchestrator.application.services.governance_precheck_service import (
    ATTRIBUTE_WITHOUT_CATALOG_TAGS,
    INVALID_TAG,
    MISSING_TAG,
    UNKNOWN_ATTRIBUTE,
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
        self._attributes = atributos if atributos is not None else CATALOGO
        self.chamadas = []

    def get_workflow(self, workflow_id):
        self.chamadas.append(("get_workflow", workflow_id))
        return self._workflow

    def list_attributes(self):
        self.chamadas.append(("list_attributes", None))
        return self._attributes


def _tags(*names):
    return [{"attributeName": n, "tags": []} for n in names]


def test_todos_os_exigidos_presentes_nao_bloqueia():
    r = GovernancePrecheckService(ManagerFake()).evaluate(
        REVISAO, _tags("My new", "teste giroto")
    )
    assert not r.blocked
    assert {e.attribute_id for e in r.required} == {149, 231}
    assert r.missing_names == []


def test_atributo_faltante_e_calculado_e_nomeado():
    """O T03 do caderno: removida a tag `My new`, falta exatamente 149."""
    r = GovernancePrecheckService(ManagerFake()).evaluate(REVISAO, _tags("teste giroto"))
    assert r.blocked
    assert [f.attribute_id for f in r.missing_names] == [149]
    assert r.missing_names[0].name == "My new"


def test_par_workflow_stage_vem_da_revisao():
    """D-020: lido em runtime, nunca configurado."""
    manager = ManagerFake()
    r = GovernancePrecheckService(manager).evaluate(REVISAO, _tags("My new", "teste giroto"))
    assert (r.workflow_id, r.stage_id) == (500, 1402)
    assert ("get_workflow", 500) in manager.chamadas


def test_stage_sem_requisito_nao_bloqueia():
    """Draft parada num stage sem `attributesRequisites`: nada é exigido ali."""
    revision = dict(REVISAO, workflowStageId=1401)
    r = GovernancePrecheckService(ManagerFake()).evaluate(revision, [])
    assert not r.blocked and r.required == []


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
    r = servico.evaluate(REVISAO, _tags("My new", "teste giroto"))
    assert [f.attribute_id for f in r.missing_names] == [96]
    assert r.missing_names[0].name == "CLI"


def test_requisito_sem_must_have_e_ignorado():
    workflow = {
        "stages": [
            {
                "workflowStageId": 1402,
                "attributesRequisites": [{"attributeId": 149, "mustHave": False}],
            }
        ]
    }
    r = GovernancePrecheckService(ManagerFake(workflow=workflow)).evaluate(REVISAO, [])
    assert not r.blocked


def test_stage_fora_do_workflow_degrada_com_aviso():
    """A plataforma já exibiu esse estado (V-23 §3): reportar, não assumir."""
    revision = dict(REVISAO, workflowStageId=420)
    r = GovernancePrecheckService(ManagerFake()).evaluate(revision, [])
    assert not r.blocked
    assert any("não existe no workflow" in a for a in r.warnings)


def test_revisao_sem_workflow_degrada_com_aviso():
    r = GovernancePrecheckService(ManagerFake()).evaluate({"id": 1}, [])
    assert not r.blocked
    assert any("não declara" in a for a in r.warnings)


def test_nome_fora_do_catalogo_nao_satisfaz_requisito():
    r = GovernancePrecheckService(ManagerFake()).evaluate(
        REVISAO, _tags("atributo inventado", "My new")
    )
    assert [f.attribute_id for f in r.missing_names] == [231]


def test_api_tags_ausente_deixa_tudo_faltando():
    r = GovernancePrecheckService(ManagerFake()).evaluate(REVISAO, None)
    assert [f.attribute_id for f in r.missing_names] == [149, 231]


def test_nenhuma_mensagem_de_erro_e_parseada():
    """V-23 §4: o faltante sai da subtração, não do texto da plataforma."""
    servico = GovernancePrecheckService(ManagerFake())
    r = servico.evaluate(REVISAO, _tags("teste giroto"))
    # o cálculo não depende de nenhum payload de erro ter sido visto
    assert r.missing_names and r.missing_names[0].name == "My new"


# --- Regras de apiTags observadas na plataforma -----------------------------

# Catálogo com as tags cadastradas, como devolvido pelo consulting.
CATALOGO_COM_TAGS = [
    {"id": 96, "name": "CLI", "tags": [], "inUse": False},
    {"id": 149, "name": "My new", "tags": ["Tag1", "Tag2"], "inUse": True},
    {"id": 231, "name": "teste giroto", "tags": ["teste giroto"], "inUse": True},
]


def _declarado(name, *tags):
    return {"attributeName": name, "tags": list(tags)}


def _servico_com_tags(workflow=None):
    return GovernancePrecheckService(
        ManagerFake(workflow=workflow, atributos=CATALOGO_COM_TAGS)
    )


def test_atributo_com_tag_valida_conta_como_presente():
    r = _servico_com_tags().evaluate(
        REVISAO, [_declarado("My new", "Tag1"), _declarado("teste giroto", "teste giroto")]
    )
    assert not r.blocked
    assert r.api_tag_problems == []


def test_atributo_sem_tag_conta_como_ausente_e_e_problema():
    """Cenário A: `My new` com `tags: []` — a plataforma respondeu 412."""
    r = _servico_com_tags().evaluate(
        REVISAO, [_declarado("My new"), _declarado("teste giroto", "teste giroto")]
    )
    assert r.blocked
    assert [f.attribute_id for f in r.missing_names] == [149]
    assert [(p.kind, p.attribute_name, p.valid) for p in r.api_tag_problems] == [
        (MISSING_TAG, "My new", ["Tag1", "Tag2"])
    ]


def test_atributo_sem_a_chave_tags_e_problema():
    r = _servico_com_tags().evaluate(REVISAO, [{"attributeName": "My new"}])
    assert [p.kind for p in r.api_tag_problems] == [MISSING_TAG]


def test_tag_fora_da_lista_do_atributo_e_invalida():
    """Tag inexistente: a plataforma aceitou com 200 e apagou todas as apiTags."""
    r = _servico_com_tags().evaluate(
        REVISAO,
        [_declarado("My new", "TagInexistente"), _declarado("teste giroto", "teste giroto")],
    )
    assert len(r.api_tag_problems) == 1
    invalida = r.api_tag_problems[0]
    assert invalida.kind == INVALID_TAG
    assert (invalida.attribute_name, invalida.tag) == ("My new", "TagInexistente")
    assert invalida.valid == ["Tag1", "Tag2"]


def test_cada_tag_fora_da_lista_e_um_problema():
    r = _servico_com_tags().evaluate(REVISAO, [_declarado("My new", "Tag1", "X", "Y")])
    assert [p.tag for p in r.api_tag_problems] == ["X", "Y"]


def test_tag_invalida_e_conferida_mesmo_sem_requisito_no_stage():
    workflow = {"stages": [{"workflowStageId": 1402, "attributesRequisites": []}]}
    r = _servico_com_tags(workflow).evaluate(REVISAO, [_declarado("My new", "Errada")])
    assert [i.tag for i in r.api_tag_problems] == ["Errada"]


def test_tag_invalida_e_conferida_mesmo_sem_workflow_na_revisao():
    r = _servico_com_tags().evaluate({"id": 1}, [_declarado("My new", "Errada")])
    assert [i.tag for i in r.api_tag_problems] == ["Errada"]


@pytest.mark.parametrize("tags", [(), ("Sensedia",), ("a", "b")])
def test_atributo_sem_tags_cadastradas_e_um_problema_so(tags):
    r = _servico_com_tags().evaluate(REVISAO, [_declarado("CLI", *tags)])
    assert [(p.kind, p.attribute_name) for p in r.api_tag_problems] == [
        (ATTRIBUTE_WITHOUT_CATALOG_TAGS, "CLI")
    ]


def test_atributo_fora_do_catalogo_e_problema_sem_sugestao():
    r = _servico_com_tags().evaluate(
        REVISAO,
        [_declarado("inventado", "x"), _declarado("My new", "Tag1"),
         _declarado("teste giroto", "teste giroto")],
    )
    assert [(p.kind, p.attribute_name, p.suggestions) for p in r.api_tag_problems] == [
        (UNKNOWN_ATTRIBUTE, "inventado", [])
    ]


CATALOGO_ACENTUADO = [
    {"id": 300, "name": "Domínio", "tags": ["Financeiro"]},
    {"id": 301, "name": "Área", "tags": ["TI"]},
]


@pytest.mark.parametrize(
    "declarado, sugestao",
    [
        ("Dominio", ["Domínio"]),
        ("domínio", ["Domínio"]),
        ("DOMINIO", ["Domínio"]),
        ("area", ["Área"]),
        ("Dominios", []),
        ("Domino", []),
        ("Domínio ", []),
    ],
)
def test_sugestao_so_quando_difere_em_acento_ou_maiuscula(declarado, sugestao):
    servico = GovernancePrecheckService(ManagerFake(atributos=CATALOGO_ACENTUADO))
    r = servico.evaluate(REVISAO, [_declarado(declarado, "Financeiro")])
    assert [(p.kind, p.suggestions) for p in r.api_tag_problems] == [
        (UNKNOWN_ATTRIBUTE, sugestao)
    ]


def test_atributo_e_tags_validos_nao_tem_problema():
    servico = GovernancePrecheckService(ManagerFake(atributos=CATALOGO_ACENTUADO))
    r = servico.evaluate(REVISAO, [_declarado("Domínio", "Financeiro")])
    assert r.api_tag_problems == []


def test_lista_vazia_nao_tem_problema():
    r = _servico_com_tags().evaluate(REVISAO, [])
    assert r.api_tag_problems == []


def test_api_tags_ausente_nao_confere_tags():
    """Ausente preserva (schema do basic info): nada é enviado, nada a conferir."""
    r = _servico_com_tags().evaluate(REVISAO, None)
    assert r.api_tag_problems == []


def test_catalogo_e_lido_uma_vez_por_execucao():
    manager = ManagerFake(atributos=CATALOGO_COM_TAGS)
    GovernancePrecheckService(manager).evaluate(
        REVISAO, [_declarado("My new", "Tag1"), _declarado("teste giroto", "teste giroto")]
    )
    assert manager.chamadas.count(("list_attributes", None)) == 1


# --- stage exposto (usado pelo `sen deploy`) ---------------------------------


@pytest.mark.parametrize("stage_id", [1401, 1402])
def test_stage_encontrado_e_exposto_com_ou_sem_requisito(stage_id):
    revision = dict(REVISAO, workflowStageId=stage_id)
    r = GovernancePrecheckService(ManagerFake()).evaluate(revision, _tags("My new", "teste giroto"))
    assert r.stage["workflowStageId"] == stage_id


@pytest.mark.parametrize("revision", [dict(REVISAO, workflowStageId=420), {"id": 1}])
def test_stage_nao_encontrado_fica_none(revision):
    r = GovernancePrecheckService(ManagerFake()).evaluate(revision, [])
    assert r.stage is None
