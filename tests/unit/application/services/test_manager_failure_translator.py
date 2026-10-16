import pytest

from apiops_orchestrator.application.enums.manager_failure_kind_enum import (
    ManagerFailureKind,
)
from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    INTERNAL_ERROR_MESSAGE,
)
from apiops_orchestrator.application.services.manager_failure_translator import (
    classify_manager_failure,
    manager_failure_message,
)
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiResponseTooLargeError,
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, ManagerFailureKind.UNAUTHORIZED),
        (403, ManagerFailureKind.FORBIDDEN),
        (404, ManagerFailureKind.NOT_FOUND),
        (400, ManagerFailureKind.INTERNAL),
        (409, ManagerFailureKind.INTERNAL),
        (413, ManagerFailureKind.INTERNAL),
        (422, ManagerFailureKind.INTERNAL),
        (429, ManagerFailureKind.INTERNAL),
    ],
)
def test_rejections_classify_by_status(status, expected):
    exc = ManagerApiTransportRejectedError(status_code=status, title="whatever")

    assert classify_manager_failure(exc) is expected


def test_response_too_large_is_an_internal_failure():
    exc = ManagerApiResponseTooLargeError(
        status_code=413, title="BACKEND_RESPONSE_TOO_LARGE", code="BACKEND_RESPONSE_TOO_LARGE"
    )

    assert classify_manager_failure(exc) is ManagerFailureKind.INTERNAL


def test_unavailable_signal_classifies_as_unavailable():
    exc = ManagerApiTransportUnavailableError("connection refused")

    assert classify_manager_failure(exc) is ManagerFailureKind.UNAVAILABLE


def test_internal_message_never_sends_user_to_login_nor_exposes_http_details():
    message = manager_failure_message(ManagerFailureKind.INTERNAL)

    assert message == INTERNAL_ERROR_MESSAGE
    assert "sen login" not in message
    assert "HTTP" not in message and "413" not in message
    assert "erro interno" in message


def test_session_families_orient_login():
    assert "sen login" in manager_failure_message(ManagerFailureKind.UNAUTHORIZED)
    assert "sen login" in manager_failure_message(ManagerFailureKind.FORBIDDEN)


def test_not_found_has_no_standard_text_each_command_words_it():
    assert manager_failure_message(ManagerFailureKind.NOT_FOUND) is None
