import pytest
from pydantic_settings import SettingsConfigDict

from apiops_orchestrator.config.settings import Settings

REQUIRED_VARS = [
    "HOST",
    "REQUEST_TIMEOUT",
    "API_ID",
    "AUTH_HOST",
    "AUTH_LOGIN_PATH",
]

OPTIONAL_VARS = [
    "OAUTH_CLIENT_ID",
    "OAUTH_CLIENT_SECRET",
    "SEN_CREDENTIALS",
    "AUTH_VALIDATE_PATH",
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


def test_oauth_pair_and_credentials_are_optional_now(monkeypatch):
    for optional_var in OPTIONAL_VARS:
        _seed_required(monkeypatch)
        monkeypatch.delenv(optional_var, raising=False)

        settings = Settings()

        assert getattr(settings, optional_var) is None, optional_var


def _clean_auth_block(monkeypatch):
    for var in ("SEN_CREDENTIALS", "AUTH_HOST", "AUTH_LOGIN_PATH"):
        monkeypatch.delenv(var, raising=False)


def _write_file(path, entries):
    path.write_text(
        "\n".join(f"{key}='{value}'" for key, value in entries.items()),
        encoding="utf-8",
    )
    return path


def _configure_sources(monkeypatch, env_file=None, sen_file=None):
    files = tuple(str(f) for f in (env_file, sen_file) if f)
    monkeypatch.setattr(
        Settings,
        "model_config",
        SettingsConfigDict(env_file=files, env_file_encoding="utf-8", extra="ignore"),
    )


def test_package_root_points_to_module_directory():
    from apiops_orchestrator.config import settings as settings_module

    settings_module.PACKAGE_ROOT.joinpath("config", "settings.py").exists()
    assert settings_module.PACKAGE_ROOT.name == "apiops_orchestrator"


def test_sen_file_alone_provides_auth_block(tmp_path, monkeypatch):
    _clean_auth_block(monkeypatch)
    monkeypatch.setenv("HOST", "https://plat.example.com")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "id")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("REQUEST_TIMEOUT", "30")
    monkeypatch.setenv("API_ID", "1")
    sen_file = _write_file(
        tmp_path / ".sen",
        {
            "SEN_CREDENTIALS": "QUJDREVG",
            "AUTH_HOST": "https://auth.example.com",
            "AUTH_LOGIN_PATH": "/cli-2/orq-auth/v1/oauth2/token",
        },
    )
    _configure_sources(monkeypatch, sen_file=sen_file)

    settings = Settings()

    assert settings.SEN_CREDENTIALS == "QUJDREVG"
    assert settings.AUTH_HOST == "https://auth.example.com"
    assert settings.AUTH_LOGIN_PATH == "/cli-2/orq-auth/v1/oauth2/token"


def test_env_file_alone_still_supports_auth_block(tmp_path, monkeypatch):
    _clean_auth_block(monkeypatch)
    monkeypatch.setenv("HOST", "https://plat.example.com")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "id")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("REQUEST_TIMEOUT", "30")
    monkeypatch.setenv("API_ID", "1")
    env_file = _write_file(
        tmp_path / ".env",
        {
            "SEN_CREDENTIALS": "RUNFB0JC",
            "AUTH_HOST": "https://env.example.com",
            "AUTH_LOGIN_PATH": "/env/orq-auth/v1/oauth2/token",
        },
    )
    _configure_sources(monkeypatch, env_file=env_file)

    settings = Settings()

    assert settings.SEN_CREDENTIALS == "RUNFB0JC"
    assert settings.AUTH_HOST == "https://env.example.com"
    assert settings.AUTH_LOGIN_PATH == "/env/orq-auth/v1/oauth2/token"


def test_sen_file_takes_precedence_over_env_file(tmp_path, monkeypatch):
    _clean_auth_block(monkeypatch)
    monkeypatch.setenv("HOST", "https://plat.example.com")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "id")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("REQUEST_TIMEOUT", "30")
    monkeypatch.setenv("API_ID", "1")
    env_file = _write_file(
        tmp_path / ".env",
        {
            "SEN_CREDENTIALS": "RUNFB0JC",
            "AUTH_HOST": "https://env.example.com",
            "AUTH_LOGIN_PATH": "/env/orq-auth/v1/oauth2/token",
        },
    )
    sen_file = _write_file(
        tmp_path / ".sen",
        {
            "SEN_CREDENTIALS": "QUJDREVG",
            "AUTH_HOST": "https://sen.example.com",
            "AUTH_LOGIN_PATH": "/sen/orq-auth/v1/oauth2/token",
        },
    )
    _configure_sources(monkeypatch, env_file=env_file, sen_file=sen_file)

    settings = Settings()

    assert settings.AUTH_HOST == "https://sen.example.com"
    assert settings.AUTH_LOGIN_PATH == "/sen/orq-auth/v1/oauth2/token"
    assert settings.SEN_CREDENTIALS == "QUJDREVG"


def test_process_environment_beats_both_files(tmp_path, monkeypatch):
    _clean_auth_block(monkeypatch)
    monkeypatch.setenv("HOST", "https://plat.example.com")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "id")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("REQUEST_TIMEOUT", "30")
    monkeypatch.setenv("API_ID", "1")
    monkeypatch.setenv("AUTH_HOST", "https://process.example.com")
    env_file = _write_file(
        tmp_path / ".env",
        {
            "SEN_CREDENTIALS": "RUNFB0JC",
            "AUTH_HOST": "https://env.example.com",
            "AUTH_LOGIN_PATH": "/env/orq-auth/v1/oauth2/token",
        },
    )
    sen_file = _write_file(
        tmp_path / ".sen",
        {
            "SEN_CREDENTIALS": "QUJDREVG",
            "AUTH_HOST": "https://sen.example.com",
            "AUTH_LOGIN_PATH": "/sen/orq-auth/v1/oauth2/token",
        },
    )
    _configure_sources(monkeypatch, env_file=env_file, sen_file=sen_file)

    settings = Settings()

    assert settings.AUTH_HOST == "https://process.example.com"
    assert settings.AUTH_LOGIN_PATH == "/sen/orq-auth/v1/oauth2/token"


def test_unknown_keys_in_sen_file_are_ignored(tmp_path, monkeypatch):
    _clean_auth_block(monkeypatch)
    monkeypatch.setenv("HOST", "https://plat.example.com")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "id")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("REQUEST_TIMEOUT", "30")
    monkeypatch.setenv("API_ID", "1")
    monkeypatch.setenv("AUTH_HOST", "https://auth.example.com")
    monkeypatch.setenv("AUTH_LOGIN_PATH", "/cli-2/orq-auth/v1/oauth2/token")
    sen_file = _write_file(tmp_path / ".sen", {"TOTALLY_UNKNOWN_KEY": "noise"})
    _configure_sources(monkeypatch, sen_file=sen_file)

    settings = Settings()

    assert not hasattr(settings, "TOTALLY_UNKNOWN_KEY")
    assert settings.AUTH_HOST == "https://auth.example.com"
