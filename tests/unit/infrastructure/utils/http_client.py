import logging
import pytest
from unittest.mock import patch, MagicMock
from apiops_orchestrator.infrastructure.observability import logging as log_lib

@pytest.fixture(autouse=True)
def reset_context():
    log_lib.clear_operation_context()
    yield
    log_lib.clear_operation_context()


def test_set_and_get_context_data():

    log_lib.set_default_data()
    log_lib.set_api_info(api_id=123, customer="test client")
    log_lib.set_span_id()

def test_context_filter_injection():
    log_lib.set_api_info(api_id=999, customer="big corp")
    log_lib.set_span_id()

    record = logging.LogRecord(
        name="test_logger", level=logging.INFO, pathname=__file__, lineno=10,
        msg="test message", args=(), exc_info=None
    )

    filter_ = log_lib.ContextFilter()
    result = filter_.filter(record)


    assert result is True
    assert getattr(record, "api_id", None) == 999
    assert getattr(record, "customer", None) == "big corp"
    assert getattr(record, "span_id", None) is not None


def test_log_duration_context_manager():
    with patch("apiops_orchestrator.infrastructure.observability.logging.getLogger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        with log_lib.log_duration("test_operation"):
            pass

        mock_logger.info.assert_called_once()

        args, _ = mock_logger.info.call_args
        assert "test_operation" in args[0]


def test_clear_operation_context():
    log_lib.set_api_info(api_id=555, customer="tobe deleted")
    log_lib.set_status("FAILURE")
    log_lib.clear_operation_context()


    record = logging.LogRecord(
        name="test_logger", level=logging.INFO, pathname=__file__, lineno=10,
        msg="test", args=(), exc_info=None
    )
    filter_ = log_lib.ContextFilter()
    filter_.filter(record)

    assert getattr(record, "api_id", None) is None
    assert getattr(record, "status", None) is None