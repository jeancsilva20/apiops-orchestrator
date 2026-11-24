"""A raiz da CLI: `--help`, `--version`, `--verbose` e `sen list` sem subcomando.

Recortado de `test_cli_adapter.py`, que reunia a raiz da CLI, `sen list api` e
`sen completeness` em 744 linhas. Os corpos sao os mesmos; mudou a casa.
"""

import platform


from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    _translate_row,
)
from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from sen_support.cli_invoke import runner



def _entry(raw) -> ApiCatalogEntry:
    e = _translate_row(raw)
    assert e is not None
    return e


def test_help():
    """Test the --help flag to ensure the CLI is registered correctly."""
    result = runner.invoke(app, ["sen", "--help"])
    assert result.exit_code == 0
    assert "CLI do APIOps" in result.output
    assert "--version" in result.output

def test_version_flag():
    """Test the --version flag."""
    result = runner.invoke(app, ["sen", "--version"])
    assert result.exit_code == 0
    assert "sen 0.1.1" in result.output
    assert "apiops-orchestrator 0.1.1" in result.output
    assert f"python {platform.python_version()}" in result.output

def test_verbose_flag():
    """Test the --verbose flag doesn't fail (it's silent for now)."""
    # Since we moved the callback to sen_app, options must come after 'sen'
    result = runner.invoke(app, ["sen", "--verbose", "--help"])
    assert result.exit_code == 0
    assert "CLI do APIOps" in result.output

def test_list_without_subcommand_orientates_instead_of_engine_speak():
    """`sen list` pelado não mostra 'Missing command.': orienta para 'sen list api' (exit 2)."""
    result = runner.invoke(app, ["sen", "list"])

    assert result.exit_code == 2
    assert "sen list api" in result.output.replace("\n", " ")
    assert "--help" in result.output
