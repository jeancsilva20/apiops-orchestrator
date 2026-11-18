from abc import ABC, abstractmethod
from typing import Any, Dict, List

from apiops_orchestrator.domain.models.governance_model import (
    GovernanceAvailability,
    WorkflowStage,
)


class GovernanceApiPort(ABC):
    """Adaptive Governance of the Manager.

    Failures use the same signals as `ManagerApiPort`
    (`ManagerApiTransportRejectedError`, `ManagerApiTransportUnavailableError`).
    """

    @abstractmethod
    def availability(self) -> GovernanceAvailability:
        """Tells whether the Manager has the Adaptive Governance module."""

    @abstractmethod
    def get_workflow(self, workflow_id: int) -> Dict[str, Any]:
        """Workflow with `stages[].attributesRequisites`."""

    @abstractmethod
    def get_workflow_stages(self, workflow_id: int) -> List[WorkflowStage]:
        """Stages of one workflow; empty when they cannot be read."""

    @abstractmethod
    def list_attributes(self) -> List[Dict[str, Any]]:
        """Attribute catalog (`id`, `name`, `tags`), read on every execution."""
