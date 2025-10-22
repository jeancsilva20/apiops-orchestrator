from pydantic import BaseModel
from typing import List, Optional


class Operation(BaseModel):
    method: str
    path: str
    description: Optional[str] = None
    file: Optional[str] = None


class Resource(BaseModel):
    name: str
    description: Optional[str] = ""
    operations: List[Operation] = []


class ResourcesList(BaseModel):
    kind: str = "ResourcesList"
    items: List[Resource]
