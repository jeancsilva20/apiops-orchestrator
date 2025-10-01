from typer.testing import CliRunner

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app

runner = CliRunner()


def test_sync_openapi_help():
    """Test the --help flag to ensure the command is registered correctly."""
    result = runner.invoke(app, ["sync-openapi", "--help"])
    assert result.exit_code == 0
    assert "Usage: root sync-openapi [OPTIONS]" in result.output
    assert "--repo" in result.output
    assert "--env" in result.output
    assert "--apply" in result.output


def test_sync_openapi_missing_env_fails():
    """Test that the command fails if the required --env option is missing."""
    result = runner.invoke(app, ["sync-openapi", "--repo", "/test"])
    assert result.exit_code != 0
    assert "Missing option '--env' / '-e'." in result.output

def test_sync_openapi_missing_repo_fails():
    """Test that the command fails if the required --repo option is missing."""
    result = runner.invoke(app, ["sync-openapi", "--env", "test"])
    assert result.exit_code != 0
    assert " Missing option '--repo' / '-r'" in result.output

# TODO Implementar caso de sucesso default.
def test_sync_openapi_defaults():
    pass


# TODO Implementar caso de sucesso com todas as opções.
def test_sync_openapi_all_options_enabled():
    pass

