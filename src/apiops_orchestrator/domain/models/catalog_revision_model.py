from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CatalogRevision(BaseModel):
    model_config = {"extra": "ignore"}

    id: Optional[int] = None
    revisionNumber: Optional[int] = None
    creationDate: Optional[Any] = None

    environments: List[str] = []

    workflowId: Optional[int] = None
    workflowStageId: Optional[int] = None

    completenessScore: Optional[float] = None


@dataclass(frozen=True)
class CatalogRevisionInfo:
    revision_id: int
    revision_number: int
    stage_name: Any
    environments: str
    complete: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "revision_number": self.revision_number,
            "stage_name": self.stage_name,
            "environments": self.environments,
            "complete": self.complete,
        }
