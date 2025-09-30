from typer.testing import CliRunner

from src.apiops_orchestrator.adapters.inbound.cli.cli_adapter import app

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
    result = runner.invoke(app, ["sync-openapi"])
    assert result.exit_code != 0
    assert "Missing option '--env' / '-e'." in result.output

'''
def test_sync_openapi_defaults():
    """Test the command with only the required --env option, checking defaults."""
    result = runner.invoke(app, ["sync-openapi", "--env", "dev"])
    assert result.exit_code == 0
    output_str = result.output.strip()
    print(result.output)
    assert "'env': 'dev'" in output_str
    assert "'file': None" in output_str
    assert "'applied': 'DRY-RUN'" in output_str  # Default is --no-apply (DRY-RUN)
    assert "'templates_base_dir': None" in output_str
    assert "'created_templates': True" in output_str  # Default is --create-templates
'''
'''
def test_sync_openapi_all_options_enabled():
    """Test the command with all options provided and enabled."""
    result = runner.invoke(
        app,
        [
            "sync-openapi",
            "--file",
            "my-api.json",
            "--env",
            "prd",
            "--apply",
            "--out-dir",
            "/tmp/plans",
            "--create-templates",
            "--templates-root",
            "/tmp/t1",
            "--write-templates-dir",
            "/tmp/t2",
        ],
    )
    assert result.exit_code == 0
    output_str = result.output.strip()
    assert "my-api.json" in output_str
    assert "'env': 'prd'" in output_str
    assert "'applied': True" in output_str
    assert "/tmp/plans" in output_str
    assert "'created_templates': True" in output_str
'''
