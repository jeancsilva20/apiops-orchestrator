import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Processo isolado: sob o pytest o root logger tem handlers do próprio pytest,
# o que mascara o `logging.lastResort` que o `sen` usa em produção.
CONNECTION_ERROR_SNIPPET = r"""
import sys
from unittest.mock import MagicMock

import requests

import apiops_orchestrator.main as main_mod
from apiops_orchestrator.adapters.inbound.cli.cli_adapter import CliError
from apiops_orchestrator.infrastructure.utils.http_client import HttpClient

requests.request = MagicMock(
    side_effect=requests.ConnectionError("('Connection aborted.', ConnectionResetError(10054))")
)


def fake_app(obj=None, prog_name=None):
    try:
        HttpClient.request("GET", "https://manager.example.com/apis", max_retries=0)
    except requests.RequestException:
        raise CliError("Manager indisponível no momento.")


main_mod.app = fake_app
sys.argv = ["sen", "publish"]
main_mod.main()
"""


def _clean_env() -> dict:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
    return env


def test_connection_error_shows_only_the_cli_message():
    proc = subprocess.run(
        [sys.executable, "-c", CONNECTION_ERROR_SNIPPET],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(REPO_ROOT),
        env=_clean_env(),
        timeout=60,
    )

    assert proc.returncode == 1
    assert "Manager indisponível no momento." in proc.stdout
    assert "Connection Error" not in proc.stdout + proc.stderr
    assert proc.stderr == ""
