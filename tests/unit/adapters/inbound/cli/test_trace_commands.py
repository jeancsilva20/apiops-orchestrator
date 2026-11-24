"""Trace e analytics: `sen list calls`, `sen get trace`, `sen get analytics`.

Recortado de `test_navigation_commands.py`, que chegou a 916 linhas cobrindo 36
comandos. Os corpos sao os mesmos; o que mudou foi a casa e a origem dos
helpers, que vieram para `tests/sen_support/`.
"""

import json
from unittest.mock import MagicMock
from sen_support.cli_invoke import invocar_navegacao as _invoke




# --------------------------------------------------------------------------- trace e analytics (sen list calls, sen get trace, sen get analytics)


def _call_doc(**overrides):
    base = {
        "traceId": "5ed84ead", "when": "2026-11-01T19:43:16.506Z", "api": {"id": 400, "name": "Orchestrator Auth API"}, "revisionId": 8948,
        "resource": {"id": 1, "name": "Token"}, "operation": {"id": 2, "name": "POST /oauth2/token"}, "environment": {"id": 9, "name": "HMG"},
        "method": "POST", "uri": "https://gw/token", "status": 401, "targetStatus": None, "result": "error", "errorType": "client",
        "durationMillis": 12, "gatewayMillis": 12, "targetMillis": 0, "app": "CI", "appDeveloper": "d", "tokenOwner": None, "caller": "1.2.3.4",
        "requestBytes": 0, "responseBytes": 93, "cache": None, "billing": False,
    }
    base.update(overrides)
    return base


def test_list_calls_table_and_validation():
    service = MagicMock()
    service.calls.return_value = {"window": {"begin": "2026-10-31T21:00:00", "end": "2026-11-01T21:00:00", "clamped": True}, "filters": {}, "page": 1, "pageSize": 20, "total": 23, "calls": [_call_doc()]}
    result = _invoke(["list", "calls", "--api", "400", "--since", "7d", "--errors", "--limit", "20"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "encolhida ao limite de 7 dias" in out and "23 chamada(s)" in out and "página 1 de 2" in out
    assert "5ed84ead" in out and "401" in out and "12 ms" in out and "sen get trace --id" in out
    service.calls.assert_called_once_with(since="7d", until=None, api_id=400, environment_id=None, uri=None, errors=True, status_from=None, status_to=None, operation_id=None, revision_id=None, page=1, limit=20)

    assert _invoke(["list", "calls", "--limit", "0"], service).exit_code == 1
    assert _invoke(["list", "calls", "--limit", "501"], service).exit_code == 1
    service.calls.return_value["calls"] = []
    assert "Nenhuma chamada" in _invoke(["list", "calls"], service).output


def test_get_trace_renders_pipeline_and_headers():
    service = MagicMock()
    service.trace.return_value = {
        **_call_doc(),
        "trace": [{"step": 1, "timeMillis": 1, "message": "Found matching route", "data": None}, {"step": 2, "timeMillis": 11, "message": "Token invalid", "data": {"reason": "x"}}],
        "totals": {"steps": 2, "traceMillis": 12},
        "requestHeaders": [{"name": "authorization", "value": "•••••", "masked": True}, {"name": "host", "value": "gw", "masked": False}],
        "responseHeaders": [],
    }
    result = _invoke(["get", "trace", "--id", "5ed84ead"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "PIPELINE 2 passo(s) · 12 ms somados" in out and "Found matching route" in out and '"reason": "x"' in out
    assert "authorization: •••••" in out and "host: gw" in out and "REQUEST HEADERS" in out
    service.trace.assert_called_once_with("5ed84ead", include_headers=True)

    result = _invoke(["get", "trace", "--id", "5ed84ead", "--no-headers", "-o", "json"], service)
    assert json.loads(result.output)["traceId"] == "5ed84ead"
    assert service.trace.call_args.kwargs["include_headers"] is False


def test_get_analytics_renders_summary():
    service = MagicMock()
    service.analytics.return_value = {
        "window": {"begin": "b", "end": "e", "clamped": False}, "filters": {}, "sample": 300, "total": 1459, "sampleCap": 2000,
        "classes": {"2xx": 100, "3xx": 0, "4xx": 200, "5xx": 0, "other": 0}, "errorRate": 0.6667,
        "latencyMillis": {"avg": 5.8, "p50": 4, "p95": 16, "max": 100, "gatewayAvg": 5.8, "targetAvg": 0.0},
        "topStatus": [{"key": 401, "calls": 200}], "topApis": [{"key": "API de Produtos (396)", "calls": 300}],
        "topOperations": [{"key": "GET /certs", "calls": 300}], "topApps": [{"key": "(sem app)", "calls": 300}],
        "topEnvironments": [{"key": "Default", "calls": 300}], "topCallers": [{"key": "34.207.62.58", "calls": 300}],
        "byHour": [{"hour": "2026-11-01T20", "calls": 209}, {"hour": "2026-11-01T21", "calls": 91}],
        "recentErrors": [{"traceId": "t", "when": "w", "method": "GET", "uri": "/certs", "status": 401, "errorType": "client", "app": None}],
    }
    result = _invoke(["get", "analytics", "--since", "6h", "--errors", "--sample", "300", "--top", "3"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "1459 chamada(s)" in out and "erros 66.7%" in out and "p95 16" in out
    assert "API de Produtos (396)" in out and "POR HORA" in out and "ERROS RECENTES" in out and "amostra parcial (300 de 1459)" in out
    service.analytics.assert_called_once_with(since="6h", until=None, api_id=None, environment_id=None, uri=None, errors=True, sample=300, top=3)

    result = _invoke(["get", "analytics", "--api", "400", "-o", "json"], service)
    assert json.loads(result.output)["total"] == 1459
    assert "APIS" not in _invoke(["get", "analytics", "--api", "400"], service).output.split("STATUS")[1].split("OPERAÇÕES")[0]
