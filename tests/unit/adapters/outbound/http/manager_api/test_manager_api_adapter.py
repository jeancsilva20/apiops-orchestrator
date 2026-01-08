import pytest
from unittest.mock import patch, Mock
import requests
import typer
from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import ManagerApiAdapter
from apiops_orchestrator.config.settings import Settings

MOCK_PATH = "apiops_orchestrator.infrastructure.utils.http_client.HttpClient.request"

@pytest.fixture
def mock_settings():
    settings = Mock(spec=Settings)
    settings.HOST = "http://urltest.com"
    return settings


def test_get_api_calls_retry_util_correctly(mock_settings):
    token = "password123"
    api_id = 123
    adapter = ManagerApiAdapter(token=token, base_path="/api-manager/api/v3/", max_retries=3, api_id=api_id,
                                settings=mock_settings)
    expected_response = {"id": "123", "status": "ok"}

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = expected_response
        result = adapter.get_api_by_id()

        assert result == expected_response
        mock_request.assert_called_once_with(
            method="GET",
            url="http://urltest.com/api-manager/api/v3/apis/123",
            headers={"Authorization": "Bearer password123", "Content-Type": "application/json"},
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
    with patch(MOCK_PATH) as mock_request:
        mock_request.side_effect = typer.Exit(code=1)

        with pytest.raises(typer.Exit) as excinfo:
            adapter.get_api_by_id()

        assert excinfo.value.exit_code == 1

def test_get_custom_interceptor_by_id_success(mock_settings):
    adapter = ManagerApiAdapter(token="password123", base_path="/api-manager/api/v3/", max_retries=3, api_id=123,
                                settings=mock_settings)
    api_response = {"id": "8", "name": "test-interceptor", "script": "ok"}

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = api_response
        result = adapter.get_custom_interceptor_by_id(8)

        assert result == api_response