import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import apiops_orchestrator.main as main_mod
from apiops_orchestrator.adapters.inbound.cli.cli_adapter import CliError
from apiops_orchestrator.config.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHONPATH_SRC = str(REPO_ROOT / "src")

ETAPA3_SKIP = pytest.mark.skip(
    reason="Exige composition root lazy (Etapa 3 do ADR 0006)"
)


class RecordingApp:
    def __init__(self):
        self.calls = []

    def __call__(self, obj=None):
        self.calls.append(obj)


def _stub_settings(project_root: Path):
    settings = Settings.__new__(Settings)
    object.__setattr__(settings, "PROJECT_ROOT", project_root)
    object.__setattr__(settings, "AUTH_HOST", "https://auth.example.com")
    object.__setattr__(settings, "AUTH_LOGIN_PATH", "/cli-2/orq-auth/v1/oauth2/token")
    object.__setattr__(settings, "SEN_CREDENTIALS", None)
    return settings


def test_login_service_factory_uses_package_root_for_session_store(tmp_path):
    settings = _stub_settings(project_root=tmp_path / "repo")
    object.__setattr__(settings, "PACKAGE_ROOT", tmp_path)

    factory = main_mod.build_login_service_factory(settings)
    service = factory()

    assert service.session_store.session_path == tmp_path / ".sen_session"
    assert service.session_store.directory == tmp_path


@pytest.fixture
def isolated_main(monkeypatch):
    fake_app = RecordingApp()
    monkeypatch.setattr(main_mod, "app", fake_app)
    monkeypatch.setattr(main_mod, "Settings", MagicMock(return_value=MagicMock()))
    return fake_app, monkeypatch


def test_invoked_argv_skips_legacy_pipeline(isolated_main):
    fake_app, monkeypatch = isolated_main
    invoked_ctx = {"login_service_factory": "L", "api_listing_service_factory": "S"}
    bare_spy = MagicMock(side_effect=AssertionError("legacy pipeline must not run"))
    invoked_spy = MagicMock(return_value=invoked_ctx)
    monkeypatch.setattr(main_mod, "run_bare_pipeline", bare_spy)
    monkeypatch.setattr(main_mod, "build_invoked_context", invoked_spy)

    monkeypatch.setattr(sys, "argv", ["main.py", "sen", "login"])
    main_mod.main()

    bare_spy.assert_not_called()
    invoked_spy.assert_called_once()
    assert fake_app.calls == [invoked_ctx]


def test_invoked_argv_for_other_commands_same_gate(isolated_main):
    fake_app, monkeypatch = isolated_main
    invoked_ctx = {"api_listing_service_factory": "S"}
    monkeypatch.setattr(main_mod, "run_bare_pipeline", MagicMock())
    monkeypatch.setattr(
        main_mod, "build_invoked_context", MagicMock(return_value=invoked_ctx)
    )

    monkeypatch.setattr(sys, "argv", ["main.py", "sen", "list", "api"])
    main_mod.main()

    assert fake_app.calls == [invoked_ctx]


def test_bare_argv_keeps_legacy_pipeline(isolated_main):
    fake_app, monkeypatch = isolated_main
    bare_ctx = {"api_listing_service": "DIRECT"}
    bare_spy = MagicMock(return_value=bare_ctx)
    invoked_spy = MagicMock(side_effect=AssertionError("invoked gate must not run"))
    monkeypatch.setattr(main_mod, "run_bare_pipeline", bare_spy)
    monkeypatch.setattr(main_mod, "build_invoked_context", invoked_spy)

    monkeypatch.setattr(sys, "argv", [])
    main_mod.main()

    invoked_spy.assert_not_called()
    bare_spy.assert_called_once()
    assert fake_app.calls == [bare_ctx]


def test_bare_mode_cli_error_returns_given_exit_code(isolated_main):
    fake_app, monkeypatch = isolated_main

    def boom(_settings):
        raise CliError("Environment variables missing", exit_code=1)

    monkeypatch.setattr(main_mod, "run_bare_pipeline", boom)
    monkeypatch.setattr(sys, "argv", [])

    with pytest.raises(SystemExit) as excinfo:
        main_mod.main()

    assert excinfo.value.code == 1
    assert fake_app.calls == []


def test_bare_flow_contract_still_present():
    assert hasattr(main_mod, "run_bare_pipeline") and callable(
        main_mod.run_bare_pipeline
    )
    assert hasattr(main_mod, "build_invoked_context") and callable(
        main_mod.build_invoked_context
    )


IMPORT_PURITY_SNIPPET = """
import apiops_orchestrator.main as m
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.infrastructure.secure_storage.session_store import (
    SessionStore,
)
from apiops_orchestrator.infrastructure.utils.http_client import HttpClient
offenders = [
    name
    for name, value in vars(m).items()
    if isinstance(value, (Settings, SessionStore, HttpClient))
]
print("PURE" if not offenders else offenders)
"""


def _clean_env() -> dict:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": PYTHONPATH_SRC,
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
    for var in ("AUTH_HOST", "AUTH_LOGIN_PATH", "SEN_CREDENTIALS", "HOST"):
        env.pop(var, None)
    return env


def test_module_import_is_side_effect_free():
    proc = subprocess.run(
        [sys.executable, "-c", IMPORT_PURITY_SNIPPET],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=_clean_env(),
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr
    assert "PURE" in proc.stdout, proc.stdout


@ETAPA3_SKIP
def test_console_script_sen_naked_shows_help_never_pipeline():
    script = (
        "import sys; sys.argv = ['sen']; "
        "from apiops_orchestrator.main import main; main()"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**_clean_env()},
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Usage" in proc.stdout or "usage" in proc.stdout


@ETAPA3_SKIP
def test_sen_list_api_help_without_env():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "apiops_orchestrator.main",
            "sen",
            "list",
            "api",
            "--help",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=_clean_env(),
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Usage" in proc.stdout or "usage" in proc.stdout
