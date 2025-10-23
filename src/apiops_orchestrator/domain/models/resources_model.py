from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from .api_operations_model import Operation


# This model represents the 'operations' block in ResourcesList.yaml
# It's a reference, not the full operation.
class ResourceOperationRef(BaseModel):
    id: Optional[int] = (
        None  # TODO Ver paulo, ID da Operation, no body do postman não tem.
    )
    method: str
    path: str
    file: str

    @field_validator("method")
    def _upper_http_method(cls, method: str) -> str:
        return method.upper()


# This model represents an 'item' in your ResourcesList.yaml
class ResourceSpec(BaseModel):
    id: Optional[int] = (
        None  # TODO Ver paulo, ID do Resource, no body do postman não tem.
    )
    name: str
    description: Optional[str] = "Sample Resource Description"
    operations: List[ResourceOperationRef] = Field(default_factory=list)


class ResourcesList(BaseModel):
    """
    Represents the file resources.yaml
    """

    apiVersion: str
    kind: str = "ResourcesList"
    items: List[ResourceSpec]  # <-- It parses into a list of Specs, not final Resources


# --- This is the FINAL model ---
# This is what you will output in your ApiFull
class Resource(BaseModel):
    """
    Represents a final, enriched resource.
    """

    id: Optional[int] = (
        None  # TODO Ver paulo, ID da Operation, no body do postman não tem.
    )
    name: str
    description: Optional[str] = "Sample Resource Description"
    operations: List[Operation] = Field(default_factory=list)
