import json
from pathlib import Path

import pytest
from unittest.mock import patch, Mock
from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    ManagerApiAdapter,
    _translate_completeness,
)
from apiops_orchestrator.domain.models.workflow_stage_model import WorkflowStage
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiGovernanceBlockedError,
    ManagerApiResponseTooLargeError,
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
    ManagerApiUnexpectedResponseError,
)
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.infrastructure.exceptions.http_client_exceptions import (
    HttpClient4xxError,
    HttpClientServerError,
)

FIXTURES_DIR = Path(__file__).parents[5] / "fixtures"


def load_completeness_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "completeness_bean_payload.json").read_text(encoding="utf-8"))

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
        mock_request.side_effect = HttpClient4xxError(
            status_code=401, title="Unauthorized", detail="Authentication required"
        )

        with pytest.raises(HttpClient4xxError) as excinfo:
            adapter.get_api_by_id()

        assert excinfo.value.status_code == 401

def test_get_custom_interceptor_by_id_success(mock_settings):
    adapter = ManagerApiAdapter(token="password123", base_path="/api-manager/api/v3/", max_retries=3, api_id=123,
                                settings=mock_settings)
    api_response = {"id": "8", "name": "test-interceptor", "script": "ok"}

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = api_response
        result = adapter.get_custom_interceptor_by_id(8)

        assert result == api_response

def test_get_apis_success(mock_settings):
    adapter = ManagerApiAdapter(token="token123", base_path="/api-manager/api/v3/", max_retries=3, api_id=123,
                                settings=mock_settings)
    expected_response = [{"id": 1, "name": "API 1"}, {"id": 2, "name": "API 2"}]

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = expected_response
        result = adapter.get_apis()

        assert result == expected_response
        mock_request.assert_called_once_with(
            method="GET",
            url="http://urltest.com/api-manager/api/v3/apis",
            headers={"Authorization": "Bearer token123", "Content-Type": "application/json"},
            max_retries=3
        )

def test_get_api_by_id_with_param_success(mock_settings):
    adapter = ManagerApiAdapter(token="token123", base_path="/api-manager/api/v3/", max_retries=3, api_id=123,
                                settings=mock_settings)
    api_id = 456
    expected_response = {"id": api_id, "name": "API 456"}

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = expected_response
        result = adapter.get_api_by_id(api_id=api_id)

        assert result == expected_response
        mock_request.assert_called_once_with(
            method="GET",
            url=f"http://urltest.com/api-manager/api/v3/apis/{api_id}",
            headers={"Authorization": "Bearer token123", "Content-Type": "application/json"},
            max_retries=3
        )


# ---------------------------------------------------------------------------
# Catalogo api-finder (fonte da listagem) — sondas r5 ancoradas
# ---------------------------------------------------------------------------

def test_list_catalog_apis_hits_finder_with_params_and_reads_count(mock_settings):
    adapter = ManagerApiAdapter(
        token="tok", base_path="/api-manager/api/v3/", max_retries=3,
        api_id=123, settings=mock_settings,
    )

    with patch("apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter.HttpClient.request") as mock_req:
        mock_req.return_value = ([{"apiId": 1}], {"count": "108"})

        page = adapter.list_catalog_apis(limit=95)

        assert page.total == 108
        assert len(page.rows) == 1 and page.rows[0].id == 1  # tipado (D4)
        mock_req.assert_called_once_with(
            method="GET",
            url="http://urltest.com/api-finder/api/v3/apis",
            headers={"Authorization": "Bearer tok", "Content-Type": "application/json"},
            max_retries=3,
            return_headers=True,
            params={
                "_limit": "95",
                "_offset": "0",
                "orderBy": "apiId",
                "sort": "asc",
                "onlyMyContextApi": "false",
            },
        )


def test_list_catalog_apis_default_orders_by_api_id_asc(mock_settings):
    adapter = ManagerApiAdapter(
        token="tok", base_path="/api-manager/api/v3/", max_retries=3,
        api_id=123, settings=mock_settings,
    )

    with patch("apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter.HttpClient.request") as mock_req:
        mock_req.return_value = ([], {"count": "0"})

        adapter.list_catalog_apis(limit=1)

        params = mock_req.call_args.kwargs["params"]
        assert params["orderBy"] == "apiId" and params["sort"] == "asc"


def test_list_catalog_apis_degrades_total_without_count_header(mock_settings):
    adapter = ManagerApiAdapter(
        token="tok", base_path="/api-manager/api/v3/", max_retries=3,
        api_id=123, settings=mock_settings,
    )

    with patch("apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter.HttpClient.request") as mock_req:
        mock_req.return_value = ([{"apiId": 7}], {})

        page = adapter.list_catalog_apis(limit=1)

        assert page.total == -1  # sem header: degrada, comando segue
        assert len(page.rows) == 1 and page.rows[0].id == 7


