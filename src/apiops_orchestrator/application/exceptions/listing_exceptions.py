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
        super().__init__(
            f"API {api_id} não encontrada ou sem permissão de acesso."
        )

class InvalidWindow(ApiCollectionError):
    _TEMPLATES = {
        "ge_zero": "--{param} deve ser maior ou igual a zero.",
        "gt_zero": "--{param} deve ser maior que zero.",
    }

    def __init__(self, param: str, rule: str):
        super().__init__(self._TEMPLATES[rule].format(param=param))

class InsufficientSessionError(ApiCollectionError):
    def __init__(self):
        super().__init__(
            "Sua sessão não possui grupos de acesso, refaça `sen login` ou "
            "acione o time de acesso."
        )
