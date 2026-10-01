import logging
import time

import requests
from requests.exceptions import HTTPError, RequestException
from apiops_orchestrator.adapters.outbound.http.common.http_error_mapper import HttpErrorMapper
from apiops_orchestrator.infrastructure.observability.logging import set_status, set_span_id, clear_operation_context, \
    log_duration
from apiops_orchestrator.infrastructure.exceptions.http_client_exceptions import (
    HttpClient4xxError,
    HttpClientServerError,
)


class HttpClient:

    @staticmethod
    def request(
            method: str,
            url: str,
            *,
            headers=None,
            max_retries: int = 3,
            interval: float = 5,
            return_headers: bool = False,
            **kwargs,
    ):
        """
        Send an http request and retry in case of 5xx errors.

        Cliente compartilhado NEUTRO de framework: nunca imprime no stdout/
        stderr do CLI e nunca levanta `typer.Exit`. Falhas previsíveis são
        sinalizadas por exceções tipadas deste módulo de exceções — a
        apresentação/tradução é responsabilidade de quem chama:

        - `HttpClient4xxError`: 4xx carregando o problema mapeado em
          RFC 7807 (`status_code`, `title`, `detail`, `url`);
        - `HttpClientServerError`: 5xx persistente após esgotar os retries;
        - outras `RequestException` (rede/timeout) propagam sem tradução.

        return_headers: default False devolve apenas o payload (contrato
        histórico); True devolve (payload, headers-lowercase) — para when the
        SERVER speaks through headers (ex.: api-finder `count`/`content-range`
        = total do universo). Sao headers da propria resposta, logo um fetch
        e tanto — so muda o formato de retorno.
        """
        logger = logging.getLogger(__name__)
        set_span_id()
        total_attempts = max_retries + 1

        with log_duration(__name__):
            for attempt in range(1, total_attempts + 1):
                try:
                    logger.info(f"Requesting {method} {url}")
                    if 'timeout' not in kwargs:
                        kwargs['timeout'] = 30

                    response = requests.request(method, url, headers=headers, **kwargs)

                    if 500 <= response.status_code < 600:
                        logger.warning(f"Status {response.status_code} - Attempt {attempt}/{total_attempts}")

                        if attempt < total_attempts:
                            time.sleep(interval)
                            continue
                        else:
                            set_status("FAILURE")
                            logger.error(f"Server Error: {response.status_code} - After {max_retries} retries")
                            raise HttpClientServerError(
                                f"Failed after {max_retries} retries, with {response.status_code} status"
                            )
                    response.raise_for_status()
                    try:
                        response_headers = {
                            key.lower(): value for key, value in response.headers.items()
                        }
                        set_status("SUCCESS")
                        clear_operation_context()
                        payload = response.json()
                        if return_headers:
                            return payload, response_headers
                        return payload
                    except ValueError:
                        if return_headers:
                            if response.text:
                                return response.text, {}
                            return {}, {}
                        if response.text:
                            return response.text
                        return {}

                except RequestException as e:
                    set_status("FAILURE")

                    if isinstance(e, HTTPError) and e.response is not None:
                        status_code = e.response.status_code

                        if 400 <= status_code < 500:
                            logger.debug(f"Client Error ({status_code}): {e}")

                            problem = HttpErrorMapper.map_to_rfc7807(e.response)
                            clear_operation_context()
                            raise HttpClient4xxError(
                                status_code=status_code,
                                title=str(problem.get("title", "Client Error")),
                                detail=str(problem.get("detail", "")),
                                url=str(problem.get("instance", e.response.url)),
                            ) from e
                        logger.error(f"HTTP Error: {e}")
                    else:
                        logger.error(f"Connection Error: {e}")

                    clear_operation_context()
                    raise