def test_list_catalog_apis_non_list_payload_normalizes_to_empty(mock_settings):
    adapter = ManagerApiAdapter(
        token="tok", base_path="/api-manager/api/v3/", max_retries=3,
        api_id=123, settings=mock_settings,
    )

    with patch("apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter.HttpClient.request") as mock_req:
        mock_req.return_value = ({"result": "failure"}, {"count": "1"})

        page = adapter.list_catalog_apis(limit=1)

        assert page.rows == []


def test_list_catalog_apis_hits_finder_with_window_defaults(mock_settings):
    adapter = ManagerApiAdapter(
        token="tok", base_path="/api-manager/api/v3/", max_retries=3,
        api_id=123, settings=mock_settings,
    )

    with patch("apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter.HttpClient.request") as mock_req:
        mock_req.return_value = ([], {"count": "0"})

        adapter.list_catalog_apis(limit=1)

        params = mock_req.call_args.kwargs["params"]
        assert params["_limit"] == "1" and params["orderBy"] == "apiId"


def _make_adapter(mock_settings):
    return ManagerApiAdapter(
        token="token123", base_path="/api-manager/api/v3/", max_retries=3,
        api_id=400, settings=mock_settings,
    )


# Stages de workflow — catálogo capturado (sonda r2, workflow 139)
STAGE_ROWS_SAMPLE = [
    {"workflowStageId": 420, "workflowStageName": "Stage One", "position": 1},
    {"workflowStageId": 753, "workflowStageName": "Teste", "position": 2},
]


def test_workflow_stages_uses_governance_base_path(mock_settings):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = STAGE_ROWS_SAMPLE
        result = adapter.get_workflow_stages(139)

        assert result == [
            WorkflowStage(workflowStageId=420, workflowStageName="Stage One"),
            WorkflowStage(workflowStageId=753, workflowStageName="Teste"),
        ]
        assert mock_request.call_args.kwargs["url"] == (
            "http://urltest.com/api-governance/api/v3/workflows/139/stages"
        )


def test_workflow_stages_cached_per_executed_execution(mock_settings):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = STAGE_ROWS_SAMPLE

        adapter.get_workflow_stages(139)
        adapter.get_workflow_stages(139)  # segunda chamada: HIT, zero rede
        adapter.get_workflow_stages(753)  # workflow distinto: MISS, 1 rede

        assert mock_request.call_count == 2


def test_workflow_stages_failures_are_never_cached_and_degrade(mock_settings):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        # 1ª: falha -> [] ; 2ª: sucesso -> payload ; 3ª (agora em cache): sem rede
        mock_request.side_effect = [RuntimeError("governance down"), STAGE_ROWS_SAMPLE, STAGE_ROWS_SAMPLE]

        assert adapter.get_workflow_stages(139) == []
        assert adapter.get_workflow_stages(139) == [
            WorkflowStage(workflowStageId=420, workflowStageName="Stage One"),
            WorkflowStage(workflowStageId=753, workflowStageName="Teste"),
        ]
        assert adapter.get_workflow_stages(139) == [
            WorkflowStage(workflowStageId=420, workflowStageName="Stage One"),
            WorkflowStage(workflowStageId=753, workflowStageName="Teste"),
        ]
        assert mock_request.call_count == 2  # falha nao entrou em cache


def test_stages_cache_lives_only_within_adapter_instance(mock_settings):
    adapter_a = _make_adapter(mock_settings)
    adapter_b = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = STAGE_ROWS_SAMPLE

        adapter_a.get_workflow_stages(139)
        adapter_a.get_workflow_stages(139)   # cache do A
        adapter_b.get_workflow_stages(139)   # B não vê cache do A

        assert mock_request.call_count == 2


# ---------------------------------------------------------------------------
# Completeness por revisão
# ---------------------------------------------------------------------------

def test_get_revision_completeness_hits_manager_endpoint_with_fixture_payload(mock_settings):
    adapter = _make_adapter(mock_settings)
    bean = load_completeness_fixture()

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = bean
        reading = adapter.get_revision_completeness(5513)

        assert type(reading).__name__ == "CatalogRevisionCompleteness"
        assert reading.score == 85.0
        assert reading.suggestions == bean["suggestions"]
        mock_request.assert_called_once_with(
            method="GET",
            url="http://urltest.com/api-manager/api/v3/revisions/5513/completeness",
            headers={"Authorization": "Bearer token123", "Content-Type": "application/json"},
            max_retries=3,
        )


