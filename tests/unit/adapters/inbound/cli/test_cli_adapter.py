import platform
from typer.testing import CliRunner
from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app

runner = CliRunner()

def test_help():
    """Test the --help flag to ensure the CLI is registered correctly."""
    result = runner.invoke(app, ["sen", "--help"])
    assert result.exit_code == 0
    assert "APIOps CLI" in result.output
    assert "--version" in result.output

def test_version_flag():
    """Test the --version flag."""
    result = runner.invoke(app, ["sen", "--version"])
    assert result.exit_code == 0
    assert "sen 0.1.0" in result.output
    assert "apiops-orchestrator 0.1.0" in result.output
    assert f"python {platform.python_version()}" in result.output

def test_verbose_flag():
    """Test the --verbose flag doesn't fail (it's silent for now)."""
    # Since we moved the callback to sen_app, options must come after 'sen'
    result = runner.invoke(app, ["sen", "--verbose", "--help"])
    assert result.exit_code == 0
    assert "APIOps CLI" in result.output

def test_api_list_success():
    """Test 'list api' naked: canonical grade + announced defaults footer (A3-2)."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [
        {"id": 1, "name": "API 1", "basePath": "/api1", "version": "1.0.0"},
        {"id": 2, "name": "API 2", "basePath": "/api2", "version": "2.0.0"},
    ]

    result = runner.invoke(app, ["sen", "list", "api"], obj={"api_listing_service": mock_service})

    assert result.exit_code == 0
    assert "ID" in result.output and "BASE PATH" in result.output
    assert "LAST REV" in result.output and "LIFE CYCLE" in result.output
    assert "/api1" in result.output
    assert "usando padrões: --limit 10 --offset 0" in result.output
    assert "detalhes: sen list api --help" in result.output
    # A3-2: o default anunciado PRECISA alcançar o pipeline (janela real)
    mock_service.list_apis.assert_called_once_with(query=None, offset=0, limit=10)

def test_api_list_explicit_window_footer():
    """Explicit --limit/--offset shows effective window footer."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [
        {"id": 1, "name": "API 1", "basePath": "/api1"}
    ]

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--offset", "90", "--limit", "5"],
        obj={"api_listing_service": mock_service},
    )

    assert result.exit_code == 0
    assert "janela: --limit 5 --offset 90" in result.output

def test_api_list_columns_values():
    """Canonical columns render version/last rev/life cycle with degradation."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [
        {
            "id": 400,
            "name": "Orchestrator Auth API",
            "basePath": "/orq-auth/v1",
            "version": "1.0.1",
            "lastRevision": {"id": 8882, "revisionNumber": 3},
            "lifeCycle": "DRAFT",
        },
        {"id": 401, "name": "Sem Revision", "basePath": "/x/v1"},
    ]

    result = runner.invoke(app, ["sen", "list", "api"], obj={"api_listing_service": mock_service})

    assert result.exit_code == 0
    assert "8882" not in result.output  # grade mostra número da revisão, não o id
    assert "DRAFT" in result.output
    assert result.output.count("-") > 0  # degradação '-' nos campos ausentes

def test_api_list_query_exclusive_with_id():
    from unittest.mock import MagicMock
    mock_service = MagicMock()

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--query", "auth", "--id", "400"],
        obj={"api_listing_service": mock_service},
    )

    assert result.exit_code == 1
    assert "--query" in result.output and "--id" in result.output

def test_api_list_invalid_limit_fails_pre_network():
    from unittest.mock import MagicMock
    mock_service = MagicMock()

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--limit", "0"],
        obj={"api_listing_service": mock_service},
    )

    assert result.exit_code == 1
    mock_service.list_apis.assert_not_called()

def test_api_list_negative_offset_fails_pre_network():
    """Symmetric with --limit: negative --offset must fail BEFORE any network call."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--offset", "-1"],
        obj={"api_listing_service": mock_service},
    )

    assert result.exit_code == 1
    assert "--offset" in result.output
    mock_service.list_apis.assert_not_called()

