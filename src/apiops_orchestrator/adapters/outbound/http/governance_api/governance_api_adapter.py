"""Adaptive Governance of the Manager, under `/api-governance/api/v3/`."""

import logging
import time
from typing import Any, Dict, List, Optional

from apiops_orchestrator.adapters.outbound.http.common.platform_request import (
    bearer_headers,
    platform_request,
)
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.governance_model import (
    GovernanceAvailability,
    WorkflowStage,
)
from apiops_orchestrator.domain.ports.governance_api_port import GovernanceApiPort
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiError,
    ManagerApiTransportRejectedError,
)

logger = logging.getLogger(__name__)

GOVERNANCE_BASE_PATH = "/api-governance/api/v3/"

# Text of the 403 when the tenant did not contract the module, measured on
# 2026-11-10: "In order to use this resource you must have Governance module enabled."
MODULE_DISABLED_MARKER = "governance module"
AVAILABILITY_ATTEMPTS = 3
AVAILABILITY_INTERVAL_SECONDS = 2.0
AVAILABILITY_TIMEOUT_SECONDS = 10


def _attribute_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("content", "data", "attributes"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def _stage(row: Any) -> Optional[WorkflowStage]:
    if not isinstance(row, dict):
        return None
    try:
        stage_id = int(row.get("workflowStageId"))
    except (TypeError, ValueError):
        return None
    name = row.get("workflowStageName")
    return WorkflowStage(
        workflowStageId=stage_id,
        workflowStageName=name if isinstance(name, str) and name.strip() else None,
    )


class GovernanceApiAdapter(GovernanceApiPort):
    def __init__(self, token: str, max_retries: int, settings: Settings):
        self.host = settings.HOST
        self.token = token
        self.max_retries = max_retries
        self._availability: Optional[GovernanceAvailability] = None
        self._attributes: Optional[List[Dict[str, Any]]] = None
        self._stages_cache: Dict[int, List[WorkflowStage]] = {}

    def _get_headers(self) -> Dict[str, str]:
        return bearer_headers(self.token)

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        kwargs.setdefault("max_retries", self.max_retries)
        return platform_request(
            method,
            f"{self.host or ''}{GOVERNANCE_BASE_PATH}{endpoint}",
            headers=self._get_headers(),
            log_prefix="governance_api",
            **kwargs,
        )

    def availability(self) -> GovernanceAvailability:
        """Reads the attribute catalog once per execution to tell whether the module exists."""
        if self._availability is None:
            self._availability = self._detect()
        return self._availability

    def _detect(self) -> GovernanceAvailability:
        reason = ""
        for attempt in range(1, AVAILABILITY_ATTEMPTS + 1):
            try:
                payload = self._request(
                    "GET",
                    "attributes",
                    max_retries=0,
                    timeout=AVAILABILITY_TIMEOUT_SECONDS,
                )
            except ManagerApiTransportRejectedError as exc:
                if exc.status_code == 403:
                    disabled = any(
                        MODULE_DISABLED_MARKER in message.lower() for message in exc.messages
                    )
                    result = (
                        GovernanceAvailability.DISABLED
                        if disabled
                        else GovernanceAvailability.UNKNOWN
                    )
                    return self._log(result, attempt, "status_403")
                reason = f"status_{exc.status_code}"
            except ManagerApiError as exc:
                reason = type(exc).__name__
            else:
                self._attributes = _attribute_rows(payload)
                return self._log(GovernanceAvailability.ENABLED, attempt, "status_200")
            if attempt < AVAILABILITY_ATTEMPTS:
                time.sleep(AVAILABILITY_INTERVAL_SECONDS)
        return self._log(GovernanceAvailability.UNKNOWN, AVAILABILITY_ATTEMPTS, reason)

    @staticmethod
    def _log(
        result: GovernanceAvailability, attempts: int, reason: str
    ) -> GovernanceAvailability:
        logger.info(
            "governance.availability result=%s attempts=%s reason=%s",
            result.value,
            attempts,
            reason,
        )
        return result

    def get_workflow(self, workflow_id: int) -> Dict[str, Any]:
        return self._request("GET", f"workflows/{workflow_id}")

    def get_workflow_stages(self, workflow_id: int) -> List[WorkflowStage]:
        if workflow_id in self._stages_cache:
            return self._stages_cache[workflow_id]

        try:
            rows = self._request("GET", f"workflows/{workflow_id}/stages")
        except Exception as exc:
            logger.warning(
                "workflow stages unavailable; degrading to empty catalog (%s)",
                type(exc).__name__,
            )
            return []

        stages = [
            stage
            for stage in (_stage(row) for row in (rows if isinstance(rows, list) else []))
            if stage is not None
        ]
        self._stages_cache[workflow_id] = stages
        return stages

    def list_attributes(self) -> List[Dict[str, Any]]:
        """Catalog read by the availability check, or read now."""
        if self._attributes is None:
            self._attributes = _attribute_rows(self._request("GET", "attributes"))
        return list(self._attributes)