def test_translate_completeness_discards_blank_suggestions():
    raw = {
        "completenessScore": 142.0,
        "suggestions": ["dica real", "   ", None, "segunda dica"],
    }

    reading = _translate_completeness(raw)

    assert reading.score == 142.0  # model é honesto: sanitizar é trabalho do render
    assert reading.suggestions == ["dica real", "segunda dica"]


def test_translate_completeness_anomalous_wire_degrades_to_zero(monkeypatch=None):
    reading = _translate_completeness({"completenessScore": "not-a-number", "suggestions": None})

    assert reading.score == 0.0
    assert reading.suggestions == []

    empty = _translate_completeness(None)
    assert empty.score == 0.0 and empty.suggestions == []


def test_get_revision_completeness_4xx_raises_transport_rejected_signal(mock_settings):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.side_effect = HttpClient4xxError(
            status_code=404, title="Not Found", detail="revision 5513 not found"
        )

        with pytest.raises(ManagerApiTransportRejectedError) as excinfo:
            adapter.get_revision_completeness(5513)

        assert excinfo.value.status_code == 404


def test_get_revision_completeness_exhausted_5xx_raises_transport_unavailable_signal(mock_settings):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.side_effect = HttpClientServerError("Bad Gateway: upstream exploded")

        with pytest.raises(ManagerApiTransportUnavailableError):
            adapter.get_revision_completeness(5513)

def test_list_catalog_apis_sends_offset_for_paging(mock_settings):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = ([], {"count": "127"})

        adapter.list_catalog_apis(limit=25, offset=50, query="pagamentos")

        params = mock_request.call_args.kwargs["params"]
        assert params["_limit"] == "25"
        assert params["_offset"] == "50"
        assert "pagamentos" in params["customSearch"]


def test_413_raises_response_too_large_signal_still_a_rejection(mock_settings):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.side_effect = HttpClient4xxError(
            status_code=413,
            title="BACKEND_RESPONSE_TOO_LARGE",
            detail="Backend response was too large to process safely",
            code="BACKEND_RESPONSE_TOO_LARGE",
            request_id="143ba864-1f30",
        )

        with pytest.raises(ManagerApiResponseTooLargeError) as excinfo:
            adapter.list_catalog_apis(limit=127)

    assert isinstance(excinfo.value, ManagerApiTransportRejectedError)
    assert excinfo.value.status_code == 413
    assert excinfo.value.code == "BACKEND_RESPONSE_TOO_LARGE"
    assert excinfo.value.request_id == "143ba864-1f30"


def test_rejection_diagnostics_are_logged_at_info_without_token(mock_settings, caplog):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.side_effect = HttpClient4xxError(
            status_code=400, title="Bad Request", detail="x",
            code="INVALID_QUERY", request_id="req-42",
        )
        with caplog.at_level("INFO"):
            with pytest.raises(ManagerApiTransportRejectedError) as excinfo:
                adapter.list_catalog_apis(limit=1)

    assert not isinstance(excinfo.value, ManagerApiResponseTooLargeError)
    records = [r for r in caplog.records if "manager_api.transport.rejected" in r.getMessage()]
    assert records and all(r.levelname == "INFO" for r in records)
    message = records[0].getMessage()
    assert "status_code=400" in message and "code=INVALID_QUERY" in message
    assert "request_id=req-42" in message
    assert "token123" not in caplog.text


# --- Envelope de erro da plataforma (V-23 §1) --------------------------------

# Corpo real do 412 (caderno de testes, T03): o motivo vem num JSON dentro de string.
GOVERNANCE_412_BODY = {
    "result": "failure",
    "errors": [{
        "type": "INVALID",
        "message": '{"timestamp":1792068778625,"status":412,"error":"PRECONDITION_FAILED",'
                   '"messages":["API must contain attribute My new"],'
                   '"path":"/api-governance/api/v3/workflows/500/validate"}',
    }],
    "status": 412,
}


def test_governance_412_becomes_governance_signal_with_workflow_and_raw(mock_settings):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.side_effect = HttpClient4xxError(
            status_code=412, title="failure", detail="x", body=GOVERNANCE_412_BODY
        )
        with pytest.raises(ManagerApiGovernanceBlockedError) as excinfo:
            adapter.update_revision(9161, {"api": {}})

    signal = excinfo.value
    assert isinstance(signal, ManagerApiTransportRejectedError)
    assert signal.workflow_id == 500
    assert signal.messages == ["API must contain attribute My new"]
    assert signal.raw == GOVERNANCE_412_BODY