def test_api_list_query_passes_flags_to_service():
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [{"id": 1, "name": "A", "basePath": "/b"}]

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--query", "auth", "--limit", "3", "--offset", "2"],
        obj={"api_listing_service": mock_service},
    )

    assert result.exit_code == 0
    mock_service.list_apis.assert_called_once_with(
        query="auth", offset=2, limit=3
    )

def test_api_list_drilldown_single_row():
    """--id keeps one-line grade without window footer."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [
        {"id": 400, "name": "Orchestrator Auth API", "basePath": "/orq-auth/v1", "version": "1.0.1"}
    ]

    result = runner.invoke(app, ["sen", "list", "api", "--id", "400"], obj={"api_listing_service": mock_service})

    assert result.exit_code == 0
    assert "Orchestrator Auth API" in result.output
    assert "usando padrões" not in result.output
    mock_service.list_apis.assert_called_once_with(api_id=400)

def test_api_list_insufficient_session_translates_error():
    from unittest.mock import MagicMock
    from apiops_orchestrator.domain.models.api_collection_model import (
        InsufficientSessionError,
    )
    mock_service = MagicMock()
    mock_service.list_apis.side_effect = InsufficientSessionError(
        "Sua sessão não possui grupos de acesso"
    )

    result = runner.invoke(app, ["sen", "list", "api"], obj={"api_listing_service": mock_service})

    assert result.exit_code == 1
    assert "grupos de acesso" in result.output

def test_api_list_no_apis_when_none_returned():
    """Test 'list api' when no APIs are returned."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = []

    result = runner.invoke(app, ["sen", "list", "api"], obj={"api_listing_service": mock_service})

    assert result.exit_code == 0
    assert "No APIs found." in result.output

def test_api_list_json():
    """Test 'list api --output json'."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    data = [{"id": 1, "name": "API 1", "basePath": "/api1"}]
    mock_service.list_apis.return_value = data
    
    result = runner.invoke(app, ["sen", "list", "api", "--output", "json"], obj={"api_listing_service": mock_service})
    
    assert result.exit_code == 0
    # The output contains rich syntax highlighting, so we check for key parts
    assert '"id": 1' in result.output
    assert '"name": "API 1"' in result.output

def test_api_list_yaml():
    """Test 'list api --output yaml'."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    data = [{"id": 1, "name": "API 1", "basePath": "/api1"}]
    mock_service.list_apis.return_value = data
    
    result = runner.invoke(app, ["sen", "list", "api", "-o", "yaml"], obj={"api_listing_service": mock_service})

    assert result.exit_code == 0
    assert "id: 1" in result.output
    assert "name: API 1" in result.output


# ---------------------------------------------------------------------------
# Drill-down de revisões (task 6, opção A) — grade canônica do §3
# ---------------------------------------------------------------------------

def test_revisions_drill_down_renders_canonical_grade():
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.api_revisions.return_value = [
        {
            "revision_id": 8862,
            "revision_number": 1,
            "stage_name": "Stage One",
            "environments": "Default",
            "complete": "85%",
        },
        {
            "revision_id": 8948,
            "revision_number": 4,
            "stage_name": "Stage One",
            "environments": "-",
            "complete": "85%",
        },
    ]

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--id", "400", "--revisions"],
        obj={"api_listing_service": mock_service},
    )

    assert result.exit_code == 0
    for col in ("REV ID", "REV #", "STAGE", "ENVS", "COMPLETE"):
        assert col in result.output
    assert "Stage One" in result.output
    assert "85%" in result.output
    mock_service.api_revisions.assert_called_once_with(400)
    mock_service.list_apis.assert_not_called()


def test_revisions_requires_id_pre_network():
    from unittest.mock import MagicMock
    mock_service = MagicMock()

    result = runner.invoke(
        app, ["sen", "list", "api", "--revisions"], obj={"api_listing_service": mock_service}
    )

    assert result.exit_code == 1
    assert "--id" in result.output
    mock_service.api_revisions.assert_not_called()
    mock_service.list_apis.assert_not_called()

