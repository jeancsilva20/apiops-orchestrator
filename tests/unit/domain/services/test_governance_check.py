"""Requisitos de stage contra uma revisão: maturidade, interceptors, atributos, ambientes."""

from apiops_orchestrator.domain.services import governance_check as gov


def _item(id_, point, kind, position=0, status="REFERENCE", **extra):
    return {
        "id": id_,
        "position": position,
        "executionPoint": point,
        "type": kind,
        "status": status,
        "parent": None,
        **extra,
    }


def _revision():
    return {
        "id": 8948,
        "revisionNumber": 4,
        "workflowId": 327,
        "workflowStageId": 783,
        "interceptors": [
            _item(1, "FIRST", "Transaction ID", 0),
            _item(2, "FIRST", "OAuth", 1),
            _item(3, "SECOND", "Log", 2),
        ],
        "resources": [
            {
                "id": 10,
                "name": "Token",
                "interceptors": [_item(20, "FIRST", "OAuth", 0, status="REMOVED", parent={"id": 2})],
                "operations": [
                    {"id": 11, "method": "POST", "path": "/a", "interceptors": [_item(30, "FIRST", "Mock", 0)]},
                    {"id": 12, "method": "GET", "path": "/b", "interceptors": []},
                ],
            }
        ],
    }


def _requisite(kind, flow="API", point="FIRST", position="ANY", must=True, **extra):
    return {
        "interceptorType": kind,
        "mustHave": must,
        "executionPoint": point,
        "positionType": position,
        "flowType": flow,
        **extra,
    }


def _workflow():
    return {
        "workflowId": 327,
        "stages": [
            {"workflowStageId": 785, "workflowStageName": "Prod", "position": 3},
            {"workflowStageId": 783, "workflowStageName": "Sandbox", "position": 1},
            {"workflowStageId": 784, "workflowStageName": "Dev-Uat", "position": 2},
        ],
    }


def test_stage_navigation_is_by_position():
    workflow = _workflow()
    assert [s["workflowStageId"] for s in gov.ordered_stages(workflow)] == [783, 784, 785]
    assert gov.find_stage(workflow, 784)["workflowStageName"] == "Dev-Uat"
    assert gov.find_stage(workflow, 1) is None
    assert gov.next_stage(workflow, 783)["workflowStageId"] == 784
    assert gov.next_stage(workflow, 785) is None
    assert gov.next_stage(workflow, 999) is None


def test_interceptor_requisites_against_effective_flows():
    stage = {
        "interceptorsRequisites": [
            _requisite("Transaction ID", position="FIRST"),  # primeiro do request da raiz: ok
            _requisite("OAuth"),  # na raiz: ok
            _requisite("OAuth", flow="RESOURCE"),  # o recurso removeu o OAuth herdado: falha
            _requisite("Mock", flow="OPERATION"),  # só POST /a tem Mock: falha em GET /b
            _requisite("Mock", flow="OPERATION", operationId=11),  # só a operação 11: ok
            _requisite("Log", point="SECOND", position="LAST"),  # único no response: ok
            _requisite("Rate limit", must=False),  # não pode ter, e não tem: ok
            _requisite("OAuth", must=False),  # não pode ter, mas tem: falha
            _requisite("Log", point="SECOND", flow="RESOURCE", resourceId=999),  # escopo inexistente
        ]
    }
    verdicts = gov.evaluate_interceptors(stage, _revision())
    statuses = [(v.status, v.failing_scopes) for v in verdicts]
    assert statuses == [
        ("ok", []),
        ("ok", []),
        ("fail", ["token"]),
        ("fail", ["GET /b"]),
        ("ok", []),
        ("ok", []),
        ("ok", []),
        ("fail", ["all"]),
        ("unknown", []),
    ]
    assert verdicts[0].requirement == "deve ter Transaction ID no request como primeiro na raiz da API"
    assert verdicts[3].requirement == "deve ter Mock no request em cada operação"
    assert verdicts[6].requirement.startswith("não pode ter Rate limit")


