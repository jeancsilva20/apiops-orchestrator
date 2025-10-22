from pydantic import BaseModel
from typing import Optional, List


class ApiResponsible(BaseModel):
    username: Optional[str] = ""
    groupName: Optional[str] = ""


class GroupVisibility(BaseModel):
    name: Optional[str] = ""


class Visibility(BaseModel):
    groupVisibility: Optional[GroupVisibility] = None


class ApiTag(BaseModel):
    attributeName: Optional[str] = ""
    tags: Optional[List[str]] = []


class ApiInfo(BaseModel):
    name: Optional[str] = ""
    version: Optional[str] = ""
    basePath: Optional[str] = ""
    description: Optional[str] = ""
    apiResponsible: Optional[ApiResponsible] = None
    visibility: Optional[Visibility] = None
    apiTags: Optional[List[ApiTag]] = []
    apiType: str = "REST"
    apiSwaggerConfiguration: dict = {
        "showAppRegister": "false",
        "showApiBrowser": "false",
    }


class ApiBasicInfo(BaseModel):
    kind: str = "ApiBasicInfo"
    spec: dict
