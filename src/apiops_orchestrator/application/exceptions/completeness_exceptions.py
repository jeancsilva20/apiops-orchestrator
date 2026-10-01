class CompletenessError(Exception):
    """Base dos erros de negócio do `sen completeness` (a CLI mapeia para exit/msg)."""

    exit_code = 2

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


_NOT_FOUND_TEMPLATE = (
    "Revisão {revision_id} não encontrada. "
    "Redescubra um REV ID válido: sen list api --id X --revisions."
)


class CompletenessNotFound(CompletenessError):
    def __init__(self, revision_id: int):
        super().__init__(_NOT_FOUND_TEMPLATE.format(revision_id=revision_id))


class CompletenessUnauthorized(CompletenessError):
    def __init__(self):
        super().__init__("Sessão inválida ou expirada. Faça `sen login` novamente.")


class CompletenessDenied(CompletenessError):
    def __init__(self, revision_id: int):
        super().__init__(_NOT_FOUND_TEMPLATE.format(revision_id=revision_id))


class CompletenessPlatformError(CompletenessError):
    def __init__(self, detail: str):
        super().__init__(
            f"A plataforma recusou a consulta ({detail}). "
            "Tente novamente em instantes; se persistir, acione o time de acesso."
        )
