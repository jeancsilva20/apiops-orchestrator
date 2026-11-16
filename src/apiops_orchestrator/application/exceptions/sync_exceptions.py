"""Erros de negócio do `sen sync`: `message` em PT-BR e `exit_code` por categoria.

    1  argumento ausente ou inválido, repositório ilegível, falha técnica
    2  sem sessão, token expirado ou recusado
    3  API inexistente ou fora da visibilidade da sessão
    4  revisão inexistente, sem recursos ou com swagger que não é OpenAPI 3
    5  `spec.id` existente diferente do `<api-id>`
    6  caminho longo demais ou erro de escrita
    7  Manager inacessível
    8  (só na CLI) `--check` encontrou diferença
"""

from typing import Any, Sequence

from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    API_NOT_FOUND_TEMPLATE,
    UNAVAILABLE_MESSAGE,
)

NOTHING_WRITTEN = "Nada foi gravado."
EXIT_DIFFERENCES = 8


class SyncError(Exception):
    """Base dos erros do `sen sync`."""

    exit_code = 1

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class MissingApiIdError(SyncError):
    """Nem o argumento nem o `spec.id` dizem qual API carregar."""

    def __init__(self):
        super().__init__(
            "Informe o id da API: `sen sync <api-id> --revision <n>`. O `spec.id` do "
            f"`api-basic-info.yaml` ainda não está preenchido.\n\n{NOTHING_WRITTEN}"
        )


class InvalidRepositoryError(SyncError):
    """O `--check` precisa da árvore completa e legível."""

    def __init__(self, problems: Sequence[str]):
        listed = "\n".join(f"  - {p}" for p in problems)
        super().__init__(
            "O repositório não está na estrutura esperada para a verificação:\n\n"
            f"{listed}\n\nFaça a carga com `sen sync` ou corrija os arquivos."
        )
        self.problems = list(problems)


class SessionRejectedError(SyncError):
    exit_code = 2

    def __init__(self, message: str):
        super().__init__(f"{message}\n\n{NOTHING_WRITTEN}")


class ApiNotFoundError(SyncError):
    """Inexistente e invisível respondem igual (api-visibility)."""

    exit_code = 3

    def __init__(self, api_id: Any):
        super().__init__(
            f"{API_NOT_FOUND_TEMPLATE.format(api_id=api_id)} Confira o id e o seu "
            f"acesso no Manager.\n\n{NOTHING_WRITTEN}"
        )
        self.api_id = api_id


class RevisionNotFoundError(SyncError):
    exit_code = 4

    def __init__(self, api_id: Any, number: int, available: Sequence[Any]):
        listed = ", ".join(str(n) for n in available) or "nenhuma"
        super().__init__(
            f"A API {api_id} não tem revisão de número {number}. Disponíveis: {listed}.\n\n"
            "O sen sync espera a API com as quatro revisões do APIOps (1 Draft, 2 DEV, "
            f"3 HML, 4 PRD). Use um dos números listados ou prepare a API no Manager.\n\n"
            f"{NOTHING_WRITTEN}"
        )
        self.number = number
        self.available = list(available)


class EmptyRevisionError(SyncError):
    exit_code = 4

    def __init__(self, number: int, revision_id: Any):
        super().__init__(
            f"A revisão {number} (id {revision_id}) não tem recursos. Confira a revisão "
            f"no Manager.\n\n{NOTHING_WRITTEN}"
        )


class UnsupportedSwaggerError(SyncError):
    """The revision swagger is not OpenAPI 3, so the contract cannot be brought."""

    exit_code = 4

    def __init__(self, number: int, document_format: str):
        super().__init__(
            f"O swagger da revisão {number} está em {document_format}. O sen sync só "
            "traz contrato OpenAPI 3: migre o swagger da API para OpenAPI 3 no "
            f"Manager.\n\n{NOTHING_WRITTEN}"
        )
        self.document_format = document_format


class ApiIdMismatchError(SyncError):
    exit_code = 5

    def __init__(self, in_repo: Any, received: Any):
        super().__init__(
            f"O `spec.id` do `api-basic-info.yaml` é {in_repo}, mas o comando recebeu "
            f"{received}. Confira o id.\n\n{NOTHING_WRITTEN}"
        )


class WriteFailedError(SyncError):
    exit_code = 6

    def __init__(self, reason: str, path: str | None):
        where = f" em `{path}`" if path else ""
        super().__init__(
            f"Não foi possível gravar a estrutura{where}: {reason}.\n\n"
            "Se o problema for o tamanho do caminho, encurte o caminho do clone "
            f"(limite de 260 caracteres no Windows).\n\n{NOTHING_WRITTEN}"
        )


class ManagerUnavailableError(SyncError):
    exit_code = 7

    def __init__(self):
        super().__init__(f"{UNAVAILABLE_MESSAGE}\n\n{NOTHING_WRITTEN}")
