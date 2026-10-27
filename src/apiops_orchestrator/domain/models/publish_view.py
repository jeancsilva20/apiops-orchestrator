"""Objeto de RESPOSTA do use-case `sen publish` (service → CLI).

Mesma forma do `ValidateView`: dataclass `frozen=True` e um `to_document()` que
emite a árvore do contrato na ordem declarada. Reusa as peças de identidade,
governança e publicação do `validate`, porque descrevem a mesma escrita.

Contrato: `apiops.sen-publish/v1`.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from apiops_orchestrator.domain.models.deploy_model import DeployEnvironment
from apiops_orchestrator.domain.models.validate_view import (
    DocumentationResult,
    RequiredAttribute,
    GovernanceResult,
    PublicationResult,
    ValidateApi,
    ValidateRevision,
    drop_mode_outside_pipeline,
)

SCHEMA_SEN_PUBLISH_V1 = "apiops.sen-publish/v1"


@dataclass(frozen=True)
class RevisionDeployment:
    """Ambiente em que a revisão alvo está no ar."""

    deployment_id: Optional[int]
    environment: DeployEnvironment
    deployed_at: Optional[str] = None


def _attribute(a: RequiredAttribute) -> Dict[str, Any]:
    return {"attributeId": a.attribute_id, "name": a.name, "tagId": a.tag_id}


def _deployment(d: RevisionDeployment) -> Dict[str, Any]:
    return {
        "deploymentId": d.deployment_id,
        "environment": {
            "managerId": d.environment.manager_id,
            "name": d.environment.name,
        },
        "deployedAt": d.deployed_at,
    }


@dataclass(frozen=True)
class PublishView:
    """Árvore completa da resposta do `sen publish`."""

    schema: str
    generated_at: str
    execution_mode: str
    api: ValidateApi
    revision: ValidateRevision
    governance: GovernanceResult = field(default_factory=GovernanceResult)
    publication: PublicationResult = field(default_factory=PublicationResult)
    documentation: DocumentationResult = field(default_factory=DocumentationResult)
    # Avisos da montagem do payload e do pré-check: dizem o que vai mudar na
    # plataforma, ou quando o veredito da governança ficou para a gravação.
    warnings: List[str] = field(default_factory=list)
    deployments: List[RevisionDeployment] = field(default_factory=list)

    def to_document(self) -> Dict[str, Any]:
        """Árvore do contrato v1, na ordem declarada — sem token e sem wire cru."""
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
                "deployments": [_deployment(d) for d in self.deployments],
            },
            "governance": {
                "workflowId": self.governance.workflow_id,
                "stageId": self.governance.stage_id,
                "required": [_attribute(r) for r in self.governance.required],
                "missing": [_attribute(m) for m in self.governance.missing],
                "blocked": self.governance.blocked,
            },
            "publication": {
                "attempted": self.publication.attempted,
                "accepted": self.publication.accepted,
                "verified": self.publication.verified,
                "divergences": list(self.publication.divergences),
            },
            "documentation": self.documentation.to_document(),
            "warnings": list(self.warnings),
        })
