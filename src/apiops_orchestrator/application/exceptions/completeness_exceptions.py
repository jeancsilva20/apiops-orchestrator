from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    API_NOT_FOUND_TEMPLATE,
    UNAUTHORIZED_MESSAGE,
)


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


class CompletenessApiNotFound(CompletenessError):
    def __init__(self, api_id: int):
        super().__init__(API_NOT_FOUND_TEMPLATE.format(api_id=api_id))


class CompletenessUnauthorized(CompletenessError):
    def __init__(self):
        super().__init__(UNAUTHORIZED_MESSAGE)


class CompletenessDenied(CompletenessError):
    def __init__(self, revision_id: int):
        super().__init__(_NOT_FOUND_TEMPLATE.format(revision_id=revision_id))


class CompletenessPlatformError(CompletenessError):
    """Falha da plataforma sem leitura de negócio (erro interno ou indisponível).

    Recebe a mensagem padrão da família, já pronta — nunca status/título HTTP.
    """
