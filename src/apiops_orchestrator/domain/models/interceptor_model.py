"""Typed models of the Manager interceptors: the flow item and the custom of the catalog.

Same contract as `api_model`: known fields typed, unknown wire keys kept
(`extra="allow"`) and given back untouched by `to_wire()`.
"""

import json
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class CustomInterceptor(BaseModel):
    """A custom interceptor of the tenant catalog (`GET /custom-interceptors`).

    The same shape is saved as text in the `content` of a `Custom` item of a flow.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: Optional[int] = None
    name: Optional[str] = None
    script: Optional[str] = None

    def to_wire(self) -> Dict[str, Any]:
        """The payload as the Manager speaks it: wire names, only what was received."""
        return self.model_dump(by_alias=True, exclude_unset=True)


class Interceptor(BaseModel):
    """An item of the interceptor flow of a scope (root, resource or operation)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: Optional[int] = None
    type: Optional[str] = None
    execution_point: Optional[str] = Field(default=None, alias="executionPoint")
    position: Optional[int] = None
    status: Optional[str] = None
    parent: Optional[Dict[str, Any]] = None
    custom_interceptor_id: Optional[int] = Field(default=None, alias="customInterceptorId")
    # Text (JSON serialized) for the native types; the platform may answer other shapes.
    content: Optional[Any] = None

    def to_wire(self) -> Dict[str, Any]:
        """The payload as the Manager speaks it: wire names, only what was received."""
        return self.model_dump(by_alias=True, exclude_unset=True)

    @property
    def parent_id(self) -> Optional[int]:
        return (self.parent or {}).get("id")

    @property
    def label(self) -> str:
        """`Custom#<id>` or the type, for messages."""
        if self.custom_interceptor_id:
            return f"{self.type}#{self.custom_interceptor_id}"
        return str(self.type)

    @property
    def custom(self) -> Optional[CustomInterceptor]:
        """The custom interceptor saved in the `content` of a `Custom` item."""
        if not self.custom_interceptor_id:
            return None
        content = self.content
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except ValueError:
                return None
        if not isinstance(content, dict):
            return None
        try:
            return CustomInterceptor.model_validate(content)
        except ValidationError:
            return None
