from apiops_orchestrator.domain.ports.manager_api_port import PublisherPort
from typing import Dict, Any

class PublisherService:
    def __init__(self, publisher_port: PublisherPort):
        self.publisher = publisher_port

    def fetch_remote_api_data(self) -> Dict[str, Any]:
        """Call the port to retrieve the API data."""
        return self.publisher.get_api_by_id()