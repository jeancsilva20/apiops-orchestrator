from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List, Union, Any


class ApiResponsible(BaseModel):
    username: str
    groupName: str  # Perform a GET request


class GroupVisibility(BaseModel):
    name: Optional[str] = ""  # Perform a GET request


class Visibility(BaseModel):
    visibilityType: Optional[str] = "GROUP"
    groupVisibility: Optional[GroupVisibility] = None  # Perform a GET request


class ApiTag(BaseModel):
    attributeName: str
    tags: List[str]


class ApiRevision(BaseModel):
    id: Optional[Union[int, str]] = None
    interceptors: List[Any] = []
    apiBroken: bool = False
    revisionNumber: Optional[int] = None
    lifeCycle: Optional[str] = "AVAILABLE"
    creationDate: Optional[Union[int, str]] = None
    deployments: List[Any] = []
    resources: List[Any] = []
    workflowId: Optional[int] = None
    workflowStageId: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def force_empty_and_default_fields(cls, values: Any) -> Any:
        if isinstance(values, dict):
            values["interceptors"] = []
            values["deployments"] = []
            values["resources"] = []
            values["apiBroken"] = False
        return values


class ApiPartialInfo(BaseModel):
    id: str
    name: str
    version: str
    basePath: str
    description: Optional[str] = "API Description"
    apiResponsible: ApiResponsible
    visibility: Optional[Visibility] = None  # Copy from the GET response.
    apiTags: Optional[List[ApiTag]] = []
    apiType: str = "REST"
    apiSwaggerConfiguration: dict = {
        "showAppRegister": "false",
        "showApiBrowser": "false",
    }

    # Placeholders until the implementation of GET in Sensedia APIM is completed.
    creationDate: Optional[Union[int, str]] = "creationDate"
    revisions: Optional[Union[List[ApiRevision], str]] = "revisions"
    lastRevision: Optional[Union[ApiRevision, str]] = "lastRevision"
    environments: Optional[List[dict]] = []

    @field_validator("basePath")
    def _normalize_path(cls, v: str) -> str:
        s = (v or "").strip() or "/"
        if not s.startswith("/"):
            s = "/" + s
        return s


class ApiBasicInfo(BaseModel):
    kind: str = "ApiBasicInfo"
    spec: dict
