from datetime import datetime, timedelta, timezone

from apiops_orchestrator.domain.models.login_session_model import LoginSession


RESPONSE_SAMPLE = {
    "access_token": "ZWM4MmMzNjYtZTMyMS00YmM1LWI5OWItZDdjZWYzMDQ4MjNiOmY0NjA0MmY5LWQ3MjYtNDJjNy1hZmI4LWY2M2RlMWRjZGY1Mg==",
    "token_type": "Bearer",
    "expires_in": 43200,
    "user_groups": ["APIOps", "Lab-tech"],
    "user_email": "isaac.machado@sensedia.com",
    "username": "isaac.machado",
}


def test_session_computed_expiry_matches_expires_in():
    before = datetime.now(timezone.utc)
    session = LoginSession(**RESPONSE_SAMPLE)
    assert session.expires_at is not None
    elapsed = (session.expires_at - before).total_seconds()
    assert 43199 <= elapsed <= 43201


def test_session_roundtrip_via_json_keeps_all_fields():
    session = LoginSession(**RESPONSE_SAMPLE)
    restored = LoginSession.model_validate_json(session.model_dump_json())
    assert restored.access_token == RESPONSE_SAMPLE["access_token"]
    assert restored.token_type == "Bearer"
    assert restored.user_groups == ["APIOps", "Lab-tech"]
    assert restored.user_email == RESPONSE_SAMPLE["user_email"]
    assert restored.username == RESPONSE_SAMPLE["username"]
    assert restored.expires_at == session.expires_at


def test_is_expired_semantics():
    session = LoginSession(**RESPONSE_SAMPLE)
    assert session.expires_at is not None
    before_expiry = session.expires_at - timedelta(seconds=1)
    after_expiry = session.expires_at + timedelta(seconds=1)
    assert session.is_expired(after_expiry) is True
    assert session.is_expired(before_expiry) is False
