from pydantic import BaseModel, Field
from typing import Optional, List
from .interceptors_model import Interceptor


class Operation(BaseModel):
    """
    Representa uma operação individual dentro de um resource.
    Pode conter interceptors e metadados como destination e timeout.
    """

    method: str
    path: str
    description: Optional[str] = None
    destination: Optional[str] = None
    timeout: Optional[str] = None
    interceptors: List[Interceptor] = Field(default_factory=list)


class ApiOperationsSpec(BaseModel):
    """
    Estrutura do campo 'spec' dentro do YAML de ApiOperations.
    """

    operations: List[Operation] = Field(alias="operation")


class ApiOperationsFile(BaseModel):
    """
    Representa o arquivo YAML completo de ApiOperations.
    """

    apiVersion: str
    kind: str = "ApiOperations"
    spec: ApiOperationsSpec
