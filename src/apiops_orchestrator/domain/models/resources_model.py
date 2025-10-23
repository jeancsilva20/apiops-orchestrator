from pydantic import BaseModel, Field
from typing import List, Optional, Union
from .api_operations_model import Operation


class ResourceOperationRef(BaseModel):
    """
    Representa uma referência a uma operação dentro de um Resource.
    Essa estrutura vem diretamente do YAML na forma de items no Resources.yaml
    """

    id: Optional[int] = None
    method: Optional[str] = None
    path: Optional[str] = None
    file: Optional[str] = None


class Resource(BaseModel):
    """
    Representa um agrupamento de operações relacionadas a um recurso específico.
    Exemplo: "CEP", "Estados", "CEP IBGE"
    """

    name: str
    description: Optional[str]
    operations: List[Operation] = Field(default_factory=list)


class ResourcesList(BaseModel):
    """
    Representa o arquivo YAML completo de resources.yaml
    """

    apiVersion: str
    kind: str = "ResourcesList"
    items: List[Resource]
