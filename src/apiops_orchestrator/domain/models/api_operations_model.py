from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from .interceptors_model import Interceptor


class Operation(BaseModel):
    """
    Representa uma operação individual dentro de um resource.
    Pode conter interceptors e metadados como destination e timeout.
    """

    method: str
    path: str
    description: Optional[str] = "Operation Description"
    destination: str
    timeout: Optional[str] = None
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
    def _normalize_timeout(cls, timeout_value: Any) -> Optional[str]:
        if timeout_value in ("", None):
            return None

        try:
            val = int(timeout_value)
        except (TypeError, ValueError):
            return str(timeout_value)

        if val < 0:
            raise ValueError("Timeout must be >= 0")

        return str(val)

    def model_post_init(self, __context):
        if self.timeout is None:
            delattr(
                self, "timeout"
            )  # Does not create model with timeout field if its empty


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
    fileName: str = Field(exclude=True)
    kind: str = "ApiOperations"
    spec: ApiOperationsSpec
