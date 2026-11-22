from unittest.mock import Mock, patch

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError

from apiops_orchestrator.adapters.outbound.http.governance_api.governance_api_adapter import (
    GovernanceApiAdapter,
)
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.governance_model import (
    GovernanceAvailability,
    WorkflowStage,
)
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)
from apiops_orchestrator.infrastructure.exceptions.http_client_exceptions import (
    HttpClient4xxError,
    HttpClientServerError,
)

MOCK_PATH = "apiops_orchestrator.infrastructure.utils.http_client.HttpClient.request"
SLEEP_PATH = "apiops_orchestrator.adapters.outbound.http.governance_api.governance_api_adapter.time.sleep"

# Body measured on a tenant without the module (2026-11-10).
MODULE_DISABLED_BODY = {
    "result": "failure",
    "message": "In order to use this resource you must have Governance module enabled.",
}
ATTRIBUTES = [{"id": 96, "name": "CLI", "tags": []}]


@pytest.fixture
def adapter():
    settings = Mock(spec=Settings)
    settings.HOST = "http://urltest.com"
    return GovernanceApiAdapter(token="token123", max_retries=3, settings=settings)


def _forbidden(body):
    return HttpClient4xxError(status_code=403, title="Forbidden", detail="x", body=body)


# --- availability ------------------------------------------------------------


def test_catalog_answer_means_enabled_in_one_call(adapter):
    with patch(MOCK_PATH) as request:
        request.return_value = ATTRIBUTES
        assert adapter.availability() is GovernanceAvailability.ENABLED

    request.assert_called_once_with(
        method="GET",
        url="http://urltest.com/api-governance/api/v3/attributes",
        headers={"Authorization": "Bearer token123", "Content-Type": "application/json"},
        max_retries=0,
        timeout=10,
    )


def test_module_message_on_403_means_disabled_without_retry(adapter):
    with patch(MOCK_PATH) as request, patch(SLEEP_PATH) as sleep:
        request.side_effect = _forbidden(MODULE_DISABLED_BODY)
        assert adapter.availability() is GovernanceAvailability.DISABLED

    assert request.call_count == 1
    sleep.assert_not_called()


def test_403_without_the_module_message_is_unknown_without_retry(adapter):
    with patch(MOCK_PATH) as request, patch(SLEEP_PATH):
        request.side_effect = _forbidden({"message": "Access denied"})
        assert adapter.availability() is GovernanceAvailability.UNKNOWN

    assert request.call_count == 1


def test_server_error_is_retried_until_the_catalog_answers(adapter):
    with patch(MOCK_PATH) as request, patch(SLEEP_PATH) as sleep:
        request.side_effect = [HttpClientServerError("502"), ATTRIBUTES]
        assert adapter.availability() is GovernanceAvailability.ENABLED

    assert request.call_count == 2
    sleep.assert_called_once_with(2.0)


@pytest.mark.parametrize(
    "failure",
    [
        RequestsConnectionError("down"),
        HttpClientServerError("503"),
        HttpClient4xxError(status_code=404, title="Not Found", detail="x"),
    ],
)
def test_three_failures_other_than_403_are_unknown(adapter, failure):
    with patch(MOCK_PATH) as request, patch(SLEEP_PATH) as sleep:
        request.side_effect = failure
        assert adapter.availability() is GovernanceAvailability.UNKNOWN

    assert request.call_count == 3
    assert sleep.call_count == 2


def test_availability_is_asked_once_per_execution(adapter):
    with patch(MOCK_PATH) as request:
        request.side_effect = _forbidden(MODULE_DISABLED_BODY)
        adapter.availability()
        assert adapter.availability() is GovernanceAvailability.DISABLED

    assert request.call_count == 1


# --- attributes and workflow -------------------------------------------------


def test_attributes_reuse_the_availability_answer(adapter):
    with patch(MOCK_PATH) as request:
        request.return_value = ATTRIBUTES
        adapter.availability()
        assert adapter.list_attributes() == ATTRIBUTES

    assert request.call_count == 1


def test_attributes_without_availability_read_the_catalog(adapter):
    with patch(MOCK_PATH) as request:
        request.return_value = {"content": ATTRIBUTES}
        assert adapter.list_attributes() == ATTRIBUTES

    assert request.call_args.kwargs["url"] == "http://urltest.com/api-governance/api/v3/attributes"
    assert request.call_args.kwargs["max_retries"] == 3


def test_attributes_refusal_becomes_the_port_signal(adapter):
    with patch(MOCK_PATH) as request:
        request.side_effect = _forbidden({"message": "Access denied"})
        with pytest.raises(ManagerApiTransportRejectedError) as excinfo:
            adapter.list_attributes()

    assert excinfo.value.status_code == 403


def test_workflow_unavailable_becomes_the_port_signal(adapter):
    with patch(MOCK_PATH) as request:
        request.side_effect = HttpClientServerError("500")
        with pytest.raises(ManagerApiTransportUnavailableError):
            adapter.get_workflow(139)

    assert request.call_args.kwargs["url"] == "http://urltest.com/api-governance/api/v3/workflows/139"


# --- workflow stages (catalog captured on probe r2, workflow 139) ------------

STAGE_ROWS_SAMPLE = [
    {"workflowStageId": 420, "workflowStageName": "Stage One", "position": 1},
    {"workflowStageId": 753, "workflowStageName": "Teste", "position": 2},
]
STAGES = [
    WorkflowStage(workflowStageId=420, workflowStageName="Stage One"),
    WorkflowStage(workflowStageId=753, workflowStageName="Teste"),
]


def test_workflow_stages_uses_governance_base_path(adapter):
    with patch(MOCK_PATH) as request:
        request.return_value = STAGE_ROWS_SAMPLE
        assert adapter.get_workflow_stages(139) == STAGES

    assert request.call_args.kwargs["url"] == (
        "http://urltest.com/api-governance/api/v3/workflows/139/stages"
    )


def test_workflow_stages_cached_per_execution(adapter):
    with patch(MOCK_PATH) as request:
        request.return_value = STAGE_ROWS_SAMPLE
        adapter.get_workflow_stages(139)
        adapter.get_workflow_stages(139)
        adapter.get_workflow_stages(753)

    assert request.call_count == 2


def test_workflow_stages_failures_are_never_cached_and_degrade(adapter):
    with patch(MOCK_PATH) as request:
        request.side_effect = [RuntimeError("governance down"), STAGE_ROWS_SAMPLE]
        assert adapter.get_workflow_stages(139) == []
        assert adapter.get_workflow_stages(139) == STAGES
        assert adapter.get_workflow_stages(139) == STAGES

    assert request.call_count == 2


def test_workflow_stages_skip_rows_without_a_numeric_id(adapter):
    rows = [
        {"workflowStageId": "x", "workflowStageName": "Broken"},
        {"workflowStageId": 420, "workflowStageName": "  "},
        "not a row",
    ]
    with patch(MOCK_PATH) as request:
        request.return_value = rows
        assert adapter.get_workflow_stages(139) == [WorkflowStage(workflowStageId=420)]
