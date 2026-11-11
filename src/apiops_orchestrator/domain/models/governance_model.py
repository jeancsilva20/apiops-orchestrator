"""Adaptive Governance models: whether the Manager has the module, and workflow stages."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class GovernanceAvailability(str, Enum):
    """Whether the Manager has the Adaptive Governance module."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    UNKNOWN = "unknown"

    @property
    def absent(self) -> bool:
        """True only when the absence of the module is confirmed."""
        return self is GovernanceAvailability.DISABLED


class WorkflowStage(BaseModel):
    workflowStageId: int
    workflowStageName: Optional[str] = None
