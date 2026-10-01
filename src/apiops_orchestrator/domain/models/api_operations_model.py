from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from .interceptors_model import Interceptor


class Operation(BaseModel):
    """
    Represents an individual operation within a resource.
    May contain interceptors and metadata such as destination and timeout.
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
        """Does not create model with timeout field if its empty"""
        if self.timeout is None:
            delattr(self, "timeout")


class ApiOperationsSpec(BaseModel):
    """
    Structure of the 'spec' field within the ApiOperations YAML.
    """

    operations: List[Operation] = Field(alias="operation")


class ApiOperationsFile(BaseModel):
    """
    Represents the complete ApiOperations YAML file.
    """

    apiVersion: str
    fileName: str = Field(exclude=True)
    kind: str = "ApiOperations"
    spec: ApiOperationsSpec
