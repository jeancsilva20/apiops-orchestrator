from pydantic import BaseModel, field_validator
from typing import Optional, List


class ApiResponsible(BaseModel):
    username: str
    groupName: str  # TODO: Variavel a ser buscada?


class GroupVisibility(BaseModel):
    name: Optional[str] = ""  # TODO: Variavel a ser buscada?


class Visibility(BaseModel):
    groupVisibility: Optional[GroupVisibility] = None  # TODO: Variavel a ser buscada?


class ApiTag(BaseModel):
    attributeName: Optional[str] = "CLI"
    tags: Optional[List[str]] = ["Sensedia"]


class ApiInfo(BaseModel):
    name: str
    version: str
    basePath: str
    description: Optional[str] = "Sample Description"
    apiResponsible: ApiResponsible
    visibility: Optional[Visibility] = None
    apiTags: Optional[List[ApiTag]] = []
    apiType: str = "REST"
    apiSwaggerConfiguration: dict = {
        "showAppRegister": "false",
        "showApiBrowser": "false",
    }

    @field_validator("basePath")
    def _normalize_path(cls, v: str) -> str:
        s = (v or "").strip() or "/"
        if not s.startswith("/"):
            s = "/" + s
        return s


class ApiBasicInfo(BaseModel):
    kind: str = "ApiBasicInfo"
    spec: dict
