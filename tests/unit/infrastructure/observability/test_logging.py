import json
import logging
import threading
import pytest
import uuid
from io import StringIO
from unittest.mock import MagicMock, patch
from enum import Enum


# --- MOCKS FOR EXTERNAL DEPENDENCIES---
class MockLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARNING"
    ERROR = "ERROR"
    FATAL = "CRITICAL"


class MockStatus(Enum):
    IN_PROGRESS = "IN PROGRESS"


# MOCK sys.modules
with patch.dict('sys.modules', {
    'apiops_orchestrator.domain.services.logging_level_enum': MagicMock(Level=MockLevel),
    'apiops_orchestrator.domain.services.logging_status_enum': MagicMock(Status=MockStatus),
    'apiops_orchestrator.config.settings': MagicMock(),
}):
    import apiops_orchestrator.infrastructure.observability.logging as log_lib


@pytest.fixture(autouse=True)
def clean_context_fixture():
    log_lib.clear_context()
    yield
    log_lib.clear_context()


def test_set_and_get_context_data():
    """Tests if set_api_info and set_default_data keep data from local thread."""
    log_lib.set_default_data()
    log_lib.set_api_info(api_id=123, customer="test client")
    log_lib.set_span_id()

    assert hasattr(log_lib._log_context, "trace_id")
    assert log_lib._log_context.api_id == 123
    assert log_lib._log_context.customer == "test client"


def test_clear_context():
    """Tests if clear_context removes all variables"""
    log_lib.set_api_info(1, "client")
    log_lib.set_default_data()

    assert hasattr(log_lib._log_context, "customer")

    log_lib.clear_context()

    assert not hasattr(log_lib._log_context, "customer")
    assert not hasattr(log_lib._log_context, "api_id")
    assert not hasattr(log_lib._log_context, "trace_id")


def test_context_filter_injection():
    """
    Tests whether the ContextFilter retrieves the thread data and places it in the LogRecord.
    """
    log_lib.set_api_info(api_id=999, customer="big corp")
    log_lib.set_span_id()

    record = logging.LogRecord(
        name="test_logger", level=logging.INFO, pathname="test.py", lineno=10,
        msg="test message", args=(), exc_info=None
    )

    filter_obj = log_lib.ContextFilter()
    filter_obj.filter(record)

    assert record.api_id == 999
    assert record.customer == "big corp"


def test_json_formatter_output():
    """Tests whether JsonFormatter generates JSON with the correct structure."""
    record = logging.LogRecord(
        name="test_service", level=logging.INFO, pathname="test.py", lineno=10,
        msg="finished processing", args=(), exc_info=None
    )
    record.trace_id = str(uuid.uuid4())
    record.api_id = 555
    record.customer = "Valid Customer"
    record.span_id = "span-xyz"
    record.duration = 150.5

    formatter = log_lib.JsonFormatter()
    json_output = formatter.format(record)

    data = json.loads(json_output)

    assert data["message"] == "finished processing"
    assert data["level"] == "INFO"
    assert data["duration"] == 150.5

    assert data["context"]["api_id"] == 555
    assert data["context"]["customer"] == "Valid Customer"
    assert data["context"]["span_id"] == "span-xyz"


def test_log_duration_context_manager():
    """Tests whether the context manager log_duration calculates the time."""
    with patch("logging.getLogger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        with log_lib.log_duration("test_operation"):
            # Simulates fast processing (do not use time.sleep to avoid delaying tests,
            # just check if duration is set, or mock time.perf_counter if you need precision)
            pass

        mock_logger.info.assert_called_once()
        args, _ = mock_logger.info.call_args
        assert "Execution of test_operation finished" in args[0]