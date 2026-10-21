from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from apiops_orchestrator.domain.models.api_visibility_model import (
    ApiVisibility,
    OwnershipContext,
)
from apiops_orchestrator.domain.models.catalog_revision_model import CatalogRevision


class ApiCatalogEntry(BaseModel):
    model_config = {"extra": "ignore"}

    id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    basePath: Optional[str] = None
    lifeCycle: Optional[str] = None
    owner: Optional[str] = None
    updateDate: Optional[Any] = None

    contextType: Optional[OwnershipContext] = None
    contextGroupName: Optional[str] = None
    contextUserLogins: List[str] = Field(default_factory=list)

    lastRevisionNumber: Optional[int] = None

    revisions: List[CatalogRevision] = Field(default_factory=list)

    def to_listing_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "basePath": self.basePath,
            "lifeCycle": self.lifeCycle,
            "owner": self.owner,
            "updateDate": self.updateDate,
            "lastRevision": {"revisionNumber": self.lastRevisionNumber},
        }

    def last_revision_number(self) -> Optional[int]:
        return self.lastRevisionNumber

    def visibility(self) -> ApiVisibility:
        """Visibilidade da API a partir dos campos de contexto do catálogo."""
        return ApiVisibility(
            context=self.contextType,
            owner=self.owner,
            groupName=self.contextGroupName,
            userLogins=self.contextUserLogins,
        )

