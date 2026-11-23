"""Erros de negócio dos comandos de navegação (`sen get ...`, `sen export ...`).

Cada um carrega a mensagem pronta para o usuário e o exit code; a CLI só
imprime. Seguem a mesma família de textos dos demais comandos que leem o
Manager (`manager_failure_messages`).
"""

from typing import Sequence

from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    API_NOT_FOUND_TEMPLATE,
)


class NavigationError(Exception):
    exit_code = 1

    def __init__(self, message: str, exit_code: int | None = None):
        self.message = message
        if exit_code is not None:
            self.exit_code = exit_code
        super().__init__(self.message)


class NavigationApiNotFound(NavigationError):
    def __init__(self, api_id: int):
        super().__init__(API_NOT_FOUND_TEMPLATE.format(api_id=api_id))


class NavigationRevisionNotFound(NavigationError):
    def __init__(self, api_id: int, wanted: str, available: Sequence[int]):
        numbers = ", ".join(str(n) for n in available) or "nenhuma"
        super().__init__(
            f"A API {api_id} não tem a revisão {wanted}. "
            f"Números disponíveis: {numbers}. Consulte: sen get api --id {api_id}"
        )


class NavigationScopeNotFound(NavigationError):
    def __init__(self, api_id: int, selector: str):
        super().__init__(
            f"Nenhum recurso/operação da API {api_id} corresponde a {selector}. "
            f"Veja os nomes exatos com: sen get resources --id {api_id}"
        )


class NavigationInterceptorNotFound(NavigationError):
    def __init__(self, api_id: int, item_id: int):
        super().__init__(
            f"Nenhum interceptor com id {item_id} nesta revisão da API {api_id}. "
            f"Liste os ids com: sen get interceptors --id {api_id}"
        )


class NavigationCustomNotFound(NavigationError):
    def __init__(self, custom_id: int):
        super().__init__(
            f"Custom interceptor {custom_id} não encontrado neste Manager. "
            "O id aparece em `customInterceptorId` na saída de sen get interceptors."
        )


class NavigationPlatformError(NavigationError):
    """Falha da plataforma sem leitura de negócio; recebe a mensagem da família."""
