from unittest.mock import patch

import pytest
import typer

from apiops_orchestrator.adapters.outbound.http.orchestrator_auth_api.orchestrator_auth_adapter import (
    OrchestratorAuthAdapter,
    build_login_url,
)
from apiops_orchestrator.config.settings import Settings

MOCK_PATH = "apiops_orchestrator.infrastructure.utils.http_client.HttpClient.request"


def _fake_settings(
    auth_host: str | None = None,
    host: str | None = "https://plat.example.com",
    login_path: str | None = "/cli-2/orq-auth/v1/oauth2/token",
):
    settings = Settings.__new__(Settings)
    object.__setattr__(settings, "AUTH_HOST", auth_host)
    object.__setattr__(settings, "HOST", host)
    object.__setattr__(settings, "AUTH_LOGIN_PATH", login_path)
    return settings


@pytest.fixture
def adapter():
    return OrchestratorAuthAdapter(settings=_fake_settings(auth_host="https://auth.example.com"), max_retries=3)


def test_build_login_url_uses_auth_host_exclusively():
    url = build_login_url(_fake_settings(auth_host="https://auth.example.com"))
    assert url == "https://auth.example.com/cli-2/orq-auth/v1/oauth2/token"


def test_build_login_url_never_falls_back_to_platform_host():
    with pytest.raises(RuntimeError):
        build_login_url(_fake_settings(auth_host=None, host="https://plat.example.com"))


def test_build_login_url_prefers_auth_host_override():
    url = build_login_url(_fake_settings(auth_host="https://hmg.example.com"))
    assert url == "https://hmg.example.com/cli-2/orq-auth/v1/oauth2/token"


def test_build_login_url_accepts_full_path_override():
    url = build_login_url(
        _fake_settings(
            auth_host="https://qa.example.com/", login_path="other/auth/token"
        )
    )
    assert url == "https://qa.example.com/other/auth/token"


def test_build_login_url_raises_without_any_host():
    with pytest.raises(RuntimeError):
        build_login_url(_fake_settings(host=None))


@patch(MOCK_PATH)
def test_login_posts_basic_header_and_payload_intact(mock_request, adapter):
    mock_request.return_value = {"access_token": "T", "token_type": "Bearer"}
    credential = "dXNlcjpzZWNyZXQ="
    response = adapter.login(credential)

    assert response == {"access_token": "T", "token_type": "Bearer"}
    kwargs = mock_request.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "https://auth.example.com/cli-2/orq-auth/v1/oauth2/token"
    assert kwargs["headers"]["Authorization"] == f"Basic {credential}"
    assert kwargs["report_client_errors"] is False
    assert kwargs["json"] == {"grantType": "client_credentials", "scope": "apis/all"}


@patch(MOCK_PATH)
def test_login_surfaces_http_client_exit_for_4xx(mock_request, adapter):
    mock_request.side_effect = typer.Exit(code=1)
    with pytest.raises(typer.Exit):
        adapter.login("cred")


@patch(MOCK_PATH)
def test_login_surfaces_generic_failure_for_5xx_after_retries(mock_request, adapter):
    mock_request.side_effect = Exception("Failed after 3 retries, with 500 status")
    with pytest.raises(Exception):
        adapter.login("cred")
