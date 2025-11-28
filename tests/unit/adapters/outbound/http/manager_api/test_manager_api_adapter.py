import pytest
from unittest.mock import patch, Mock
import requests
from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import ManagerApiAdapter
from apiops_orchestrator.config.settings import Settings

MOCK_PATH = "apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter.RetryUtil.http_request"

@pytest.fixture
def mock_settings():
    settings = Mock(spec=Settings)
    settings.HOST = "http://urltest.com"
    return settings


def test_get_api_calls_retry_util_correctly(mock_settings):
    token = "password123"
    api_id = 123
    adapter = ManagerApiAdapter(
        token=token,
        base_path="/api-manager/api/v3/",
        max_retries=3,
        api_id=api_id,
        settings=mock_settings
    )

    expected_response = {"id": "123", "status": "ok"}

    with patch(MOCK_PATH) as mock_retry:
        mock_retry.return_value = expected_response

        result = adapter.get_api_by_id()

        assert result == expected_response
        mock_retry.assert_called_once_with(
            method="GET",
            url="http://urltest.com/api-manager/api/v3/apis/123",
            headers={
                "Authorization": "Bearer password123",
                "Content-Type": "application/json"
            },
            max_retries=3
        )


def test_get_api_re_raises_exception(mock_settings):
    adapter = ManagerApiAdapter(
        token="token",
        base_path="/base/",
        max_retries=1,
        api_id=123,
        settings=mock_settings
    )
    with patch(MOCK_PATH) as mock_retry:
        error = requests.exceptions.HTTPError("404 Client Error")
        mock_retry.side_effect = error

        with pytest.raises(requests.exceptions.HTTPError):
            adapter.get_api_by_id()

def test_get_custom_interceptor_by_id_success(mock_settings):
    adapter = ManagerApiAdapter(
        token="password123",
        base_path="/api-manager/api/v3/",
        max_retries=3,
        api_id=123,
        settings=mock_settings
    )

    expected_response = {"id": "8", "name": "test-interceptor", "script": "ok"}

    with patch(MOCK_PATH) as mock_retry:
        mock_retry.return_value = expected_response

        result = adapter.get_custom_interceptor_by_id(8)

        assert result == expected_response

        mock_retry.assert_called_once_with(
            method="GET",
            url="http://urltest.com/api-manager/api/v3/custom-interceptors/8",
            headers={
                "Authorization": "Bearer password123",
                "Content-Type": "application/json"
            },
            max_retries=3
        )