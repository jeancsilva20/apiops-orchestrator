from unittest.mock import MagicMock

import pytest
import requests

from apiops_orchestrator.infrastructure.utils.http_client import HttpClient
from apiops_orchestrator.infrastructure.exceptions.http_client_exceptions import (
    HttpClient4xxError,
    HttpClientServerError,
)


def _unauthorized_response():
    response = MagicMock(spec=requests.Response)
    response.status_code = 401
    response.url = "https://api.example.com/cli-2/orq-auth/v1/oauth2/token"
    response.json.return_value = {"message": "Authentication required"}
    response.text = '{"message": "Authentication required"}'

    def raise_for_status():
        raise requests.HTTPError("401 Unauthorized", response=response)

    response.raise_for_status.side_effect = raise_for_status
    return response


def test_4xx_raises_typed_error_with_mapped_rfc7807_details(monkeypatch):
    monkeypatch.setattr(requests, "request", MagicMock(return_value=_unauthorized_response()))

    with pytest.raises(HttpClient4xxError) as excinfo:
        HttpClient.request(method="POST", url="https://api.example.com/token")

    error = excinfo.value
    assert error.status_code == 401
    assert error.title == "Unauthorized"
    assert "Authentication required" in error.detail
    assert error.url == "https://api.example.com/cli-2/orq-auth/v1/oauth2/token"
    assert "Unauthorized (401)" in str(error)
    assert "Authentication required" in str(error)


def test_4xx_never_prints_to_stdout_or_stderr(monkeypatch, capfd):
    """Cliente neutro: a apresentação do problema é de quem chama (UX própria)."""
    monkeypatch.setattr(requests, "request", MagicMock(return_value=_unauthorized_response()))

    with pytest.raises(HttpClient4xxError):
        HttpClient.request(method="POST", url="https://api.example.com/token")

    captured = capfd.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_4xx_raises_the_same_typed_contract_regardless_of_caller(monkeypatch):
    """Não existe mais modo silencioso: todo 4xx sinaliza tipado pela mesma porta."""
    monkeypatch.setattr(requests, "request", MagicMock(return_value=_unauthorized_response()))

    with pytest.raises(HttpClient4xxError):
        HttpClient.request(method="GET", url="https://api.example.com/resource")


def test_5xx_after_retries_raises_typed_server_error(monkeypatch):
    def exhausted_response():
        response = MagicMock(spec=requests.Response)
        response.status_code = 503
        response.url = "https://api.example.com/token"
        return response

    responses = [exhausted_response() for _ in range(3)]
    monkeypatch.setattr(requests, "request", MagicMock(side_effect=responses))

    with pytest.raises(HttpClientServerError) as excinfo:
        HttpClient.request(
            method="POST",
            url="https://api.example.com/token",
            max_retries=2,
            interval=0,
        )

    assert "503" in str(excinfo.value)
    assert "after 2 retries" in str(excinfo.value)


def _too_large_response(headers=None):
    response = MagicMock(spec=requests.Response)
    response.status_code = 413
    response.url = "https://platform.example.com/api-finder/api/v3/apis?_limit=127"
    body = {
        "code": "BACKEND_RESPONSE_TOO_LARGE",
        "message": "Backend response was too large to process safely",
    }
    response.json.return_value = body
    response.text = str(body)
    response.headers = requests.structures.CaseInsensitiveDict(headers or {})

    def raise_for_status():
        raise requests.HTTPError("413", response=response)

    response.raise_for_status.side_effect = raise_for_status
    return response


def test_4xx_carries_body_code_and_platform_request_id(monkeypatch):
    response = _too_large_response({"x-amzn-RequestId": "143ba864-1f30"})
    monkeypatch.setattr(requests, "request", MagicMock(return_value=response))

    with pytest.raises(HttpClient4xxError) as excinfo:
        HttpClient.request(method="GET", url="https://platform.example.com/apis")

    error = excinfo.value
    assert error.status_code == 413
    assert error.code == "BACKEND_RESPONSE_TOO_LARGE"
    assert error.request_id == "143ba864-1f30"
    assert error.title == "BACKEND_RESPONSE_TOO_LARGE"
    assert "too large" in error.detail


def test_4xx_without_request_id_header_degrades_to_none(monkeypatch):
    monkeypatch.setattr(requests, "request", MagicMock(return_value=_too_large_response()))

    with pytest.raises(HttpClient4xxError) as excinfo:
        HttpClient.request(method="GET", url="https://platform.example.com/apis")

    assert excinfo.value.request_id is None
    assert excinfo.value.code == "BACKEND_RESPONSE_TOO_LARGE"


def test_4xx_with_non_json_body_keeps_degrading_to_text(monkeypatch):
    response = _too_large_response()
    response.json.side_effect = ValueError("not json")
    response.text = "<html>Request Entity Too Large</html>"
    monkeypatch.setattr(requests, "request", MagicMock(return_value=response))

    with pytest.raises(HttpClient4xxError) as excinfo:
        HttpClient.request(method="GET", url="https://platform.example.com/apis")

    assert excinfo.value.code is None
    assert "Request Entity Too Large" in excinfo.value.detail
