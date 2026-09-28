from unittest.mock import Mock, patch
import pytest

from apiops_orchestrator.adapters.outbound.http.user_management_api.sensedia_authentication_adapter import \
    SensediaAuthenticationAdapter
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.infrastructure.exceptions.http_client_exceptions import (
    HttpClient4xxError,
)

MOCK_PATH = "apiops_orchestrator.infrastructure.utils.http_client.HttpClient.request"

@pytest.fixture
def adapter():
    fake_settings = Mock(spec=Settings)
    fake_settings.OAUTH_CLIENT_ID = "fake_id"
    fake_settings.OAUTH_CLIENT_SECRET = "fake_secret"
    fake_settings.HOST = "http://fakehost"
    return SensediaAuthenticationAdapter(base_path="api-manager", max_retries=3, settings=fake_settings)

@patch(MOCK_PATH)
def test_authenticate_success(mock_request, adapter):
    mock_request.return_value = {"access_token": "TOKEN123"}
    token = adapter.authenticate()
    assert token == "TOKEN123"
    assert mock_request.called


@patch(MOCK_PATH)
def test_authenticate_propagates_typed_4xx(mock_request, adapter):
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.url = "http://fake"
    mock_response.json.return_value = {"message": "unauthorized"}
    mock_request.side_effect = HttpClient4xxError(
        status_code=401, title="Unauthorized", detail="unauthorized", url="http://fake"
    )

    with pytest.raises(HttpClient4xxError) as excinfo:
        adapter.authenticate()

    assert excinfo.value.status_code == 401