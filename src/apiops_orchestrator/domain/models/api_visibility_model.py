from enum import StrEnum
from typing import List, Optional

from pydantic import BaseModel, Field


class OwnershipContext(StrEnum):
    ORGANIZATION = "organization"
    ME = "me"
    GROUP = "group"


class ApiVisibility(BaseModel):
    """Quem enxerga uma API: tipo da visibilidade, dono, grupo e usuários."""

    model_config = {"frozen": True}

    context: Optional[OwnershipContext] = None
    owner: Optional[str] = None
    groupName: Optional[str] = None
    userLogins: List[str] = Field(default_factory=list)
