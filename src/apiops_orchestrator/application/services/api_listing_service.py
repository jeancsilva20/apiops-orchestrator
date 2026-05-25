from typing import List, Dict, Any
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort

class ApiListingService:
    def __init__(self, manager_api: ManagerApiPort):
        self.manager_api = manager_api

    def list_apis(self, api_id: int | None = None) -> List[Dict[str, Any]]:
        """
        Retrieves a list of APIs. If api_id is provided, returns a list containing that single API.
        """
        if api_id:
            api = self.manager_api.get_api_by_id(api_id)
            return [api]
        
        return self.manager_api.get_apis()
