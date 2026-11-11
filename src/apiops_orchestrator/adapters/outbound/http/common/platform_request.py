"""Platform call shared by the Manager and Governance adapters.

Transport failures from the `HttpClient` never cross this boundary: the port
consumer only sees the typed signals of `manager_api_port`.
"""

import json
import logging
from typing import Any, Callable, Dict, List

from requests.exceptions import RequestException

from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiResponseTooLargeError,
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)
from apiops_orchestrator.infrastructure.exceptions.http_client_exceptions import (
    HttpClient4xxError,
    HttpClientServerError,
)
from apiops_orchestrator.infrastructure.utils.http_client import HttpClient

logger = logging.getLogger(__name__)

RejectionSignal = Callable[[HttpClient4xxError, Dict[str, Any]], ManagerApiTransportRejectedError]


def platform_error_items(body: Any) -> List[Any]:
    """Unwraps the platform error envelope into its items (V-23 §1).

    The Manager answers `{"errors": [{"message": "<JSON as a string>"}]}`; the
    inner JSON carries `messages[]` and `path`. Each item is the parsed inner
    dict when the string is JSON, or the raw string otherwise.
    """
    if not isinstance(body, dict):
        return []
    items: List[Any] = [body]
    for error in body.get("errors") or []:
        if not isinstance(error, dict):
            continue
        message = error.get("message")
        if not isinstance(message, str):
            continue
        try:
            items.append(json.loads(message))
        except ValueError:
            items.append(message)
    return items


def platform_messages(body: Any) -> List[str]:
    """Human-readable reasons the platform gave, in order and without repeats."""
    found: List[str] = []
    for item in platform_error_items(body):
        if isinstance(item, str):
            candidates: List[Any] = [item]
        elif isinstance(item, dict):
            candidates = list(item.get("messages") or [])
            if item is not body or not candidates:
                candidates.append(item.get("message"))
        else:
            continue
        for candidate in candidates:
            text = candidate.strip() if isinstance(candidate, str) else ""
            if text and text not in found:
                found.append(text)
    return found


def rejection_signal(
    exc: HttpClient4xxError, fields: Dict[str, Any]
) -> ManagerApiTransportRejectedError:
    """Signal of a 4xx: a too-large response (413) or a refusal."""
    if exc.status_code == 413:
        return ManagerApiResponseTooLargeError(**fields)
    return ManagerApiTransportRejectedError(**fields)


def bearer_headers(token: str) -> Dict[str, str]:
    """Headers of an authenticated JSON call."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def platform_request(
    method: str,
    url: str,
    *,
    headers: Dict[str, str],
    max_retries: int,
    log_prefix: str,
    rejection: RejectionSignal = rejection_signal,
    **kwargs: Any,
) -> Any:
    """Sends the call and turns transport failures into port signals."""
    try:
        return HttpClient.request(
            method=method,
            url=url,
            headers=headers,
            max_retries=max_retries,
            **kwargs,
        )
    except HttpClient4xxError as exc:
        # INFO on purpose: with logging not wired, WARNING+ falls into
        # logging.lastResort and would leak diagnostics to the user's stderr.
        logger.info(
            "%s.transport.rejected status_code=%s code=%s request_id=%s",
            log_prefix,
            exc.status_code,
            exc.code,
            exc.request_id,
        )
        fields = dict(
            status_code=exc.status_code,
            title=exc.title,
            code=exc.code,
            request_id=exc.request_id,
            messages=platform_messages(exc.body),
        )
        raise rejection(exc, fields) from exc
    except HttpClientServerError as exc:
        logger.info("%s.transport.unavailable reason=server_error", log_prefix)
        raise ManagerApiTransportUnavailableError(str(exc)) from exc
    except RequestException as exc:
        logger.info("%s.transport.unavailable reason=connection_failure", log_prefix)
        raise ManagerApiTransportUnavailableError(
            "Platform connection failed or timed out"
        ) from exc
