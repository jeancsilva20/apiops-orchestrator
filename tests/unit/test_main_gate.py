import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import apiops_orchestrator.main as main_mod
from apiops_orchestrator.adapters.inbound.cli.cli_adapter import CliError
from apiops_orchestrator.config.settings import Settings


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


def test_login_service_factory_uses_project_root_for_session_store(tmp_path):
    settings = _stub_settings(project_root=tmp_path)

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
