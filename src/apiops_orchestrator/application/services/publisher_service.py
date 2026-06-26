import json
import logging
import sys

from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.domain.models.api_partial_model import Visibility, ApiRevision
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
        revisions_raw = remote_api_data.get("revisions", [])

        # Filter/convert each revision dict to ApiRevision, keeping only specified fields
        revisions = []
        for r in revisions_raw:
            if isinstance(r, dict):
                revisions.append(ApiRevision(**r))
            else:
                revisions.append(r)

        if revisions:
            last_rev = revisions[-1]
            if isinstance(last_rev, ApiRevision):
                if last_rev.workflowId is not None:
                    api_data.workflowId = last_rev.workflowId
                if last_rev.workflowStageId is not None:
                    api_data.workflowStageId = last_rev.workflowStageId
            elif isinstance(last_rev, dict):
                if "workflowId" in last_rev:
                    api_data.workflowId = last_rev["workflowId"]
                if "workflowStageId" in last_rev:
                    api_data.workflowStageId = last_rev["workflowStageId"]

        last_revision_raw = remote_api_data.get("lastRevision")
        if isinstance(last_revision_raw, dict):
            api_data.api.lastRevision = ApiRevision(**last_revision_raw)
        else:
            api_data.api.lastRevision = last_revision_raw

        api_data.api.creationDate = remote_api_data.get("creationDate")

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
