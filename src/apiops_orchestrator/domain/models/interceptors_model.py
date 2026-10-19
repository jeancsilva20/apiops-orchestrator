from pydantic import BaseModel, model_validator
from typing import List, Dict, Any, Union


class Interceptor(BaseModel):
    """⚠️ MODELO LEGADO — não usar em código novo.

    Descreve o shape ANTIGO e tem um defeito conhecido: `set_ids_from_position`
    deriva `idTemp` de `position`, que é do **escopo**. O `idTemp` é do
    **payload inteiro** (W-9), e dois itens novos em escopos diferentes com o
    mesmo valor fazem o Manager **descartar um deles**, devolvendo HTTP 200 —
    perda silenciosa. Além disso `id` e `idTemp` são `int` obrigatórios, então
    "`id` nulo em item novo" não é sequer representável.

    O caminho novo não passa por aqui: a aritmética de identidade vive em
    `domain/services/interceptor_flow.py`, sobre dicts do wire, com contador
    global de `idTemp` e `id: None` em item novo. Este modelo permanece apenas
    enquanto o `ConversorService` do pipeline bare o consumir, e sai com ele na
    substituição do publisher.
    """

    id: int
    idTemp: int
    position: int
    type: str
    content: Union[Dict[str, Any], str, int]
    executionPoint: str
    status: str

    @model_validator(mode="before")
    def set_ids_from_position(cls, values: Dict[str, Any]):
        """⚠️ Fonte da colisão de `idTemp` do W-9. Ver a nota da classe."""
        position = values.get("position")
        if position is not None:
            values.setdefault("id", position)
            values.setdefault("idTemp", position)
        return values


class InterceptorsSpec(BaseModel):
    interceptors: List[Interceptor]


class InterceptorsFile(BaseModel):
    apiVersion: str
    kind: str
    spec: InterceptorsSpec
