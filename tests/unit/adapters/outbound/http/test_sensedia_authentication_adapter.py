from unittest.mock import Mock, patch
import pytest
import typer

from apiops_orchestrator.adapters.outbound.http.user_management_api.sensedia_authentication_adapter import \
    SensediaAuthenticationAdapter
from apiops_orchestrator.config.settings import Settings

MOCK_PATH = "apiops_orchestrator.adapters.outbound.http.user_management_api.sensedia_authentication_adapter.RetryUtil.http_request"

@pytest.fixture
def adapter(monkeypatch):
    fake_settings = Settings.model_construct(
        OAUTH_CLIENT_ID="fake",
        OAUTH_CLIENT_SECRET="fake",
        HOST="fake",
    )
    monkeypatch.setattr("apiops_orchestrator.config.settings", fake_settings)
    return SensediaAuthenticationAdapter(base_path="http://fake", max_retries=3, settings=fake_settings)

@patch(MOCK_PATH)
def test_authenticate_success(mock_retry, adapter):
    mock_retry.return_value = {"access_token": "TOKEN123"}
    token = adapter.authenticate()
    assert token == "TOKEN123"

@patch(MOCK_PATH)
def test_authenticate_propagates_exception(mock_retry, adapter):
    mock_retry.side_effect = Exception("Failed after retries")

    with pytest.raises(typer.Exit) as excinfo:
        adapter.authenticate()

    assert excinfo.value.exit_code == 1