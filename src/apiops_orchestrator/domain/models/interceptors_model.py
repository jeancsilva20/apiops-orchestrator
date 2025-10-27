from pydantic import BaseModel, model_validator
from typing import List, Dict, Any


class Interceptor(BaseModel):
    id: int
    idTemp: int
    position: int
    type: str
    content: Dict[str, Any]
    executionPoint: str
    status: str

    @model_validator(mode="before")
    def set_ids_from_position(cls, values: Dict[str, Any]):
        position = values.get("position")
        if position is not None:
            values.setdefault("id", position)
            values.setdefault("idTemp", position)
        return values


class InterceptorsSpec(BaseModel):
    interceptors: List[Interceptor]


class InterceptorsFile(BaseModel):
    apiVersion: str
    kind: str
    spec: InterceptorsSpec
