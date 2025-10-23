from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from .interceptors_model import Interceptor


class Operation(BaseModel):
    """
    Representa uma operação individual dentro de um resource.
    Pode conter interceptors e metadados como destination e timeout.
    """

    method: str
    path: str
    description: Optional[str] = "Sample Operation Description"
    destination: Optional[str] = None
    timeout: Optional[str] = "60"
    interceptors: List[Interceptor] = Field(default_factory=list)

    @field_validator("method")
    def _upper_http_method(cls, method: str) -> str:
        return method.upper()

    @field_validator("path")
    def _normalize_path(cls, v: str) -> str:
        s = (v or "").strip() or "/"
        if not s.startswith("/"):
            s = "/" + s
        return s

    @field_validator("timeout", mode="before")
    def _non_negative_timeout(cls, timeout_value: any) -> str:
        if timeout_value == "":
            return "60"

        try:
            val = int(timeout_value)
        except (TypeError, ValueError):
            # Let Pydantic's core validation handle types that can't be cast to int (e.g., 'abc')
            return timeout_value

        if val < 0:
            raise ValueError("Timeout must be >= 0")

        return timeout_value


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
    file_name: str = Field(exclude=True)
    kind: str = "ApiOperations"
    spec: ApiOperationsSpec
