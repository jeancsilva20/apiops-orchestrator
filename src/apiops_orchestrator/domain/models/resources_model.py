from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from .api_operations_model import Operation


# This model represents the 'operations' block in ResourcesList.yaml
# It's a reference, not the full operation.
class ResourceOperationRef(BaseModel):
    method: str
    path: str
    file: str

    @field_validator("method")
    def _upper_http_method(cls, method: str) -> str:
        return method.upper()


# This model represents an 'item' in your ResourcesList.yaml
class ResourceSpec(BaseModel):
    name: str
    description: Optional[str] = "Resource Description"
    operations: List[ResourceOperationRef] = Field(default_factory=list)


class ResourcesSpecList(BaseModel):
    """
    Represents the file resources.yaml
    """

    apiVersion: str
    kind: str = "ResourcesList"
    items: List[ResourceSpec]


# --- This is the FINAL model ---
# This is what you will output in your ApiFull
class Resource(BaseModel):
    """
    Represents a final, enriched resource.
    """

    name: str
    description: Optional[str] = "Resource Description"
    operations: List[Operation] = Field(default_factory=list)
