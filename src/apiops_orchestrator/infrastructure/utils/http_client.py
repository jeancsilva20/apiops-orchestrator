import logging
import time
import requests
import typer
from requests.exceptions import HTTPError, RequestException
from rich.console import Console
from apiops_orchestrator.adapters.outbound.http.common.http_error_mapper import HttpErrorMapper
from apiops_orchestrator.infrastructure.observability.logging import set_status, set_span_id, clear_operation_context, \
    log_duration

error_console = Console(stderr=True)


class HttpClient:

    @staticmethod
    def request(
            method: str,
            url: str,
            *,
            headers=None,
            max_retries: int = 3,
            interval: float = 5,
            **kwargs,
    ):
        """
        Send an http request and retries in case of 5xx errors

        Returns: JSON or text
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
                            raise Exception(f"Failed after {max_retries} retries, with {response.status_code} status")
                    response.raise_for_status()
                    try:
                        set_status("SUCCESS")
                        clear_operation_context()
                        return response.json()
                    except ValueError:
                        if response.text:
                            return response.text
                        return {}

                except RequestException as e:
                    set_status("FAILURE")

                    if isinstance(e, HTTPError) and e.response is not None:
                        status_code = e.response.status_code

                        if 400 <= status_code < 500:
                            logger.debug(f"Client Error ({status_code}): {e}")

                            rfc_error = HttpErrorMapper.map_to_rfc7807(e.response)

                            error_console.print("\n[bold red] Error in Request:[/bold red]")
                            error_console.print_json(data=rfc_error)

                            clear_operation_context()
                            raise typer.Exit(code=1)
                        else:
                            logger.error(f"HTTP Error: {e}")
                    else:
                        logger.error(f"Connection Error: {e}")

                    clear_operation_context()
                    raise
