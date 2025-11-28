import logging
import time
import requests

from apiops_orchestrator.infrastructure.observability.logging import set_status, set_span_id, clear_operation_context, \
    log_duration


class RetryUtil:

    @staticmethod
    def http_request(
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
        with log_duration(__name__):
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"Requesting {method} {url}")
                    response = requests.request(method, url, headers=headers, **kwargs)

                    if 500 <= response.status_code < 600:
                        logger.warning(f"Status {response.status_code} - Attempt {attempt}/{max_retries}")

                        if attempt < max_retries:
                            time.sleep(interval)
                            continue
                        else:
                            set_status("FAILURE")
                            logger.error(f"Error status: {response.status_code} - After {max_retries} tries")
                            raise Exception(f"Failed after {max_retries} tries, with {response.status_code} status")

                    response.raise_for_status()
                    try:
                        set_status("SUCCESS")
                        clear_operation_context()
                        return response.json()
                    except ValueError:
                        set_status("FAILURE")
                        clear_operation_context()
                        raise

                except requests.exceptions.RequestException as e:
                    set_status("FAILURE")
                    logger.error(f"Error: {e}")
                    clear_operation_context()
                    raise
