from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from apiops_orchestrator.domain.models.login_session_model import LoginSession

TOKEN_DEV = "QUJDREVG"
TOKEN_ADMIN = "REVGQUND"


def developer_payload() -> dict:
    return {
        "accessToken": TOKEN_DEV,
        "tokenType": "Bearer",
        "expiresIn": 43200,
        "scope": "apis/read",
        "profile": "developer",
        "userName": "ci.runner",
        "userEmail": "runner@company.test",
        "userGroups": ["APIOps"],
    }


def super_admin_payload(with_admin_token: bool = True) -> dict:
    payload = {
        "accessToken": TOKEN_ADMIN,
        "tokenType": "Bearer",
        "expiresIn": 7200,
        "scope": "admin",
        "profile": "super-admin",
    }
    if with_admin_token:
        payload["adminAccessToken"] = TOKEN_ADMIN
    return payload


@pytest.mark.parametrize(
    "field",
    ["userName", "userEmail", "userGroups", "scope"],
)
def test_developer_requires_identity_fields(field):
    payload = developer_payload()
    del payload[field]
    with pytest.raises(ValidationError):
        LoginSession(**payload)


def test_developer_user_groups_presence_overrides_values():
    payload = developer_payload()
    payload["userGroups"] = []
    with pytest.raises(ValidationError):
        LoginSession(**payload)

    payload["userGroups"] = None
    with pytest.raises(ValidationError):
        LoginSession(**payload)


@pytest.mark.parametrize("scope", ["", "   "])
def test_scope_required_for_any_profile(scope):
    for payload_builder in (developer_payload, super_admin_payload):
        payload = payload_builder()
        payload["scope"] = scope
        with pytest.raises(ValidationError):
            LoginSession(**payload)


def test_developer_carrying_admin_token_tolerates_the_field():
    payload = developer_payload()
    payload["adminAccessToken"] = TOKEN_ADMIN
    session = LoginSession(**payload)
    assert session.adminAccessToken == TOKEN_ADMIN
    assert session.is_super_admin is False


def test_super_admin_valid_without_admin_token_reload_assumption():
    session = LoginSession(**super_admin_payload(with_admin_token=False))
    assert session.is_super_admin is True
    assert session.adminAccessToken is None


def test_superuser_with_admin_token_roundtrip_keeps_it_in_memory():
    payload = super_admin_payload()
    restored = LoginSession.model_validate_json(
        LoginSession(**payload).model_dump_json()
    )
    assert restored.adminAccessToken == TOKEN_ADMIN


def test_legacy_flat_payload_fails_model_validation():
    legacy = {
        "access_token": TOKEN_DEV,
        "token_type": "Bearer",
        "expires_in": 43200,
        "user_groups": ["APIOps"],
        "user_email": "runner@company.test",
        "username": "ci.runner",
    }
    with pytest.raises(ValidationError):
        LoginSession(**legacy)


def test_session_computed_expiry_matches_expires_in():
    before = datetime.now(timezone.utc)
    session = LoginSession(**developer_payload())
    assert session.expiresAt is not None
    elapsed = (session.expiresAt - before).total_seconds()
    assert 43199 <= elapsed <= 43201


def test_session_roundtrip_via_json_keeps_all_fields():
    session = LoginSession(**developer_payload())
    restored = LoginSession.model_validate_json(session.model_dump_json())
    assert restored.accessToken == TOKEN_DEV
    assert restored.tokenType == "Bearer"
    assert restored.userGroups == ["APIOps"]
    assert restored.userEmail == "runner@company.test"
    assert restored.userName == "ci.runner"
    assert restored.scope == "apis/read"
    assert restored.profile == "developer"
    assert restored.expiresAt == session.expiresAt


def test_is_expired_semantics():
    session = LoginSession(**developer_payload())
    assert session.expiresAt is not None
    before_expiry = session.expiresAt - timedelta(seconds=1)
    after_expiry = session.expiresAt + timedelta(seconds=1)
    assert session.is_expired(after_expiry) is True
    assert session.is_expired(before_expiry) is False
