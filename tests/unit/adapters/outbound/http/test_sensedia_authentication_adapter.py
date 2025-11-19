from unittest.mock import Mock, patch

import pytest

from apiops_orchestrator.adapters.outbound.http.user_management_api.sensedia_authentication_adapter import \
    SensediaAuthenticationAdapter
from apiops_orchestrator.config.settings import Settings

@pytest.fixture
def adapter(monkeypatch):
    fake_settings = Settings.model_construct(
        OAUTH_CLIENT_ID="fake",
        OAUTH_CLIENT_SECRET="fake",
        HOST="fake",
    )

    monkeypatch.setattr("apiops_orchestrator.config.settings", fake_settings)

    return SensediaAuthenticationAdapter(base_path="http://fake",max_retries=3,settings=fake_settings)

@patch("apiops_orchestrator.adapters.outbound.http.user_management_api.sensedia_authentication_adapter.requests.post")
def test_authenticate_success(mock_post, adapter):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "TOKEN123"}

    mock_post.return_value = mock_response
    token = adapter.authenticate()

    mock_post.assert_called_once()
    assert token == "TOKEN123"

@patch("apiops_orchestrator.adapters.outbound.http.user_management_api.sensedia_authentication_adapter.time.sleep")
@patch("apiops_orchestrator.adapters.outbound.http.user_management_api.sensedia_authentication_adapter.requests.post")
def test_authenticate_retries(mock_post, mock_sleep, adapter):
    mock_response = Mock()
    mock_response.status_code = 504
    mock_response.json.return_value = {"error": "error"}

    mock_post.return_value = mock_response

    with pytest.raises(Exception):
        adapter.authenticate()

    assert mock_post.call_count == 3
