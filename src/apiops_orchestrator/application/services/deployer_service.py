import logging
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort
from typing import Dict, Any
from apiops_orchestrator.infrastructure.observability.logging import (
    log_duration,
    set_span_id,
    clear_operation_context,
    set_status,
)


class DeployerService:
    def __init__(self, manager_port: ManagerApiPort):
        self.manager = manager_port
        self.logger = logging.getLogger(__name__)

    def fetch_remote_api_data(self) -> Dict[str, Any]:
        """Call the port to retrieve the API data."""
        set_span_id()
        with log_duration(__name__):
            self.logger.debug("Loading path file")
            data = self.manager.get_api_by_id()
            set_status("SUCCESS")
            clear_operation_context()
            return data

    def deploy_revision(self, environment_id: int) -> Dict[str, Any]:
        """Deploys the last API revision."""
        set_span_id()
        with log_duration(__name__):
            self.logger.info(f"Retrieving API data to get last revision")
            remote_api_data = self.fetch_remote_api_data()
            revision_id = remote_api_data["lastRevision"]["id"]

            payload = {
                "environmentId": environment_id,
                "revisionId": revision_id,
                "status": "DEPLOYED",
            }

            self.logger.info(
                f"Deploying revision {revision_id} to environment {environment_id}"
            )
            data = self.manager.deploy_api(payload)
            set_status("SUCCESS")
            clear_operation_context()
            return data
