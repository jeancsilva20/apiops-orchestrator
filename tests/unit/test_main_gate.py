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


def test_invoked_argv_builds_lazy_factories(recording_app, monkeypatch):
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

    monkeypatch.setattr(main_mod, "build_login_service_factory", login_factory)
    monkeypatch.setattr(main_mod, "build_listing_service_factory", listing_factory)

    monkeypatch.setattr(sys, "argv", ["main.py", "sen", "login"])
    main_mod.main()

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

    monkeypatch.setattr(sys, "argv", ["main.py", "sen", "list", "api"])
    main_mod.main()

    obj = fake_app.calls[0]
    assert obj["api_listing_service_factory"] is listing_marker


@pytest.mark.parametrize("argv0", ["main.py", r"C:\venv\Scripts\sen.exe"])
def test_no_args_routes_to_sen_help(recording_app, monkeypatch, argv0):
    load_spy = MagicMock(side_effect=AssertionError("Settings must not load"))
    monkeypatch.setattr(main_mod, "_load_settings", load_spy)
    monkeypatch.setattr(sys, "argv", [argv0])

    main_mod.main()

    assert sys.argv == [argv0, "sen"]
    assert len(recording_app.calls) == 1
    load_spy.assert_not_called()


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


def test_no_args_shows_sen_help_without_touching_settings():
    """Sem argumentos mostra o help do `sen` (exit 2 do Click) com Settings venenada."""
    snippet = HELP_WITHOUT_SETTINGS_SNIPPET.format(args=[])
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=_clean_env(),
        timeout=60,
    )

    assert proc.returncode == 2, proc.stderr
    assert "Usage" in proc.stdout or "usage" in proc.stdout
    assert "login" in proc.stdout
    assert "BOOM" not in proc.stderr and "BOOM" not in proc.stdout
