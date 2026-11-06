"""Errors of `sen schema`: message in PT-BR and the exit code the CLI uses."""


class SchemaError(Exception):
    exit_code = 1

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class SchemasUnavailableError(SchemaError):
    def __init__(self):
        super().__init__(
            "Os schemas não foram encontrados nesta instalação do sen. A instalação "
            "está incompleta: reinstale o sen."
        )
