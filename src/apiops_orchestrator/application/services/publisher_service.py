import logging
from apiops_orchestrator.domain.ports.manager_api_port import PublisherPort
from typing import Dict, Any
from apiops_orchestrator.infrastructure.observability.logging import log_duration, set_span_id, clear_operation_context, set_status


class PublisherService:
    def __init__(self, publisher_port: PublisherPort):
        self.publisher = publisher_port
        self.logger = logging.getLogger(__name__)

    def fetch_remote_api_data(self) -> Dict[str, Any]:
        """Call the port to retrieve the API data."""
        set_span_id()
        with log_duration(__name__):
            self.logger.debug("Loading path file")
            data = self.publisher.get_api_by_id()
            set_status("SUCCESS")
            self.logger.info(f"Data reached successfully: {data}")
            clear_operation_context()
            return data