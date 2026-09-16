import json
import os
from datetime import datetime, timezone

import pytest

from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.infrastructure.secure_storage.session_store import (
    SESSION_FILE_NAME,
    SessionStore,
    SessionStorageError,
)


SESSION = LoginSession(
    access_token="SECRET-TOKEN-VALUE",
    token_type="Bearer",
    expires_in=3600,
    user_groups=["APIOps"],
    user_email="dev@sensedia.com",
    username="dev",
)


def _session(expires_in=3600):
    return LoginSession(
        access_token="SECRET-TOKEN-VALUE",
        token_type="Bearer",
        expires_in=expires_in,
        user_groups=["APIOps"],
        user_email="dev@sensedia.com",
        username="dev",
    )


def test_save_writes_full_content_atomically(tmp_path):
    store = SessionStore(directory=tmp_path)
    store.save(SESSION)

    raw = json.loads((tmp_path / SESSION_FILE_NAME).read_text(encoding="utf-8"))
    assert raw["access_token"] == "SECRET-TOKEN-VALUE"
    assert raw["token_type"] == "Bearer"
    assert raw["expires_in"] == 3600
    assert "expires_at" in raw
    assert raw["user_groups"] == ["APIOps"]
    assert raw["user_email"] == "dev@sensedia.com"
    assert raw["username"] == "dev"
    leftovers = [p for p in tmp_path.iterdir() if p.name != SESSION_FILE_NAME]
    assert leftovers == []


def test_load_returns_valid_session(tmp_path):
    store = SessionStore(directory=tmp_path)
    store.save(SESSION)
    loaded = store.load(now=datetime.now(timezone.utc))
    assert loaded is not None
    assert loaded.access_token == "SECRET-TOKEN-VALUE"


def test_load_returns_none_when_absent(tmp_path):
    store = SessionStore(directory=tmp_path)
    assert store.load() is None


def test_load_treats_expired_session_as_absent(tmp_path):
    store = SessionStore(directory=tmp_path)
    store.save(_session(expires_in=-10))
    assert store.load() is None


def test_load_treats_corrupted_file_as_absent(tmp_path):
    store = SessionStore(directory=tmp_path)
    (tmp_path / SESSION_FILE_NAME).write_text("{ not-json", encoding="utf-8")
    assert store.load() is None


def test_replace_leaves_no_temp_leftovers(tmp_path):
    store = SessionStore(directory=tmp_path)
    store.save(_session(expires_in=10))
    store.save(_session(expires_in=3600))
    loaded = store.load()
    assert loaded is not None
    assert loaded.expires_in == 3600
    leftovers = [p for p in tmp_path.iterdir() if p.name != SESSION_FILE_NAME]
    assert leftovers == []


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_saved_file_has_owner_only_permissions(tmp_path):
    store = SessionStore(directory=tmp_path)
    store.save(SESSION)
    mode = (tmp_path / SESSION_FILE_NAME).stat().st_mode & 0o777
    assert mode == 0o600


def test_io_failure_maps_to_sanitized_categorized_error(tmp_path, monkeypatch):
    store = SessionStore(directory=tmp_path)

    def boom(src, dst):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(SessionStorageError) as excinfo:
        store.save(SESSION)
    assert "SECRET-TOKEN-VALUE" not in str(excinfo.value)
    assert "não foi possível gravar" in str(excinfo.value).lower()
