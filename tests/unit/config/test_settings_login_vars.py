import pytest
from pydantic_settings import SettingsConfigDict

from apiops_orchestrator.config.settings import Settings

REQUIRED_VARS = [
    "HOST",
    "OAUTH_CLIENT_ID",
    "OAUTH_CLIENT_SECRET",
    "REQUEST_TIMEOUT",
    "API_ID",
    "AUTH_HOST",
    "AUTH_LOGIN_PATH",
]


@pytest.fixture(autouse=True)
def _isolate_settings_sources(monkeypatch):
    monkeypatch.setattr(
        Settings,
        "model_config",
        SettingsConfigDict(env_file=None, env_file_encoding="utf-8", extra="ignore"),
    )


def _seed_required(monkeypatch):
    monkeypatch.setenv("HOST", "https://plat.example.com")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "id")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("REQUEST_TIMEOUT", "30")
    monkeypatch.setenv("API_ID", "1")
    monkeypatch.setenv("AUTH_HOST", "https://auth.example.com")
    monkeypatch.setenv("AUTH_LOGIN_PATH", "/cli-2/orq-auth/v1/oauth2/token")
    monkeypatch.delenv("SEN_CREDENTIALS", raising=False)


def test_sen_credentials_defaults_to_none(monkeypatch):
    _seed_required(monkeypatch)
    settings = Settings()
    assert settings.SEN_CREDENTIALS is None


def test_login_auth_variable_values_are_loaded(monkeypatch):
    _seed_required(monkeypatch)
    monkeypatch.setenv("SEN_CREDENTIALS", "QUJDREVG")
    monkeypatch.setenv("AUTH_HOST", "https://qa.example.com")
    monkeypatch.setenv("AUTH_LOGIN_PATH", "/qa/orq-auth/v1/oauth2/token")
    settings = Settings()
    assert settings.SEN_CREDENTIALS == "QUJDREVG"
    assert settings.AUTH_HOST == "https://qa.example.com"
    assert settings.AUTH_LOGIN_PATH == "/qa/orq-auth/v1/oauth2/token"


def test_every_required_setting_is_enforced(monkeypatch):
    for missing_var in REQUIRED_VARS:
        _seed_required(monkeypatch)
        monkeypatch.delenv(missing_var, raising=False)
        raised = False
        try:
            Settings()
        except Exception:
            raised = True
        assert raised, f"Expected error when {missing_var} is missing"


def test_sen_credentials_is_optional_at_settings_level(monkeypatch):
    _seed_required(monkeypatch)
    settings = Settings()
    assert settings.SEN_CREDENTIALS is None
    assert settings.OAUTH_CLIENT_ID == "id"
    assert settings.OAUTH_CLIENT_SECRET == "secret"
