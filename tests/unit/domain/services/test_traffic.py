"""Trace de chamadas e analytics: janela, chamadas sem credencial, pipeline, agregações."""

import json
from datetime import datetime, timezone

import pytest

from apiops_orchestrator.domain.services import traffic

NOW = datetime(2026, 11, 1, 21, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- janela


def test_window_defaults_to_last_24h():
    begin, end, info = traffic.window(None, None, now=NOW)
    assert (begin, end) == ("2026-10-31T21:00:00", "2026-11-01T21:00:00")
    assert info == {"begin": begin, "end": end, "clamped": False}


@pytest.mark.parametrize(
    "since,until,expected_begin,expected_end,clamped",
    [
        ("6h", None, "2026-11-01T15:00:00", "2026-11-01T21:00:00", False),
        ("30m", "10m", "2026-11-01T20:30:00", "2026-11-01T20:50:00", False),
        ("2026-10-30", "2026-10-31", "2026-10-30T00:00:00", "2026-10-31T00:00:00", False),
        ("2026-10-30T10:30:00", "2026-10-30T11:00", "2026-10-30T10:30:00", "2026-10-30T11:00:00", False),
        ("2026-10-30T10:30:00Z", None, "2026-10-30T10:30:00", "2026-11-01T21:00:00", False),
        ("30d", None, "2026-10-25T21:01:00", "2026-11-01T21:00:00", True),  # limite de 7 dias da rota
        ("2026-10-01", "2026-10-05", "2026-10-25T21:01:00", "2026-10-05T00:00:00", True),  # piso da plataforma
    ],
)
def test_window_formats_and_clamping(since, until, expected_begin, expected_end, clamped):
    begin, end, info = traffic.window(since, until, now=NOW)
    assert (begin, end, info["clamped"]) == (expected_begin, expected_end, clamped)


def test_window_rejects_empty_or_invalid():
    with pytest.raises(ValueError):
        traffic.window("1h", "2h", now=NOW)
    with pytest.raises(ValueError) as info:
        traffic.window("ontem", None, now=NOW)
    assert "momento inválido" in str(info.value)


def test_status_filters():
    assert traffic.status_filters() == {}
    assert traffic.status_filters(errors=True) == {"httpStatusFrom": "400", "httpStatusTo": "599"}
    assert traffic.status_filters(status_from=500) == {"httpStatusFrom": "500", "httpStatusTo": "599"}
    assert traffic.status_filters(status_to=299) == {"httpStatusFrom": "100", "httpStatusTo": "299"}
    assert traffic.status_filters(errors=True, status_from=500, status_to=503) == {"httpStatusFrom": "500", "httpStatusTo": "503"}


# --------------------------------------------------------------------------- chamadas


def _call(**overrides):
    base = {
        "id": "t1", "traceId": "t1", "requestID": "t1", "apiId": 400, "apiName": "Orchestrator Auth API", "revisionId": 8948,
        "resourceId": 8949, "resourceName": "Token", "operationId": 8953, "operationName": "POST /oauth2/token",
        "environmentId": 9, "environmentName": "HMG-APIOPS", "method": "POST", "uri": "https://gw/cli-2/orq-auth/v1/oauth2/token",
        "resultStatus": 200, "targetResultStatus": 200, "typeStatus": "success", "typeError": None,
        "durationMillis": 1500, "gatewayDurationMillis": 1300, "targetDurationMillis": 200,
        "appName": "CI", "appDeveloper": "d@x", "accessTokenOwner": "o@x", "callerAddress": "1.2.3.4",
        "requestPayload": 10, "responsePayload": 20, "cache": False, "billing": True,
        "receivedOnDate": "2026-11-01T19:43:16.506Z", "callDate": "2026-11-01T19:43:16.506+00:00",
        "accessToken": "SECRET-TOKEN", "appSecret": "SECRET-APP", "appToken": "SECRET-APPTOKEN", "clientId": "SECRET-CLIENT",
        "requestHeaders": "host: gw\nauthorization: Basic SECRET\nx-request-id: t1\nCookie: SECRET\nclient_id: SECRET",
        "responseHeaders": "content-type: application/json\nset-cookie: SECRET",
        "trace": json.dumps([
            {"timeMillis": 1, "message": "Found matching route", "data": None, "encryptContent": False},
            {"timeMillis": 1200, "message": "Custom interceptor executed", "data": {"name": "x"}},
        ]),
    }
    base.update(overrides)
    return base


def test_describe_call_drops_credentials():
    document = traffic.describe_call(_call())
    assert "SECRET" not in json.dumps(document)
    assert document["traceId"] == "t1" and document["status"] == 200 and document["targetStatus"] == 200
    assert document["operation"] == {"id": 8953, "name": "POST /oauth2/token"}
    assert document["durationMillis"] == 1500 and document["gatewayMillis"] == 1300 and document["targetMillis"] == 200
    assert document["app"] == "CI" and document["tokenOwner"] == "o@x" and document["caller"] == "1.2.3.4"

    sparse = traffic.describe_call({"id": "x", "resourceId": 0, "operationId": 0, "duration": 3, "resultStatus": "401"})
    assert sparse["resource"] == {"id": None, "name": None} and sparse["durationMillis"] == 3 and sparse["status"] == 401


def test_detail_masks_headers_and_parses_pipeline():
    document = traffic.describe_call_detail(_call())
    assert "SECRET" not in json.dumps(document)
    masked = {h["name"]: h["value"] for h in document["requestHeaders"] if h["masked"]}
    assert set(masked) == {"authorization", "Cookie", "client_id"} and set(masked.values()) == {traffic.MASK}
    assert {h["name"]: h["value"] for h in document["requestHeaders"] if not h["masked"]} == {"host": "gw", "x-request-id": "t1"}
    assert document["responseHeaders"][1] == {"name": "set-cookie", "value": traffic.MASK, "masked": True}
    assert [s["message"] for s in document["trace"]] == ["Found matching route", "Custom interceptor executed"]
    assert document["trace"][1]["data"] == {"name": "x"} and document["trace"][0]["step"] == 1
    assert document["totals"] == {"steps": 2, "traceMillis": 1201}

    without = traffic.describe_call_detail(_call(), include_headers=False)
    assert "requestHeaders" not in without

    assert traffic.parse_trace("not json")[0]["message"] == "not json"
    assert traffic.parse_trace(None) == [] and traffic.parse_trace(["a"])[0]["message"] == "a"
    assert traffic.mask_headers(None) == [] and traffic.mask_headers("no colon line") == []


# --------------------------------------------------------------------------- analytics


def test_analytics_summary():
    calls = [
        _call(id="a", resultStatus=200, durationMillis=100, receivedOnDate="2026-11-01T19:00:00Z"),
        _call(id="b", resultStatus=200, durationMillis=300, receivedOnDate="2026-11-01T19:10:00Z"),
        _call(id="c", resultStatus=401, typeError="client", durationMillis=10, receivedOnDate="2026-11-01T20:00:00Z", appName=""),
        _call(id="d", resultStatus=503, typeError="server", durationMillis=2000, receivedOnDate="2026-11-01T20:30:00Z", operationName="", method="GET", uri="/x"),
        _call(id="e", resultStatus=None, durationMillis=None, receivedOnDate=None, callDate=None),
    ]
    summary = traffic.analytics_summary(calls, total=50, top=2)
    assert summary["sample"] == 5 and summary["total"] == 50
    assert summary["classes"] == {"2xx": 2, "3xx": 0, "4xx": 1, "5xx": 1, "other": 1}
    assert summary["errorRate"] == 0.4
    assert summary["latencyMillis"]["avg"] == 602.5 and summary["latencyMillis"]["p50"] == 300  # nearest-rank
    assert summary["latencyMillis"]["p95"] == 2000 and summary["latencyMillis"]["max"] == 2000
    assert summary["topStatus"] == [{"key": 200, "calls": 2}, {"key": 401, "calls": 1}]
    assert summary["topOperations"][0] == {"key": "POST /oauth2/token", "calls": 4}
    assert summary["topOperations"][1] == {"key": "GET /x", "calls": 1}
    assert summary["topApps"] == [{"key": "CI", "calls": 4}, {"key": "(sem app)", "calls": 1}]
    assert summary["byHour"] == [{"hour": "2026-11-01T19", "calls": 2}, {"hour": "2026-11-01T20", "calls": 2}]
    assert [e["status"] for e in summary["recentErrors"]] == [401, 503]
    assert "SECRET" not in json.dumps(summary)

    empty = traffic.analytics_summary([], total=0)
    assert empty["errorRate"] is None and empty["latencyMillis"]["p50"] is None and empty["topStatus"] == []


def test_pipeline_data_is_sanitized():
    steps = traffic.parse_trace(json.dumps([
        {"timeMillis": 1, "message": "Request log", "data": {"log": {"headers": "host: gw\nclient_id: SECRET\nauthorization: Basic SECRET", "client_secret": "SECRET", "nested": [{"api_key": "SECRET", "ok": "fine"}]}}},
        {"timeMillis": 1, "message": "cookie: SECRET", "data": "x-api-key: SECRET\naccept: */*"},
    ]))
    text = json.dumps(steps)
    assert "SECRET" not in text
    assert steps[0]["data"]["log"]["headers"] == f"host: gw\nclient_id: {traffic.MASK}\nauthorization: {traffic.MASK}"
    assert steps[0]["data"]["log"]["client_secret"] == traffic.MASK and steps[0]["data"]["log"]["nested"][0]["ok"] == "fine"
    assert steps[1]["data"] == f"x-api-key: {traffic.MASK}\naccept: */*"
    assert steps[1]["message"] == f"cookie: {traffic.MASK}"
    assert traffic.sanitize_data(3) == 3 and traffic.sanitize_data("plain text") == "plain text"
