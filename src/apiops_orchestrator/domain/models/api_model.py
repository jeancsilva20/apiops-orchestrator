"""Typed models of the Manager API (`GET /apis/{id}`, `GET /revisions/{id}`).

Typed where the domain reads; tolerant everywhere else. Every model keeps the
wire keys it does not declare (`extra="allow"`) and gives them back untouched in
`to_wire()`, so a payload read from the Manager and written back loses nothing:
the state the repository does not govern (`workflowId`, `certificateId`, fields
added by the platform later) travels through the domain without being seen.

Round-trip is the contract: `Api.model_validate(json).to_wire() == json`, proven
against the real payloads in `tests/fixtures/manager`.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apiops_orchestrator.domain.models.interceptor_model import Interceptor


class WireModel(BaseModel):
    """Base of the models read from the Manager: known fields typed, unknown kept."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def to_wire(self) -> Dict[str, Any]:
        """The payload as the Manager speaks it: wire names, only what was received."""
        return self.model_dump(by_alias=True, exclude_unset=True)


def _empty_list_when_null(value: Any) -> Any:
    return [] if value is None else value


class _Scope(WireModel):
    """What the three scopes (root, resource, operation) share."""

    description: Optional[str] = None
    destination: Optional[str] = None
    # The wire answers `"30"` or `null`; the repository keeps it as text.
    timeout: Optional[Any] = None
    interceptors: List[Interceptor] = Field(default_factory=list)

    @field_validator("interceptors", mode="before")
    @classmethod
    def _interceptors_list(cls, value: Any) -> Any:
        return _empty_list_when_null(value)


class Operation(_Scope):
    method: Optional[str] = None
    path: Optional[str] = None

    @property
    def route(self) -> tuple:
        return (str(self.method or "").upper(), self.path)


class Resource(_Scope):
    name: Optional[str] = None
    operations: List[Operation] = Field(default_factory=list)

    @field_validator("operations", mode="before")
    @classmethod
    def _operations_list(cls, value: Any) -> Any:
        return _empty_list_when_null(value)


class Revision(_Scope):
    id: Optional[int] = None
    revision_number: Optional[int] = Field(default=None, alias="revisionNumber")
    resources: List[Resource] = Field(default_factory=list)

    @field_validator("resources", mode="before")
    @classmethod
    def _resources_list(cls, value: Any) -> Any:
        return _empty_list_when_null(value)

    @property
    def total_operations(self) -> int:
        return sum(len(r.operations) for r in self.resources)


class RevisionSummary(WireModel):
    """One entry of `revisions[]` in `GET /apis/{id}`."""

    id: Optional[int] = None
    revision_number: Optional[int] = Field(default=None, alias="revisionNumber")


class ApiResponsible(WireModel):
    username: Optional[str] = None
    group_name: Optional[str] = Field(default=None, alias="groupName")


class ApiTag(WireModel):
    attribute_name: Optional[str] = Field(default=None, alias="attributeName")
    tags: List[str] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def _tags_list(cls, value: Any) -> Any:
        return _empty_list_when_null(value)


class Api(WireModel):
    id: Optional[int] = None
    name: Optional[str] = None
    version: Optional[str] = None
    base_path: Optional[str] = Field(default=None, alias="basePath")
    description: Optional[str] = None
    api_responsible: Optional[ApiResponsible] = Field(default=None, alias="apiResponsible")
    # `None` is "absent in the Manager", which the repository preserves; `[]` removes all.
    api_tags: Optional[List[ApiTag]] = Field(default=None, alias="apiTags")
    visibility: Optional[Dict[str, Any]] = None
    revisions: List[RevisionSummary] = Field(default_factory=list)

    @field_validator("revisions", mode="before")
    @classmethod
    def _revisions_list(cls, value: Any) -> Any:
        return _empty_list_when_null(value)

    def revision_by_number(self, number: int) -> Optional[RevisionSummary]:
        """The summary with that `revisionNumber` and an `id` (V-24), or `None`."""
        for summary in self.revisions:
            if summary.revision_number == number and summary.id is not None:
                return summary
        return None

    @property
    def revision_numbers(self) -> List[Any]:
        return [s.revision_number for s in self.revisions]


def as_wire(value: Any) -> Any:
    """Bridge for the code that still reads the raw payload: a model becomes its wire dict.

    Used by `validate`, `publish` and `deploy` until they move to the models;
    anything that is not a model (a dict from a test fake) passes through.
    """
    return value.to_wire() if isinstance(value, BaseModel) and hasattr(value, "to_wire") else value
