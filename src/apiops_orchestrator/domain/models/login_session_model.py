from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pydantic import BaseModel


class LoginSession(BaseModel):
    """Authenticated session returned by the Orchestrator Auth API (`/orq-auth/v1`)."""

    access_token: str
    token_type: str
    expires_in: int
    user_groups: List[str]
    user_email: str
    username: str
    expires_at: Optional[datetime] = None

    def model_post_init(self, __context) -> None:
        received_at = datetime.now(timezone.utc)
        if self.expires_at is None:
            self.expires_at = received_at + timedelta(seconds=self.expires_in)

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        current = now or datetime.now(timezone.utc)
        if self.expires_at is None:
            return True
        return self.expires_at <= current
