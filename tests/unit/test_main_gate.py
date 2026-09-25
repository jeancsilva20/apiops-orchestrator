import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pydantic
import pytest

import apiops_orchestrator.main as main_mod
from apiops_orchestrator.adapters.inbound.cli.cli_adapter import CliError
from apiops_orchestrator.config.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHONPATH_SRC = str(REPO_ROOT / "src")

BARE_MODE_SKIP = pytest.mark.skip(
    reason="Modo bare mantido (decisão): invocação desnuda executa o fluxo legacy; "
    "paridade/instalação do shim ficam nos smokes do add-sen-entrypoint"
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


def test_login_service_factory_uses_package_root_for_session_store(monkeypatch, tmp_path):
    settings = _stub_settings(project_root=tmp_path / "repo")
    object.__setattr__(settings, "PACKAGE_ROOT", tmp_path)
    monkeypatch.setattr(main_mod, "_load_settings", MagicMock(return_value=settings))

    factory = main_mod.build_login_service_factory()
    service = factory()

    assert service.session_store.session_path == tmp_path / ".sen_session"
    assert service.session_store.directory == tmp_path


# ---------------------------------------------------------------------------
# Gate de boot: main() é dispatch puro; Settings só nasce no consumo
# ---------------------------------------------------------------------------


@pytest.fixture
def recording_app(monkeypatch):
    fake_app = RecordingApp()
    monkeypatch.setattr(main_mod, "app", fake_app)
    return fake_app


def test_invoked_argv_builds_lazy_factories_and_never_runs_pipeline(recording_app, monkeypatch):
    fake_app = recording_app
    def login_marker():
        return "LOGIN_SERVICE"

    def listing_marker():
        return "LISTING_SERVICE"

    constructions = []

    def login_factory():
        constructions.append("login")
        return login_marker

    def listing_factory():
        constructions.append("listing")
        return listing_marker

    bare_spy = MagicMock(side_effect=AssertionError("legacy pipeline must not run"))
    monkeypatch.setattr(main_mod, "build_login_service_factory", login_factory)
    monkeypatch.setattr(main_mod, "build_listing_service_factory", listing_factory)
    monkeypatch.setattr(main_mod, "run_bare_pipeline", bare_spy)

    monkeypatch.setattr(sys, "argv", ["main.py", "sen", "login"])
    main_mod.main()

    bare_spy.assert_not_called()
    assert constructions == ["login", "listing"]
    obj = fake_app.calls[0]
    assert obj["login_service_factory"] is login_marker
    assert obj["api_listing_service_factory"] is listing_marker


def test_invoked_argv_other_commands_share_same_gate(recording_app, monkeypatch):
    fake_app = recording_app

    def listing_marker():
        return "LISTING_SERVICE"

    monkeypatch.setattr(
        main_mod, "build_login_service_factory", lambda: lambda: "LOGIN_SERVICE"
    )
    monkeypatch.setattr(main_mod, "build_listing_service_factory", lambda: listing_marker)
    monkeypatch.setattr(main_mod, "run_bare_pipeline", MagicMock())

    monkeypatch.setattr(sys, "argv", ["main.py", "sen", "list", "api"])
    main_mod.main()

    obj = fake_app.calls[0]
    assert obj["api_listing_service_factory"] is listing_marker


def test_bare_argv_keeps_legacy_pipeline(recording_app, monkeypatch):
    fake_app = recording_app
    sentinel = object()
    load_spy = MagicMock(return_value=sentinel)
    bare_spy = MagicMock(return_value={"api_listing_service": "DIRECT"})
    monkeypatch.setattr(main_mod, "_load_settings", load_spy)
    monkeypatch.setattr(main_mod, "run_bare_pipeline", bare_spy)

    monkeypatch.setattr(sys, "argv", [])
    main_mod.main()

    load_spy.assert_called_once()
    bare_spy.assert_called_once_with(sentinel)
    assert fake_app.calls == []


def test_bare_cli_error_returns_given_exit_code(recording_app, monkeypatch):
    monkeypatch.setattr(
        main_mod,
        "_load_settings",
        MagicMock(side_effect=CliError("Configuração incompleta", exit_code=1)),
    )
    monkeypatch.setattr(sys, "argv", [])

    with pytest.raises(SystemExit) as excinfo:
        main_mod.main()

    assert excinfo.value.code == 1


def test_load_settings_translates_missing_config_into_educational_cli_error(monkeypatch):
    line_errors = [
        {"type": "missing", "loc": ("HOST",), "input": {}},
        {"type": "missing", "loc": ("AUTH_HOST",), "input": {}},
    ]
    monkeypatch.setattr(
        main_mod,
        "Settings",
        MagicMock(
            side_effect=pydantic.ValidationError.from_exception_data(
                title="Settings", line_errors=line_errors
            )
        ),
    )

    with pytest.raises(CliError) as excinfo:
        main_mod._load_settings()

    message = excinfo.value.message
    assert "HOST" in message and "AUTH_HOST" in message
    assert "--help" in message
    assert excinfo.value.exit_code == 1


def test_factories_do_not_touch_settings_at_construction(monkeypatch):
    monkeypatch.setattr(
        main_mod,
        "Settings",
        MagicMock(side_effect=AssertionError("Settings must not load eagerly")),
    )

    main_mod.build_login_service_factory()
    main_mod.build_listing_service_factory()


# ---------------------------------------------------------------------------
# Contract that survived migration
# ---------------------------------------------------------------------------


def test_bare_flow_contract_still_present():
    assert hasattr(main_mod, "run_bare_pipeline") and callable(
        main_mod.run_bare_pipeline
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

# O filho ainda encontraria o .env do repo (dotenv caminho absoluto), então a
# prova honesta de D1-a NÃO é "env zerada" — é venenar Settings ANTES de
# importar main: se qualquer caminho do boot tocar Settings, RuntimeError BOOM.
HELP_WITHOUT_SETTINGS_SNIPPET = """
import sys
sys.argv = ["main.py"] + {args!r}
import apiops_orchestrator.config.settings as _cs

class _BoomSettings:
    def __new__(cls):
        raise RuntimeError("BOOM: Settings loaded during --help!")

_cs.Settings = _BoomSettings

from apiops_orchestrator.main import main
main()
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


def test_sen_help_booms_if_settings_are_touched():
    """sen --help responde (exit 0) mesmo com Settings venenada — D1-a."""
    snippet = HELP_WITHOUT_SETTINGS_SNIPPET.format(args=["sen", "--help"])
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=_clean_env(),
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Usage" in proc.stdout or "usage" in proc.stdout
    assert "BOOM" not in proc.stderr and "BOOM" not in proc.stdout


def test_sen_list_api_help_booms_if_settings_are_touched():
    snippet = HELP_WITHOUT_SETTINGS_SNIPPET.format(args=["sen", "list", "api", "--help"])
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=_clean_env(),
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Usage" in proc.stdout or "usage" in proc.stdout
    assert "BOOM" not in proc.stderr and "BOOM" not in proc.stdout


@BARE_MODE_SKIP
def test_console_script_sen_naked_behaviour_parked():
    pass
