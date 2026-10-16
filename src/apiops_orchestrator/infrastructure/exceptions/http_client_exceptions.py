"""Exceções neutras de transporte do cliente HTTP compartilhado.

Contrato: nenhuma exceção daqui carrega framework de inbound (typer/rich),
não imprime na tela e não decide UX — o HttpClient apenas sinaliza a falha
de forma tipada; quem chama traduz/apresenta na sua borda.
"""

from typing import Any


class HttpClientError(Exception):
    """Base para falhas previsíveis reportadas pelo HttpClient compartilhado."""


class HttpClient4xxError(HttpClientError):
    """Servidor respondeu 4xx (pedido rejeitado pelo lado cliente/remoto).

    Carrega o problema já mapeado para RFC 7807 (`HttpErrorMapper`): quem
    possui o próprio UX do erro consome os campos estruturados
    (`status_code`, `title`, `detail`, `url`); quem não possui pode
    apresentar `str(exc)` diretamente.

    `code` (código de erro do corpo) e `request_id` (id da requisição no
    gateway da plataforma) existem só para diagnóstico em log — nunca para
    a saída do usuário. `body` é o corpo já parseado, para o adapter que
    precisa ler o envelope próprio da plataforma.
    """

    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str,
        url: str | None = None,
        code: str | None = None,
        request_id: str | None = None,
        body: Any = None,
    ) -> None:
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.url = url
        self.code = code
        self.request_id = request_id
        self.body = body
        super().__init__(f"{title} ({status_code}): {detail}")


class HttpClientServerError(HttpClientError):
    """5xx persistente após esgotar todas as tentativas de retry."""
