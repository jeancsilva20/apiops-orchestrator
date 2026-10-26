"""Resposta do `sen deploy` (service → CLI), contrato `apiops.sen-deploy/v1`."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from apiops_orchestrator.domain.models.validate_view import (
    RequiredAttribute,
    ValidateApi,
    ValidateRevision,
    drop_mode_outside_pipeline,
)

SCHEMA_SEN_DEPLOY_V1 = "apiops.sen-deploy/v1"

STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED = "FAILED"


@dataclass(frozen=True)
class DeployEnvironment:
    manager_id: int
    name: Optional[str] = None


@dataclass(frozen=True)
class DeployState:
    """Revisão no ar num ambiente e o registro de deploy correspondente."""

    deployment_id: Optional[int]
    revision_id: Optional[int]
    revision_number: Optional[int] = None
    deployed_at: Optional[str] = None


@dataclass(frozen=True)
class DeployGovernance:
    workflow_id: Optional[int] = None
    stage_id: Optional[int] = None
    deployable_environments: List[int] = field(default_factory=list)
    completeness_required: Optional[float] = None
    completeness_actual: Optional[float] = None
    required: List[RequiredAttribute] = field(default_factory=list)
    missing: List[RequiredAttribute] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return bool(self.violations)


@dataclass(frozen=True)
class DeploymentResult:
    attempted: bool = False
    accepted: bool = False
    deployment_id: Optional[int] = None
    verified: bool = False
    status: str = STATUS_FAILED
    reason: Optional[str] = None


def _attribute(a: RequiredAttribute) -> Dict[str, Any]:
    return {"attributeId": a.attribute_id, "name": a.name, "tagId": a.tag_id}


def _state(s: Optional[DeployState]) -> Optional[Dict[str, Any]]:
    if s is None:
        return None
    return {
        "deploymentId": s.deployment_id,
        "revisionId": s.revision_id,
        "revisionNumber": s.revision_number,
        "deployedAt": s.deployed_at,
    }


@dataclass(frozen=True)
class DeployView:
    """Árvore completa da resposta do `sen deploy`."""

    schema: str
    generated_at: str
    execution_mode: str
    api: ValidateApi
    revision: ValidateRevision
    environment: DeployEnvironment
    governance: DeployGovernance = field(default_factory=DeployGovernance)
    previous_state: Optional[DeployState] = None
    new_state: Optional[DeployState] = None
    deployment: DeploymentResult = field(default_factory=DeploymentResult)
    warnings: List[str] = field(default_factory=list)

    def to_document(self) -> Dict[str, Any]:
        """Árvore do contrato v1, na ordem declarada."""
        gov = self.governance
        return drop_mode_outside_pipeline({
            "schema": self.schema,
            "generatedAt": self.generated_at,
            "executionMode": self.execution_mode,
            "api": {
                "managerId": self.api.manager_id,
                "name": self.api.name,
                "version": self.api.version,
                "basePath": self.api.base_path,
            },
            "revision": {
                "managerId": self.revision.manager_id,
                "revisionNumber": self.revision.revision_number,
            },
            "environment": {
                "managerId": self.environment.manager_id,
                "name": self.environment.name,
            },
            "governance": {
                "workflowId": gov.workflow_id,
                "stageId": gov.stage_id,
                "deployableEnvironments": list(gov.deployable_environments),
                "completeness": {
                    "required": gov.completeness_required,
                    "actual": gov.completeness_actual,
                },
                "required": [_attribute(r) for r in gov.required],
                "missing": [_attribute(m) for m in gov.missing],
                "violations": list(gov.violations),
                "blocked": gov.blocked,
            },
            "previousState": _state(self.previous_state),
            "newState": _state(self.new_state),
            "deployment": {
                "attempted": self.deployment.attempted,
                "accepted": self.deployment.accepted,
                "deploymentId": self.deployment.deployment_id,
                "verified": self.deployment.verified,
                "status": self.deployment.status,
                "reason": self.deployment.reason,
            },
            "warnings": list(self.warnings),
        })
