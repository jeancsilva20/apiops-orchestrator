from abc import ABC, abstractmethod
from typing import Dict, Any

class PublisherPort(ABC):
    @abstractmethod
    def get_api_by_id(self) -> Dict[str, Any]:
        """Contract to search data from the API by ID"""
        pass