from pydantic import BaseModel, field_validator
from typing import Optional, List


class ApiResponsible(BaseModel):
    username: str
    groupName: str  # TODO: Variavel a ser buscada?


class GroupVisibility(BaseModel):
    name: Optional[str] = ""  # TODO: Variavel a ser buscada?


class Visibility(BaseModel):
    visibilityType: Optional[str] = "GROUP"
    groupVisibility: Optional[GroupVisibility] = None  # TODO: Variavel a ser buscada?


class ApiTag(BaseModel):
    attributeName: Optional[str] = "CLI"  # Opcional, cliente com AG, vindo .env
    tags: Optional[List[str]] = ["Sensedia"]  # Opcional, cliente com AG, vindo .env


class ApiInfo(BaseModel):
    name: str
    version: str
    basePath: str
    description: Optional[str] = "Sample Description"
    apiResponsible: ApiResponsible
    visibility: Optional[Visibility] = None  # Copiar da resposta do GET
    apiTags: Optional[List[ApiTag]] = []  # Opcional, cliente com AG, vindo .env
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
