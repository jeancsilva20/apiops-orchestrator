import platform
from typer.testing import CliRunner
from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app

runner = CliRunner()

def test_help():
    """Test the --help flag to ensure the CLI is registered correctly."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "APIOps CLI" in result.output
    assert "--version" in result.output

def test_version_flag():
    """Test the --version flag."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "sen 0.1.0" in result.output
    assert "apiops-orchestrator 0.1.0" in result.output
    assert f"python {platform.python_version()}" in result.output

def test_verbose_flag():
    """Test the --verbose flag doesn't fail (it's silent for now)."""
    # Using a command that exists but does nothing or just checking root with verbose
    # Since we have no functional commands yet, we can just call root help with verbose
    result = runner.invoke(app, ["--verbose", "--help"])
    assert result.exit_code == 0
    assert "APIOps CLI" in result.output

def test_api_list_success():
    """Test 'api list' command with mocked service."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [
        {"id": 1, "name": "API 1", "basePath": "/api1"},
        {"id": 2, "name": "API 2", "basePath": "/api2"}
    ]
    
    result = runner.invoke(app, ["sen", "api", "list"], obj={"api_listing_service": mock_service})
    
    assert result.exit_code == 0
    assert "id, name, basePath" in result.output
    assert "1, API 1, /api1" in result.output
    assert "2, API 2, /api2" in result.output
    mock_service.list_apis.assert_called_once_with(api_id=None)

def test_api_list_with_id():
    """Test 'api list --id' command."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [
        {"id": 123, "name": "API 123", "basePath": "/api123", "description": "Desc"}
    ]
    
    result = runner.invoke(app, ["sen", "api", "list", "--id", "123"], obj={"api_listing_service": mock_service})
    
    assert result.exit_code == 0
    assert "id, name, basePath, description" in result.output
    assert "123, API 123, /api123, Desc" in result.output
    mock_service.list_apis.assert_called_once_with(api_id=123)

def test_api_list_verbose():
    """Test 'api list --verbose' command."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [
        {"id": 1, "name": "API 1", "basePath": "/api1", "version": "v1", "description": "Desc"}
    ]
    
    result = runner.invoke(app, ["sen", "api", "list", "--verbose"], obj={"api_listing_service": mock_service})
    
    assert result.exit_code == 0
    assert "id, name, basePath, version, description" in result.output
    assert "1, API 1, /api1, v1, Desc" in result.output

def test_api_list_no_apis():
    """Test 'api list' when no APIs are returned."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = []
    
    result = runner.invoke(app, ["sen", "api", "list"], obj={"api_listing_service": mock_service})
    
    assert result.exit_code == 0
    assert "No APIs found." in result.output

