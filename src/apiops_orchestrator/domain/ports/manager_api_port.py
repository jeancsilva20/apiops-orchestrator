from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry


@dataclass(frozen=True)
class ApiCatalogPage:
    """Uma pagina do catalogo (api-finder) com o total de registros."""

    rows: List[ApiCatalogEntry]
    total: int


class ManagerApiPort(ABC):
    @abstractmethod
    def get_apis(self) -> list[Dict[str, Any]]:
        """Contract to search all APIs (manager cru — fluxo legado/bare)."""
        pass

    @abstractmethod
    def list_catalog_apis(
        self,
        limit: int,
        query: Optional[str] = None,
    ) -> ApiCatalogPage:
        """Contract to search the APIs catalog with query filter."""
        pass

    @abstractmethod
    def get_api_by_id(self, api_id: int) -> Dict[str, Any]:
        """Contract to search data from the API by ID """
        pass

    @abstractmethod
    def list_api_detail(self, api_id: int) -> Optional[ApiCatalogEntry]:
        """Search API detail from the CATALOG."""
        pass

    @abstractmethod
    def get_workflow_stages(self, workflow_id: int) -> list[Dict[str, Any]]:
        """Contract to fetch the stages catalog of one workflow."""
        pass

    @abstractmethod
    def publish_api_changes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Contract to publish new API revisions"""
        pass

    def get_custom_interceptor_by_id(
        self, custom_interceptor_id: int
    ) -> Dict[str, str] | None:
        """Get the content of a custom interceptor"""
        pass
