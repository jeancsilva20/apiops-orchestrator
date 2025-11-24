import pytest
from unittest.mock import patch, Mock
import requests
from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import ManagerApiAdapter
from apiops_orchestrator.config.settings import Settings


@pytest.fixture
def mock_settings():
    settings = Mock(spec=Settings)
    settings.HOST = "http://urltest.com"
    return settings


def test_get_api_calls_requests_correctly(mock_settings):
    token = "password123"
    api_id = 123
    base_path = "/api-manager/api/v3/"
    max_retries = 3

    adapter = ManagerApiAdapter(
        token=token,
        base_path=base_path,
        max_retries=max_retries,
        api_id=api_id,
        settings=mock_settings
    )

    expected_response = {"id": "123", "status": "ok"}

    with patch("requests.request") as mock_request:
        mock_response_obj = Mock()
        mock_response_obj.json.return_value = expected_response
        mock_response_obj.status_code = 200
        mock_request.return_value = mock_response_obj

        result = adapter.get_api_by_id()

        assert result == expected_response
        expected_url = "http://urltest.com/api-manager/api/v3/apis/123"
        mock_request.assert_called_once_with(
            "GET",
            expected_url,
            headers={
                "Authorization": "Bearer password123",
                "Content-Type": "application/json"
            }
        )


def test_get_api_re_raises_exception(mock_settings):
    adapter = ManagerApiAdapter(
        token="token",
        base_path="/base/",
        max_retries=1,
        api_id=123,
        settings=mock_settings
    )

    with patch("requests.request") as mock_request:
        mock_response_obj = Mock()
        mock_response_obj.status_code = 404
        error = requests.exceptions.HTTPError("404 Client Error")
        mock_response_obj.raise_for_status.side_effect = error
        mock_request.return_value = mock_response_obj

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

    with patch("requests.request") as mock_request:
        mock_response_obj = Mock()
        mock_response_obj.json.return_value = expected_response
        mock_response_obj.status_code = 200
        mock_request.return_value = mock_response_obj

        result = adapter.get_custom_interceptor_by_id(8)

        assert result == expected_response
        expected_url = "http://urltest.com/api-manager/api/v3/custom-interceptors/8"
        mock_request.assert_called_once_with(
            "GET",
            expected_url,
            headers={
                "Authorization": "Bearer password123",
                "Content-Type": "application/json"
            }
        )

def test_get_custom_interceptor_by_id_not_found(mock_settings):
    adapter = ManagerApiAdapter(
        token="token",
        base_path="/base/",
        max_retries=1,
        api_id=123,
        settings=mock_settings
    )

    with patch("requests.request") as mock_request:
        mock_response_obj = Mock()
        mock_response_obj.status_code = 404
        error = requests.exceptions.HTTPError("404 Client Error")
        mock_response_obj.raise_for_status.side_effect = error
        mock_request.return_value = mock_response_obj

        with pytest.raises(requests.exceptions.HTTPError):
            adapter.get_custom_interceptor_by_id(8)

def test_get_custom_interceptor_by_id_retries(mock_settings):
    adapter = ManagerApiAdapter(
        token="token",
        base_path="/base/",
        max_retries=3,
        api_id=123,
        settings=mock_settings
    )

    with patch("requests.request") as mock_request:
        mock_response_obj = Mock()
        mock_response_obj.status_code = 500
        mock_request.return_value = mock_response_obj

        with patch("time.sleep") as mock_sleep:
            mock_sleep.return_value = None

            with pytest.raises(Exception):
                adapter.get_custom_interceptor_by_id(8)

        assert mock_request.call_count == 3