def test_412_without_governance_path_stays_a_plain_rejection(mock_settings):
    adapter = _make_adapter(mock_settings)
    body = {"errors": [{"message": "revision is locked"}]}

    with patch(MOCK_PATH) as mock_request:
        mock_request.side_effect = HttpClient4xxError(
            status_code=412, title="x", detail="x", body=body
        )
        with pytest.raises(ManagerApiTransportRejectedError) as excinfo:
            adapter.update_revision(9161, {})

    assert not isinstance(excinfo.value, ManagerApiGovernanceBlockedError)
    assert excinfo.value.messages == ["revision is locked"]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"code": "BACKEND_RESPONSE_TOO_LARGE", "message": "too large"}, ["too large"]),
        ({"errors": [{"message": "Invalid basePath"}]}, ["Invalid basePath"]),
        ({"errors": [{"message": "{broken json"}]}, ["{broken json"]),
        ({"messages": ["a", "a", " b "]}, ["a", "b"]),
        (None, []),
        ("plain text body", []),
    ],
)
def test_platform_messages_unwraps_envelope_defensively(mock_settings, body, expected):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.side_effect = HttpClient4xxError(
            status_code=400, title="x", detail="x", body=body
        )
        with pytest.raises(ManagerApiTransportRejectedError) as excinfo:
            adapter.update_revision(9161, {})

    assert excinfo.value.messages == expected


# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------


def test_deploy_revision_posta_o_corpo_da_ui_e_devolve_o_id(mock_settings):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = {"id": 267}
        deployment_id = adapter.deploy_revision(7, 9327)

    assert deployment_id == 267
    kwargs = mock_request.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "http://urltest.com/api-manager/api/v3/deployments"
    assert kwargs["json"] == {"environmentId": 7, "revisionId": 9327, "status": "DEPLOYED"}


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (
            400,
            {"result": "failure", "errors": [{"path": "environment", "type": "INVALID",
             "message": "Environment Variable '$backend' have not found"}], "status": 400},
            ["Environment Variable '$backend' have not found"],
        ),
        (
            404,
            {"result": "failure", "errors": [{"path": "environment", "type": "INVALID",
             "message": "Environment not found."}], "status": 404},
            ["Environment not found."],
        ),
    ],
)
def test_deploy_revision_recusa_carrega_a_mensagem_da_plataforma(
    mock_settings, status, body, expected
):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.side_effect = HttpClient4xxError(
            status_code=status, title="x", detail="x", body=body
        )
        with pytest.raises(ManagerApiTransportRejectedError) as excinfo:
            adapter.deploy_revision(7, 9327)

    assert excinfo.value.status_code == status
    assert excinfo.value.messages == expected


def test_deploy_revision_5xx_esgotado_vira_indisponivel(mock_settings):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.side_effect = HttpClientServerError("Internal Server Error")
        with pytest.raises(ManagerApiTransportUnavailableError):
            adapter.deploy_revision(7, None)


def test_get_revision_swagger_reads_the_revision_swagger(mock_settings):
    adapter = _make_adapter(mock_settings)
    swagger = {"openapi": "3.0.0", "paths": {}}

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = swagger
        assert adapter.get_revision_swagger(9554) == swagger

    kwargs = mock_request.call_args.kwargs
    assert kwargs["method"] == "GET"
    assert kwargs["url"] == "http://urltest.com/api-manager/api/v3/revisions/9554/swagger"


def test_get_revision_swagger_outside_json_is_an_unexpected_response(mock_settings):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = "openapi: 3.0.0"
        with pytest.raises(ManagerApiUnexpectedResponseError):
            adapter.get_revision_swagger(9554)


def test_update_revision_swagger_puts_the_whole_document(mock_settings):
    adapter = _make_adapter(mock_settings)
    document = {"openapi": "3.0.0", "paths": {"/t": {}}}

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = {"result": "success"}
        adapter.update_revision_swagger(9554, document)

    kwargs = mock_request.call_args.kwargs
    assert kwargs["method"] == "PUT"
    assert kwargs["url"] == "http://urltest.com/api-manager/api/v3/revisions/9554/swagger"
    assert kwargs["json"] == document


def test_update_revision_swagger_rejection_carries_the_platform_reasons(mock_settings):
    adapter = _make_adapter(mock_settings)
    body = {"result": "failure", "errors": [{"message": "Invalid swagger"}], "status": 400}

    with patch(MOCK_PATH) as mock_request:
        mock_request.side_effect = HttpClient4xxError(status_code=400, title="x", detail="x", body=body)
        with pytest.raises(ManagerApiTransportRejectedError) as excinfo:
            adapter.update_revision_swagger(9554, {})

    assert excinfo.value.messages == ["Invalid swagger"]
