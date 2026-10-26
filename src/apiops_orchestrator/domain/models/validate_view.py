"""Objeto de RESPOSTA do use-case `sen validate` (service → CLI).

Espelha a forma do `CompletenessView`: dataclasses `frozen=True` e um
`to_document()` que emite a árvore do contrato na ordem declarada, sem campos
fantasma. A CLI renderiza texto a partir da mesma estrutura, de modo que os três
formatos (`text`, `json`, `yaml`) nunca divergem.

Contrato: `apiops.sen-validate/v1`.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SCHEMA_SEN_VALIDATE_V1 = "apiops.sen-validate/v1"

# Achados que vêm do repositório, não da comparação com a API-template. A
# borda os apresenta à parte: são textos explicativos de várias frases, e
# numa coluna de tabela ficam ilegíveis.
REPOSITORY_SCOPE = "repositório"

SEVERITY_INFO = "INFO"
SEVERITY_WARNING = "WARNING"

PIPELINE_MODE = "pipeline"


def drop_mode_outside_pipeline(document: Dict[str, Any]) -> Dict[str, Any]:
    """Tira `executionMode` do documento quando ele não vem da esteira."""
    if document.get("executionMode") != PIPELINE_MODE:
        document.pop("executionMode", None)
    return document


@dataclass(frozen=True)
class ValidateApi:
    """Identidade da API, ecoada para o consumidor cego de stdout."""

    manager_id: int
    name: Optional[str] = None
    version: Optional[str] = None
    base_path: Optional[str] = None


@dataclass(frozen=True)
class ValidateRevision:
    """Revisão alvo. O número é o que o humano vê na UI; o id é transporte (V-24)."""

    manager_id: int
    revision_number: Optional[int] = None


@dataclass(frozen=True)
class RulerSnapshot:
    """Snapshot da régua usada na comparação (D-4 / P-3).

    Sem ele um achado deixa de ser reproduzível assim que a API-template muda.
    O `flow_hash` identifica o fluxo exato contra o qual se comparou.
    """

    template_id: Optional[int] = None
    revision_number: Optional[int] = None
    flow_hash: Optional[str] = None
    interceptors_count: Optional[int] = None


@dataclass(frozen=True)
class Finding:
    """Um achado de conformidade. Nunca bloqueia: INFO ou WARNING (V-11 §3)."""

    severity: str
    scope: str
    message: str
    interceptor_type: Optional[str] = None
    custom_interceptor_id: Optional[int] = None


@dataclass(frozen=True)
class RequiredAttribute:
    """Atributo exigido pelo stage do Adaptive Governance."""

    attribute_id: int
    name: Optional[str] = None
    tag_id: Optional[int] = None


@dataclass(frozen=True)
class GovernanceResult:
    """Resultado do pré-check. O faltante é CALCULADO, nunca extraído de texto (V-23 §4)."""

    workflow_id: Optional[int] = None
    stage_id: Optional[int] = None
    required: List[RequiredAttribute] = field(default_factory=list)
    missing: List[RequiredAttribute] = field(default_factory=list)
    blocked: bool = False


@dataclass(frozen=True)
class PublicationResult:
    """Resultado da E3 e da conferência da E3.1.

    `accepted` é só o código HTTP. O veredito é `verified`: HTTP 200 não é prova
    de sucesso (W-8).
    """

    attempted: bool = False
    accepted: bool = False
    verified: bool = False
    divergences: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompletenessSummary:
    """Completeness em regime INFORMATIVO no `validate`: nunca bloqueia (decisão 2)."""

    score: Optional[float] = None
    gate_percent: Optional[float] = None
    suggestions: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ValidateView:
    """Árvore completa da resposta do `sen validate`."""

    schema: str
    generated_at: str
    execution_mode: str
    api: ValidateApi
    revision: ValidateRevision
    ruler: RulerSnapshot
    findings: List[Finding] = field(default_factory=list)
    governance: GovernanceResult = field(default_factory=GovernanceResult)
    publication: PublicationResult = field(default_factory=PublicationResult)
    completeness: CompletenessSummary = field(default_factory=CompletenessSummary)

    @property
    def warnings(self) -> List[Finding]:
        return [a for a in self.findings if a.severity == SEVERITY_WARNING]

    @property
    def infos(self) -> List[Finding]:
        return [a for a in self.findings if a.severity == SEVERITY_INFO]

    def to_document(self) -> Dict[str, Any]:
        """Árvore do contrato v1, na ordem declarada.

        Nenhum campo pode carregar token, cookie ou material de credencial, e não
        há dump cru de wire: o consumidor recebe só o que foi decidido expor.
        """
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
            "ruler": {
                "templateId": self.ruler.template_id,
                "revisionNumber": self.ruler.revision_number,
                "flowHash": self.ruler.flow_hash,
                "interceptorsCount": self.ruler.interceptors_count,
            },
            "findings": [
                {
                    "severity": a.severity,
                    "scope": a.scope,
                    "message": a.message,
                    "interceptorType": a.interceptor_type,
                    "customInterceptorId": a.custom_interceptor_id,
                }
                for a in self.findings
            ],
            "governance": {
                "workflowId": self.governance.workflow_id,
                "stageId": self.governance.stage_id,
                "required": [
                    {
                        "attributeId": r.attribute_id,
                        "name": r.name,
                        "tagId": r.tag_id,
                    }
                    for r in self.governance.required
                ],
                "missing": [
                    {
                        "attributeId": m.attribute_id,
                        "name": m.name,
                        "tagId": m.tag_id,
                    }
                    for m in self.governance.missing
                ],
                "blocked": self.governance.blocked,
            },
            "publication": {
                "attempted": self.publication.attempted,
                "accepted": self.publication.accepted,
                "verified": self.publication.verified,
                "divergences": list(self.publication.divergences),
            },
            "completeness": {
                "score": self.completeness.score,
                "gatePercent": self.completeness.gate_percent,
                "suggestions": list(self.completeness.suggestions),
            },
        })
