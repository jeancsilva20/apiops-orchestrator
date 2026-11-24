from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    API_NOT_FOUND_TEMPLATE,
)


class ListingError(Exception):
    exit_code = 1

    def __init__(self, message: str, exit_code: int | None = None):
        self.message = message
        if exit_code is not None:
            self.exit_code = exit_code
        super().__init__(self.message)


class ApiCollectionError(ListingError):
    exit_code = 1


class ApiNotFound(ApiCollectionError):
    def __init__(self, api_id: int):
        super().__init__(API_NOT_FOUND_TEMPLATE.format(api_id=api_id))

class InvalidWindow(ApiCollectionError):
    _TEMPLATES = {
        "ge_zero": "--{param} deve ser maior ou igual a zero.",
        "gt_zero": "--{param} deve ser maior que zero.",
    }

    def __init__(self, param: str, rule: str):
        super().__init__(self._TEMPLATES[rule].format(param=param))

class AttributeNotFound(ApiCollectionError):
    """Nome pedido em `--attribute` que o catálogo de governança não cadastra.

    Sem esta recusa o comando devolveria uma lista vazia, indistinguível de
    "nenhuma API declara o atributo".
    """

    _SHOWN = 8

    def __init__(self, name: str, known: list[str]):
        shown = ", ".join(known[: self._SHOWN]) or "nenhum atributo cadastrado"
        rest = len(known) - self._SHOWN
        if rest > 0:
            shown += f" (+{rest})"
        super().__init__(
            f"O atributo '{name}' não existe no catálogo de governança. "
            f"Atributos: {shown}. Consulte: sen list attributes."
        )


class InsufficientSessionError(ApiCollectionError):
    def __init__(self):
        super().__init__(
            "Sua sessão não possui grupos de acesso, refaça `sen login` ou "
            "acione o time de acesso."
        )
