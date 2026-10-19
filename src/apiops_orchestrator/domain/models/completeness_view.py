from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CompletenessContext:
    type: Optional[str] = None
    group_name: Optional[str] = None
    owner: Optional[str] = None


@dataclass(frozen=True)
class CompletenessApi:
    manager_id: int
    name: Optional[str] = None
    version: Optional[str] = None
    context: Optional[CompletenessContext] = None


@dataclass(frozen=True)
class CompletenessSuggestion:
    index: int
    text: str


@dataclass(frozen=True)
class CompletenessView:
    """Objeto de RESPOSTA do use-case `sen completeness` (service → CLI).
    """

    schema: str
    generated_at: str
    api: CompletenessApi
    revision_id: int
    revision_number: Optional[int]
    score: float
    gate_percent: float
    suggestions: List[CompletenessSuggestion] = field(default_factory=list)

    def to_document(self) -> Dict[str, Any]:
        """Árvore do contrato v1, na ordem declarada (sem campos-fantasma)."""
        context = self.api.context
        return {
            "schema": self.schema,
            "generatedAt": self.generated_at,
            "api": {
                "managerId": self.api.manager_id,
                "name": self.api.name,
                "version": self.api.version,
                "context": (
                    {
                        "type": context.type,
                        "groupName": context.group_name,
                        "owner": context.owner,
                    }
                    if context
                    else None
                ),
            },
            "revision": {
                "managerId": self.revision_id,
                "revisionNumber": self.revision_number,
            },
            "maturity": {"score": self.score},
            "gate": {"percent": self.gate_percent},
            "suggestions": [
                {"index": item.index, "text": item.text}
                for item in self.suggestions
            ],
        }
