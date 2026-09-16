import sys
from unittest.mock import MagicMock

import pytest

import apiops_orchestrator.main as main_mod
from apiops_orchestrator.adapters.inbound.cli.cli_adapter import CliError


class RecordingApp:
    def __init__(self):
        self.calls = []

    def __call__(self, obj=None):
        self.calls.append(obj)


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
