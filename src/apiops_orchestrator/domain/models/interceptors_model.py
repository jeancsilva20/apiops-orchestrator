from pydantic import BaseModel
from typing import List, Dict, Any


class Interceptor(BaseModel):
    id: int
    idTemp: int
    position: int
    type: str
    content: Dict[str, Any]
    executionPoint: str
    status: str


class InterceptorsSpec(BaseModel):
    interceptors: List[Interceptor]


class InterceptorsFile(BaseModel):
    apiVersion: str
    kind: str
    spec: InterceptorsSpec
