from pydantic import BaseModel, field_validator
from typing import Optional, List


class ApiResponsible(BaseModel):
    groupName: str  # Perform a GET request


class GroupVisibility(BaseModel):
    name: Optional[str] = ""  # Perform a GET request


class Visibility(BaseModel):
    visibilityType: Optional[str] = "GROUP"
    groupVisibility: Optional[GroupVisibility] = None  # Perform a GET request


class ApiTag(BaseModel):
    attributeName: str
    tags: List[str]


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
    creationDate: Optional[int] = "creationDate"
    revisions: Optional[list[dict]] = "revisions"
    lastRevision: Optional[dict] = "lastRevision"

    @field_validator("basePath")
    def _normalize_path(cls, v: str) -> str:
        s = (v or "").strip() or "/"
        if not s.startswith("/"):
            s = "/" + s
        return s


class ApiBasicInfo(BaseModel):
    kind: str = "ApiBasicInfo"
    spec: dict
