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
    AtributoExigido,
    GovernancaResultado,
    PublicacaoResultado,
    ValidateApi,
    ValidateRevision,
    sem_modo_fora_da_esteira,
)

SCHEMA_SEN_PUBLISH_V1 = "apiops.sen-publish/v1"


@dataclass(frozen=True)
class RevisionDeployment:
    """Ambiente em que a revisão alvo está no ar."""

    deployment_id: Optional[int]
    environment: DeployEnvironment
    deployed_at: Optional[str] = None


def _atributo(a: AtributoExigido) -> Dict[str, Any]:
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
    governanca: GovernancaResultado = field(default_factory=GovernancaResultado)
    publicacao: PublicacaoResultado = field(default_factory=PublicacaoResultado)
    # Avisos da montagem do payload e do pré-check: dizem o que vai mudar na
    # plataforma, ou quando o veredito da governança ficou para a gravação.
    avisos: List[str] = field(default_factory=list)
    deployments: List[RevisionDeployment] = field(default_factory=list)

    def to_document(self) -> Dict[str, Any]:
        """Árvore do contrato v1, na ordem declarada — sem token e sem wire cru."""
        return sem_modo_fora_da_esteira({
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
                "workflowId": self.governanca.workflow_id,
                "stageId": self.governanca.stage_id,
                "required": [_atributo(r) for r in self.governanca.required],
                "missing": [_atributo(m) for m in self.governanca.missing],
                "blocked": self.governanca.blocked,
            },
            "publication": {
                "attempted": self.publicacao.attempted,
                "accepted": self.publicacao.accepted,
                "verified": self.publicacao.verified,
                "divergences": list(self.publicacao.divergences),
            },
            "warnings": list(self.avisos),
        })
