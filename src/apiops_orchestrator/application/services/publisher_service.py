import logging
import sys

from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.domain.models.api_partial_model import Visibility
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort
from typing import Dict, Any
from apiops_orchestrator.infrastructure.observability.logging import (
    log_duration,
    set_span_id,
    clear_operation_context,
    set_status,
)


class PublisherService:
    def __init__(self, publisher_port: ManagerApiPort):
        self.publisher = publisher_port
        self.logger = logging.getLogger(__name__)

    def _format_data(
        self, api_data: ApiFull, remote_api_data: Dict[str, Any]
    ) -> ApiFull:
        revisions = remote_api_data["revisions"]

        if "workflowId" in revisions[len(revisions) - 1]:
            api_data.workflowId = revisions[len(revisions) - 1]["workflowId"]
        if "workflowStageId" in revisions[len(revisions) - 1]:
            api_data.workflowStageId = revisions[len(revisions) - 1]["workflowStageId"]

        api_data.api.lastRevision = remote_api_data["lastRevision"]
        api_data.api.creationDate = remote_api_data["creationDate"]

        if "visibility" in remote_api_data and remote_api_data["visibility"]:
            api_data.api.visibility = Visibility(**remote_api_data["visibility"])

        api_data.api.revisions = revisions

        return api_data

    def fetch_remote_api_data(self) -> Dict[str, Any]:
        """Call the port to retrieve the API data."""
        set_span_id()
        with log_duration(__name__):
            self.logger.debug("Loading path file")
            data = self.publisher.get_api_by_id()
            set_status("SUCCESS")
            clear_operation_context()
            return data

    def publish_changes(self, api_data: ApiFull) -> Dict[str, Any]:
        """Send the final JSON to the call."""

        remote_api_data = self.fetch_remote_api_data()
        formatted_api_data = self._format_data(api_data, remote_api_data)

        payload = formatted_api_data.model_dump(by_alias=True, exclude_none=True)

        return self.publisher.publish_api_changes(payload)
