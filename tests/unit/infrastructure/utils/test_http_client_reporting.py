from unittest.mock import MagicMock

import pytest
import requests
import typer

from apiops_orchestrator.infrastructure.utils.http_client import HttpClient


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


def test_report_client_errors_true_keeps_legacy_stdout_report(monkeypatch, capfd):
    monkeypatch.setattr(requests, "request", MagicMock(return_value=_unauthorized_response()))

    with pytest.raises(typer.Exit):
        HttpClient.request(
            method="POST",
            url="https://api.example.com/token",
            report_client_errors=True,
        )

    captured = capfd.readouterr()
    combined = captured.out + captured.err
    assert "Unauthorized" in combined
    assert "401" in combined


def test_report_client_errors_false_suppresses_response_body_report(monkeypatch, capfd):
    monkeypatch.setattr(requests, "request", MagicMock(return_value=_unauthorized_response()))

    with pytest.raises(typer.Exit):
        HttpClient.request(
            method="POST",
            url="https://api.example.com/token",
            report_client_errors=False,
        )

    captured = capfd.readouterr()
    combined = captured.out + captured.err
    assert "Unauthorized" not in combined
    assert "Authentication required" not in combined
    assert '"status"' not in combined


def test_report_client_errors_defaults_to_true(monkeypatch, capfd):
    monkeypatch.setattr(requests, "request", MagicMock(return_value=_unauthorized_response()))

    with pytest.raises(typer.Exit):
        HttpClient.request(method="POST", url="https://api.example.com/token")

    captured = capfd.readouterr()
    combined = captured.out + captured.err
    assert "Unauthorized" in combined
