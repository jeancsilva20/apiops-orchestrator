from abc import ABC, abstractmethod
from typing import Dict, Any

class PublisherPort(ABC):
    @abstractmethod
    def get_api_by_id(self) -> Dict[str, Any]:
        """Contract to search data from the API by ID"""
        pass

    @abstractmethod
    def publish_api_changes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Contract to publish new API revisions"""
        pass

    def get_custom_interceptor_by_id(self, custom_interceptor_id: int) -> Dict[str, str] | None:
        """Get the content of a custom interceptor"""
        pass