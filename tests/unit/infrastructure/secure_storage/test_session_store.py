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

ACCESS_TOKEN = "QUJDREVG"
ADMIN_TOKEN = "REVGQUNC"


def developer_session(**overrides) -> LoginSession:
    payload = {
        "accessToken": ACCESS_TOKEN,
        "tokenType": "Bearer",
        "expiresIn": 3600,
        "scope": "apis/read",
        "profile": "developer",
        "userName": "ci.runner",
        "userEmail": "runner@company.test",
        "userGroups": ["APIOps"],
    }
    payload.update(overrides)
    return LoginSession(**payload)


def super_admin_session(**overrides) -> LoginSession:
    payload = {
        "accessToken": ADMIN_TOKEN,
        "tokenType": "Bearer",
        "expiresIn": 7200,
        "scope": "admin",
        "profile": "super-admin",
        "adminAccessToken": ADMIN_TOKEN,
    }
    payload.update(overrides)
    return LoginSession(**payload)


def test_save_writes_full_content_atomically(tmp_path):
    store = SessionStore(directory=tmp_path)
    store.save(developer_session())

    raw = json.loads((tmp_path / SESSION_FILE_NAME).read_text(encoding="utf-8"))
    assert raw["accessToken"] == ACCESS_TOKEN
    assert raw["tokenType"] == "Bearer"
    assert raw["expiresIn"] == 3600
    assert raw["scope"] == "apis/read"
    assert raw["profile"] == "developer"
    assert "expiresAt" in raw
    assert raw["userName"] == "ci.runner"
    assert raw["userEmail"] == "runner@company.test"
    assert raw["userGroups"] == ["APIOps"]
    leftovers = [p for p in tmp_path.iterdir() if p.name != SESSION_FILE_NAME]
    assert leftovers == []


def test_save_super_admin_never_persists_admin_token(tmp_path):
    store = SessionStore(directory=tmp_path)
    store.save(super_admin_session())

    raw = json.loads((tmp_path / SESSION_FILE_NAME).read_text(encoding="utf-8"))
    assert "adminAccessToken" not in raw
    assert raw["profile"] == "super-admin"
    assert raw["scope"] == "admin"
    assert raw["accessToken"] == ADMIN_TOKEN


def test_saved_super_admin_reloads_without_privileged_token(tmp_path):
    store = SessionStore(directory=tmp_path)
    store.save(super_admin_session())

    loaded = store.load(now=datetime.now(timezone.utc))

    assert loaded is not None
    assert loaded.is_super_admin is True
    assert loaded.adminAccessToken is None
    assert loaded.accessToken == ADMIN_TOKEN


def test_load_returns_valid_developer_session(tmp_path):
    store = SessionStore(directory=tmp_path)
    store.save(developer_session())
    loaded = store.load(now=datetime.now(timezone.utc))
    assert loaded is not None
    assert loaded.accessToken == ACCESS_TOKEN
    assert loaded.profile == "developer"


def test_load_returns_none_when_absent(tmp_path):
    store = SessionStore(directory=tmp_path)
    assert store.load() is None


def test_load_treats_expired_session_as_absent(tmp_path):
    store = SessionStore(directory=tmp_path)
    store.save(developer_session(expiresIn=-10))
    assert store.load() is None


def test_load_treats_corrupted_file_as_absent(tmp_path):
    store = SessionStore(directory=tmp_path)
    (tmp_path / SESSION_FILE_NAME).write_text("{ not-json", encoding="utf-8")
    assert store.load() is None


def test_load_treats_legacy_flat_session_as_absent(tmp_path):
    store = SessionStore(directory=tmp_path)
    legacy = {
        "access_token": ACCESS_TOKEN,
        "token_type": "Bearer",
        "expires_in": 3600,
        "user_groups": ["APIOps"],
        "user_email": "runner@company.test",
        "username": "ci.runner",
    }
    (tmp_path / SESSION_FILE_NAME).write_text(json.dumps(legacy), encoding="utf-8")
    assert store.load() is None


def test_load_treats_unknown_profile_as_absent(tmp_path):
    store = SessionStore(directory=tmp_path)
    persisted = json.loads(super_admin_session().model_dump_json())
    persisted["profile"] = "nomad"
    (tmp_path / SESSION_FILE_NAME).write_text(json.dumps(persisted), encoding="utf-8")
    assert store.load() is None


def test_replace_leaves_no_temp_leftovers(tmp_path):
    store = SessionStore(directory=tmp_path)
    store.save(developer_session(scope="apis/read", expiresIn=10))
    store.save(developer_session(scope="apis/write", expiresIn=3600))
    loaded = store.load()
    assert loaded is not None
    assert loaded.expiresIn == 3600
    assert loaded.scope == "apis/write"
    leftovers = [p for p in tmp_path.iterdir() if p.name != SESSION_FILE_NAME]
    assert leftovers == []


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_saved_file_has_owner_only_permissions(tmp_path):
    store = SessionStore(directory=tmp_path)
    store.save(developer_session())
    mode = (tmp_path / SESSION_FILE_NAME).stat().st_mode & 0o777
    assert mode == 0o600


def test_io_failure_maps_to_sanitized_categorized_error(tmp_path, monkeypatch):
    store = SessionStore(directory=tmp_path)

    def boom(src, dst):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(SessionStorageError) as excinfo:
        store.save(developer_session())
    assert ACCESS_TOKEN not in str(excinfo.value)
    assert "não foi possível gravar" in str(excinfo.value).lower()
