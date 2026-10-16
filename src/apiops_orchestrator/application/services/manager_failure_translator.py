"""Single classification of Manager port signals into user-facing families.

Every command that queries the Manager (`sen list`, `sen completeness`, the
template ruler of `sen validate`) used to translate failures on its own, and
they drifted apart: a `413` was shown as "faça `sen login`" in one place and
as a raw `HTTP 413: Invalid Request` in another. This module owns the family
and its PT-BR text; each command keeps its own exception class and exit code,
overriding only where it has business meaning (e.g. a revision not found).

Diagnostics (status, platform error code, request id) are logged by the
adapter where the refusal is born and never reach these messages. The texts
themselves live in `application/exceptions/manager_failure_messages.py`.
"""

from typing import Optional

from apiops_orchestrator.application.enums.manager_failure_kind_enum import (
    ManagerFailureKind,
)
from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    FORBIDDEN_MESSAGE,
    INTERNAL_ERROR_MESSAGE,
    UNAUTHORIZED_MESSAGE,
    UNAVAILABLE_MESSAGE,
)
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiError,
    ManagerApiTransportRejectedError,
)

_MESSAGES = {
    ManagerFailureKind.UNAUTHORIZED: UNAUTHORIZED_MESSAGE,
    ManagerFailureKind.FORBIDDEN: FORBIDDEN_MESSAGE,
    ManagerFailureKind.INTERNAL: INTERNAL_ERROR_MESSAGE,
    ManagerFailureKind.UNAVAILABLE: UNAVAILABLE_MESSAGE,
}

_REJECTION_KINDS = {
    401: ManagerFailureKind.UNAUTHORIZED,
    403: ManagerFailureKind.FORBIDDEN,
    404: ManagerFailureKind.NOT_FOUND,
}


def classify_manager_failure(exc: ManagerApiError) -> ManagerFailureKind:
    """Family of a port signal: 401/403/404 by status, any other 4xx is internal.

    Anything that is not a rejection (connection failure, exhausted 5xx) means
    the Manager could not answer at all.
    """
    if isinstance(exc, ManagerApiTransportRejectedError):
        return _REJECTION_KINDS.get(exc.status_code, ManagerFailureKind.INTERNAL)
    return ManagerFailureKind.UNAVAILABLE


def manager_failure_message(kind: ManagerFailureKind) -> Optional[str]:
    """Standard PT-BR text of a family.

    `NOT_FOUND` has no standard text on purpose: what was not found (an API, a
    revision, a template) is only known by the command, which must word it.
    """
    return _MESSAGES.get(kind)
