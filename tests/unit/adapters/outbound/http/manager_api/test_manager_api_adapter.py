import pytest
from unittest.mock import patch, Mock
import typer
from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import ManagerApiAdapter
from apiops_orchestrator.config.settings import Settings

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
        mock_request.side_effect = typer.Exit(code=1)

        with pytest.raises(typer.Exit) as excinfo:
            adapter.get_api_by_id()

        assert excinfo.value.exit_code == 1

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
# Drill-down (task 5 do add-sen-list) — shapes ancorados nas sondas 21/09/2026
# (docs/feat-command-sen-list/probes/): revision_completeness e
# workflow_139_stages capturados da plataforma em produção.
#
# Nota de desenho: o drill-down NÃO chama /revisions/{rid} nem revisions/basic
# — TODA a matéria-prima das grades (revisions[], lastRevision, environments)
# já vem no próprio GET /apis/{id} (ver temp_example_api.json da fatia).
# ---------------------------------------------------------------------------

STAGE_ROWS_SAMPLE = [
    {"workflowStageId": 420, "workflowStageName": "Stage One", "position": 1},
    {"workflowStageId": 753, "workflowStageName": "Teste", "position": 2},
]


def _make_adapter(mock_settings):
    return ManagerApiAdapter(
        token="token123", base_path="/api-manager/api/v3/", max_retries=3,
        api_id=400, settings=mock_settings,
    )


def test_get_revision_completeness_success_returns_payload(mock_settings):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = {"percentageCompleted": 80}
        result = adapter.get_revision_completeness(8948)

        assert result == {"percentageCompleted": 80}


def test_get_revision_completeness_degrades_to_empty_on_backend_refusal(mock_settings):
    """O backend delega ao Adaptive Governance e pode recusar (422→403 nas sondas)."""
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.side_effect = RuntimeError("HTTP 422: INVALID")
        result = adapter.get_revision_completeness(8948)

        assert result == {}


def test_workflow_stages_uses_governance_base_path(mock_settings):
    adapter = _make_adapter(mock_settings)

    with patch(MOCK_PATH) as mock_request:
        mock_request.return_value = STAGE_ROWS_SAMPLE
        result = adapter.get_workflow_stages(139)

        assert result == STAGE_ROWS_SAMPLE
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
        assert adapter.get_workflow_stages(139) == STAGE_ROWS_SAMPLE
        assert adapter.get_workflow_stages(139) == STAGE_ROWS_SAMPLE
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