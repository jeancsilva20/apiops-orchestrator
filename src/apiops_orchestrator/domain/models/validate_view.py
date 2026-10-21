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
ESCOPO_REPOSITORIO = "repositório"

SEVERIDADE_INFO = "INFO"
SEVERIDADE_WARNING = "WARNING"

MODO_ESTEIRA = "pipeline"


def sem_modo_fora_da_esteira(documento: Dict[str, Any]) -> Dict[str, Any]:
    """Tira `executionMode` do documento quando ele não vem da esteira."""
    if documento.get("executionMode") != MODO_ESTEIRA:
        documento.pop("executionMode", None)
    return documento


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
class ReguaSnapshot:
    """Snapshot da régua usada na comparação (D-4 / P-3).

    Sem ele um achado deixa de ser reproduzível assim que a API-template muda.
    O `flow_hash` identifica o fluxo exato contra o qual se comparou.
    """

    template_id: Optional[int] = None
    revision_number: Optional[int] = None
    flow_hash: Optional[str] = None
    interceptors_count: Optional[int] = None


@dataclass(frozen=True)
class Achado:
    """Um achado de conformidade. Nunca bloqueia: INFO ou WARNING (V-11 §3)."""

    severity: str
    scope: str
    message: str
    interceptor_type: Optional[str] = None
    custom_interceptor_id: Optional[int] = None


@dataclass(frozen=True)
class AtributoExigido:
    """Atributo exigido pelo stage do Adaptive Governance."""

    attribute_id: int
    name: Optional[str] = None
    tag_id: Optional[int] = None


@dataclass(frozen=True)
class GovernancaResultado:
    """Resultado do pré-check. O faltante é CALCULADO, nunca extraído de texto (V-23 §4)."""

    workflow_id: Optional[int] = None
    stage_id: Optional[int] = None
    required: List[AtributoExigido] = field(default_factory=list)
    missing: List[AtributoExigido] = field(default_factory=list)
    blocked: bool = False


@dataclass(frozen=True)
class PublicacaoResultado:
    """Resultado da E3 e da conferência da E3.1.

    `accepted` é só o código HTTP. O veredito é `verified`: HTTP 200 não é prova
    de sucesso (W-8).
    """

    attempted: bool = False
    accepted: bool = False
    verified: bool = False
    divergences: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompletenessResumo:
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
    regua: ReguaSnapshot
    achados: List[Achado] = field(default_factory=list)
    governanca: GovernancaResultado = field(default_factory=GovernancaResultado)
    publicacao: PublicacaoResultado = field(default_factory=PublicacaoResultado)
    completeness: CompletenessResumo = field(default_factory=CompletenessResumo)

    @property
    def warnings(self) -> List[Achado]:
        return [a for a in self.achados if a.severity == SEVERIDADE_WARNING]

    @property
    def infos(self) -> List[Achado]:
        return [a for a in self.achados if a.severity == SEVERIDADE_INFO]

    def to_document(self) -> Dict[str, Any]:
        """Árvore do contrato v1, na ordem declarada.

        Nenhum campo pode carregar token, cookie ou material de credencial, e não
        há dump cru de wire: o consumidor recebe só o que foi decidido expor.
        """
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
            },
            "ruler": {
                "templateId": self.regua.template_id,
                "revisionNumber": self.regua.revision_number,
                "flowHash": self.regua.flow_hash,
                "interceptorsCount": self.regua.interceptors_count,
            },
            "findings": [
                {
                    "severity": a.severity,
                    "scope": a.scope,
                    "message": a.message,
                    "interceptorType": a.interceptor_type,
                    "customInterceptorId": a.custom_interceptor_id,
                }
                for a in self.achados
            ],
            "governance": {
                "workflowId": self.governanca.workflow_id,
                "stageId": self.governanca.stage_id,
                "required": [
                    {
                        "attributeId": r.attribute_id,
                        "name": r.name,
                        "tagId": r.tag_id,
                    }
                    for r in self.governanca.required
                ],
                "missing": [
                    {
                        "attributeId": m.attribute_id,
                        "name": m.name,
                        "tagId": m.tag_id,
                    }
                    for m in self.governanca.missing
                ],
                "blocked": self.governanca.blocked,
            },
            "publication": {
                "attempted": self.publicacao.attempted,
                "accepted": self.publicacao.accepted,
                "verified": self.publicacao.verified,
                "divergences": list(self.publicacao.divergences),
            },
            "completeness": {
                "score": self.completeness.score,
                "gatePercent": self.completeness.gate_percent,
                "suggestions": list(self.completeness.suggestions),
            },
        })
