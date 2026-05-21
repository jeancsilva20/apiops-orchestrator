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
