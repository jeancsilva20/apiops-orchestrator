"""Leitura dos requisitos de um stage do Adaptive Governance contra uma revisão.

Lógica pura: recebe o stage (como vem de `GET /api-governance/.../workflows`), a
revisão crua, o score de completeness e os catálogos do tenant, e devolve o
veredito de cada requisito. Nada aqui escreve nem decide: é o que `sen get
governance` mostra para explicar *por que* uma revisão passa ou não no stage.

Requisitos de um stage (mapeamento AG, doc 04/12/99):

    completenessRequisite    maturidade mínima (0–100), lida de /completeness
    interceptorsRequisites   {interceptorType, mustHave, executionPoint,
                              positionType FIRST|LAST|ANY,
                              flowType API|RESOURCE|OPERATION,
                              resourceType/operationType ALL|…, resourceId, operationId}
    attributesRequisites     {attributeId, tagId, mustHave} — conferido fora daqui
                             (GovernancePrecheckService), porque precisa do catálogo
    environments[]           {id, deployableApiManager, mandatoryDeployment}
    deployableEnvironments   ids dos ambientes onde o stage permite deploy

O fluxo que cada escopo executa vem de `api_navigation.scope_tree`: herdado −
removido + próprio, por ponto de execução.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from apiops_orchestrator.domain.services import api_navigation as nav

STATUS_OK = "ok"
STATUS_FAIL = "fail"
STATUS_UNKNOWN = "unknown"


@dataclass(frozen=True)
class Verdict:
    kind: str  # maturity | interceptor | attribute | environment
    status: str  # ok | fail | unknown
    requirement: str
    detail: str = ""
    failing_scopes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "status": self.status,
            "requirement": self.requirement,
            "detail": self.detail,
            "failingScopes": list(self.failing_scopes),
        }


# --------------------------------------------------------------------------- stage


def find_stage(workflow: Dict[str, Any], stage_id: Any) -> Optional[Dict[str, Any]]:
    for stage in workflow.get("stages") or []:
        if isinstance(stage, dict) and stage.get("workflowStageId") == stage_id:
            return stage
    return None


def ordered_stages(workflow: Dict[str, Any]) -> List[Dict[str, Any]]:
    stages = [s for s in workflow.get("stages") or [] if isinstance(s, dict)]
    return sorted(stages, key=lambda s: (s.get("position") or 0, s.get("workflowStageId") or 0))


def next_stage(workflow: Dict[str, Any], stage_id: Any) -> Optional[Dict[str, Any]]:
    stages = ordered_stages(workflow)
    for index, stage in enumerate(stages):
        if stage.get("workflowStageId") == stage_id:
            return stages[index + 1] if index + 1 < len(stages) else None
    return None


def describe_requisites(
    stage: Dict[str, Any],
    attributes_by_id: Optional[Dict[Any, str]] = None,
    environments_by_id: Optional[Dict[Any, str]] = None,
) -> Dict[str, Any]:
    """Os requisitos de um stage com ids traduzidos para nomes, sem avaliar nada."""
    attributes_by_id = attributes_by_id or {}
    environments_by_id = environments_by_id or {}
    return {
        "id": stage.get("workflowStageId"),
        "name": stage.get("workflowStageName"),
        "position": stage.get("position"),
        "maturityRequired": stage.get("completenessRequisite"),
        "interceptors": [
            {
                "type": r.get("interceptorType"),
                "mustHave": bool(r.get("mustHave")),
                "executionPoint": (r.get("executionPoint") or "").upper() or None,
                "positionType": (r.get("positionType") or "ANY").upper(),
                "flowType": (r.get("flowType") or "API").upper(),
                "resourceId": r.get("resourceId"),
                "operationId": r.get("operationId"),
                "description": _interceptor_requirement_text(r),
            }
            for r in stage.get("interceptorsRequisites") or []
            if isinstance(r, dict)
        ],
        "attributes": [
            {
                "attributeId": r.get("attributeId"),
                "name": attributes_by_id.get(r.get("attributeId")),
                "tagId": r.get("tagId"),
                "mustHave": bool(r.get("mustHave")),
            }
            for r in stage.get("attributesRequisites") or []
            if isinstance(r, dict)
        ],
        "deployableEnvironments": [
            {"id": env_id, "name": environments_by_id.get(env_id)}
            for env_id in stage.get("deployableEnvironments") or []
        ],
        "environments": [
            {
                "id": e.get("id"),
                "name": environments_by_id.get(e.get("id")),
                "mandatoryDeployment": e.get("mandatoryDeployment"),
                "deployableApiManager": e.get("deployableApiManager"),
            }
            for e in stage.get("environments") or []
            if isinstance(e, dict)
        ],
    }


def _interceptor_requirement_text(requisite: Dict[str, Any]) -> str:
    kind = requisite.get("interceptorType")
    must = "deve ter" if requisite.get("mustHave") else "não pode ter"
    point = {"FIRST": "request", "SECOND": "response"}.get(
        (requisite.get("executionPoint") or "").upper(), requisite.get("executionPoint") or "?"
    )
    position = (requisite.get("positionType") or "ANY").upper()
    where = {
        "API": "na raiz da API",
        "RESOURCE": "em cada recurso",
        "OPERATION": "em cada operação",
    }.get((requisite.get("flowType") or "API").upper(), str(requisite.get("flowType")))
    if requisite.get("resourceId"):
        where = f"no recurso {requisite['resourceId']}"
    if requisite.get("operationId"):
        where = f"na operação {requisite['operationId']}"
    order = {"FIRST": " como primeiro", "LAST": " como último"}.get(position, "")
    return f"{must} {kind} no {point}{order} {where}"


# --------------------------------------------------------------------------- avaliação


def _scopes_for(tree: nav.Scope, requisite: Dict[str, Any]) -> List[nav.Scope]:
    flow = (requisite.get("flowType") or "API").upper()
    if flow == "RESOURCE":
        scopes = [s for s in tree.children if s.kind == "resource"]
        wanted = requisite.get("resourceId")
        return [s for s in scopes if wanted in (None, s.raw.get("id"))]
    if flow == "OPERATION":
        scopes = [op for r in tree.children for op in r.children if op.kind == "operation"]
        wanted = requisite.get("operationId")
        return [s for s in scopes if wanted in (None, s.raw.get("id"))]
    return [tree]


def _satisfied(scope: nav.Scope, requisite: Dict[str, Any]) -> bool:
    """O escopo tem (ou não tem) o tipo exigido, na posição exigida, no ponto exigido."""
    kind = str(requisite.get("interceptorType") or "")
    point = (requisite.get("executionPoint") or "").upper()
    at_point = [
        i
        for i in scope.effective
        if not point or (i.get("executionPoint") or "").upper() == point
    ]
    matches = [i for i in at_point if str(i.get("type") or "") == kind]
    present = bool(matches)
    if not requisite.get("mustHave"):
        return not present
    if not present:
        return False
    position = (requisite.get("positionType") or "ANY").upper()
    if position == "FIRST":
        return at_point[0] is matches[0]
    if position == "LAST":
        return at_point[-1] is matches[-1]
    return True


def evaluate_interceptors(
    stage: Dict[str, Any], revision: Dict[str, Any]
) -> List[Verdict]:
    tree = nav.scope_tree(revision)
    verdicts: List[Verdict] = []
    for requisite in stage.get("interceptorsRequisites") or []:
        if not isinstance(requisite, dict):
            continue
        scopes = _scopes_for(tree, requisite)
        failing = [s.key for s in scopes if not _satisfied(s, requisite)]
        if not scopes:
            status, detail = STATUS_UNKNOWN, "nenhum escopo deste tipo na revisão"
        elif failing:
            status, detail = STATUS_FAIL, f"não atendido em {len(failing)} de {len(scopes)} escopo(s)"
        else:
            status, detail = STATUS_OK, f"atendido em {len(scopes)} escopo(s)"
        verdicts.append(
            Verdict(
                kind="interceptor",
                status=status,
                requirement=_interceptor_requirement_text(requisite),
                detail=detail,
                failing_scopes=failing,
            )
        )
    return verdicts


def evaluate_maturity(stage: Dict[str, Any], score: Optional[float]) -> Optional[Verdict]:
    required = stage.get("completenessRequisite")
    try:
        required = float(required) if required is not None else 0.0
    except (TypeError, ValueError):
        required = 0.0
    if required <= 0:
        return None
    requirement = f"maturidade (completeness) ≥ {required:g}%"
    if score is None:
        return Verdict("maturity", STATUS_UNKNOWN, requirement, "o Manager não respondeu o completeness")
    status = STATUS_OK if score >= required else STATUS_FAIL
    return Verdict("maturity", status, requirement, f"revisão está em {score:g}%")


def evaluate_environments(
    stage: Dict[str, Any],
    deployed_env_ids: Sequence[Any],
    environments_by_id: Optional[Dict[Any, str]] = None,
) -> List[Verdict]:
    """Deploy obrigatório/proibido por ambiente, e deploy fora dos permitidos."""
    environments_by_id = environments_by_id or {}
    deployed = {e for e in deployed_env_ids}
    verdicts: List[Verdict] = []

    def name(env_id: Any) -> str:
        label = environments_by_id.get(env_id)
        return f"{label} ({env_id})" if label else str(env_id)

    for env in stage.get("environments") or []:
        if not isinstance(env, dict) or not env.get("mandatoryDeployment"):
            continue
        rule = str(env["mandatoryDeployment"]).upper()
        env_id = env.get("id")
        is_deployed = env_id in deployed
        if "NOT" in rule:
            status = STATUS_FAIL if is_deployed else STATUS_OK
            requirement = f"não pode estar no ar em {name(env_id)}"
        else:
            status = STATUS_OK if is_deployed else STATUS_FAIL
            requirement = f"deve estar no ar em {name(env_id)}"
        verdicts.append(
            Verdict(
                "environment",
                status,
                requirement,
                "no ar" if is_deployed else "não está no ar",
            )
        )

    allowed = stage.get("deployableEnvironments")
    if isinstance(allowed, list):
        outside = sorted(deployed - set(allowed), key=str)
        if outside:
            verdicts.append(
                Verdict(
                    "environment",
                    STATUS_FAIL,
                    "deploy só nos ambientes permitidos pelo stage",
                    "no ar fora do permitido: " + ", ".join(name(e) for e in outside),
                )
            )
    return verdicts


def evaluate_attributes(
    stage: Dict[str, Any],
    present_attribute_ids: Sequence[Any],
    attributes_by_id: Optional[Dict[Any, str]] = None,
) -> List[Verdict]:
    """Atributos exigidos/proibidos contra os que a API declara de forma válida.

    `present_attribute_ids` vem do pré-check (mesma regra do publish: atributo
    com tags cadastradas só conta se declarar ao menos uma).
    """
    attributes_by_id = attributes_by_id or {}
    present = set(present_attribute_ids)
    verdicts: List[Verdict] = []
    for requisite in stage.get("attributesRequisites") or []:
        if not isinstance(requisite, dict):
            continue
        attribute_id = requisite.get("attributeId")
        label = attributes_by_id.get(attribute_id) or f"atributo {attribute_id}"
        has = attribute_id in present
        if requisite.get("mustHave"):
            status = STATUS_OK if has else STATUS_FAIL
            requirement = f"deve declarar o atributo {label}"
        else:
            status = STATUS_FAIL if has else STATUS_OK
            requirement = f"não pode declarar o atributo {label}"
        verdicts.append(
            Verdict("attribute", status, requirement, "declarado" if has else "não declarado")
        )
    return verdicts


def summarize(verdicts: Sequence[Verdict]) -> Dict[str, Any]:
    counts = {STATUS_OK: 0, STATUS_FAIL: 0, STATUS_UNKNOWN: 0}
    for verdict in verdicts:
        counts[verdict.status] = counts.get(verdict.status, 0) + 1
    if counts[STATUS_FAIL]:
        overall = STATUS_FAIL
    elif counts[STATUS_UNKNOWN]:
        overall = STATUS_UNKNOWN
    else:
        overall = STATUS_OK
    return {"overall": overall, **counts, "total": len(verdicts)}