def test_position_first_fails_when_another_type_comes_first():
    stage = {"interceptorsRequisites": [_requisite("OAuth", position="FIRST")]}
    (verdict,) = gov.evaluate_interceptors(stage, _revision())
    assert verdict.status == "fail" and verdict.failing_scopes == ["all"]


def test_maturity_requirement():
    assert gov.evaluate_maturity({"completenessRequisite": 0.0}, 10.0) is None
    assert gov.evaluate_maturity({"completenessRequisite": None}, 10.0) is None
    ok = gov.evaluate_maturity({"completenessRequisite": 60}, 77.5)
    assert ok.status == "ok" and ok.requirement == "maturidade (completeness) ≥ 60%"
    assert gov.evaluate_maturity({"completenessRequisite": 80}, 77.5).status == "fail"
    unknown = gov.evaluate_maturity({"completenessRequisite": 80}, None)
    assert unknown.status == "unknown"


def test_attribute_requirements_use_present_ids_and_names():
    stage = {
        "attributesRequisites": [
            {"attributeId": 149, "mustHave": True},
            {"attributeId": 231, "mustHave": True},
            {"attributeId": 96, "mustHave": False},
        ]
    }
    verdicts = gov.evaluate_attributes(stage, present_attribute_ids={149, 96}, attributes_by_id={149: "My new"})
    assert [(v.status, v.requirement) for v in verdicts] == [
        ("ok", "deve declarar o atributo My new"),
        ("fail", "deve declarar o atributo atributo 231"),
        ("fail", "não pode declarar o atributo atributo 96"),
    ]


def test_environment_requirements():
    stage = {
        "deployableEnvironments": [9],
        "environments": [
            {"id": 9, "mandatoryDeployment": "MUST_HAVE"},
            {"id": 1, "mandatoryDeployment": "MUST_NOT_HAVE"},
            {"id": 7, "mandatoryDeployment": None},
        ],
    }
    verdicts = gov.evaluate_environments(stage, deployed_env_ids=[1], environments_by_id={1: "Default", 9: "HMG"})
    assert [(v.status, v.requirement) for v in verdicts] == [
        ("fail", "deve estar no ar em HMG (9)"),
        ("fail", "não pode estar no ar em Default (1)"),
        ("fail", "deploy só nos ambientes permitidos pelo stage"),
    ]
    assert "Default (1)" in verdicts[2].detail

    assert gov.evaluate_environments(stage, deployed_env_ids=[9], environments_by_id={}) == [
        gov.Verdict("environment", "ok", "deve estar no ar em 9", "no ar"),
        gov.Verdict("environment", "ok", "não pode estar no ar em 1", "não está no ar"),
    ]


def test_describe_requisites_resolves_names_and_summarize():
    stage = {
        "workflowStageId": 783,
        "workflowStageName": "Sandbox",
        "position": 1,
        "completenessRequisite": 60.0,
        "interceptorsRequisites": [_requisite("Mock", flow="OPERATION")],
        "attributesRequisites": [{"attributeId": 149, "tagId": None, "mustHave": True}],
        "deployableEnvironments": [1],
        "environments": [{"id": 1, "deployableApiManager": True, "mandatoryDeployment": None}],
    }
    described = gov.describe_requisites(stage, {149: "My new"}, {1: "Default"})
    assert described["maturityRequired"] == 60.0
    assert described["interceptors"][0]["description"] == "deve ter Mock no request em cada operação"
    assert described["attributes"] == [{"attributeId": 149, "name": "My new", "tagId": None, "mustHave": True}]
    assert described["deployableEnvironments"] == [{"id": 1, "name": "Default"}]
    assert described["environments"][0]["name"] == "Default"

    verdicts = [
        gov.Verdict("x", "ok", "a"),
        gov.Verdict("x", "unknown", "b"),
    ]
    assert gov.summarize(verdicts) == {"overall": "unknown", "ok": 1, "fail": 0, "unknown": 1, "total": 2}
    assert gov.summarize([])["overall"] == "ok"
    assert gov.summarize(verdicts + [gov.Verdict("x", "fail", "c")])["overall"] == "fail"
