from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel

PROFILE_DEVELOPER = "developer"
PROFILE_SUPER_ADMIN = "super-admin"

Profile = Literal["developer", "super-admin"]


class LoginSession(BaseModel):
    """Authenticated session returned by the Orchestrator.

    Identity fields describe a `developer` session, `adminAccessToken` a
    `super-admin` one. The guarded combinations make inconsistent states
    unrepresentable: a legacy (flat) payload, an unknown profile or an empty
    scope always fails model validation, which lets persistence treat it as
    "session absent".
    """

    accessToken: str
    tokenType: str
    expiresIn: int
    scope: str
    profile: Profile
    expiresAt: Optional[datetime] = None

    # Developer-only identity fields (requirement when profile is developer).
    userName: Optional[str] = None
    userEmail: Optional[str] = None
    userGroups: Optional[List[str]] = None

    # Super-admin-only privileged token: kept in memory only, never persisted.
    adminAccessToken: Optional[str] = None

    def model_post_init(self, __context) -> None:
        self._ensure_guarded_state()
        received_at = datetime.now(timezone.utc)
        if self.expiresAt is None:
            self.expiresAt = received_at + timedelta(seconds=self.expiresIn)

    def _ensure_guarded_state(self) -> None:
        """Reject impossible profile/field combinations via ValueError.

        Detail messages carry field names only, never credential values.
        """
        if not (self.scope or "").strip():
            raise ValueError("'scope' não pode ser vazio.")

        if self.profile == PROFILE_DEVELOPER:
            if not (self.userName or "").strip():
                raise ValueError("Perfil 'developer' exige 'userName'.")
            if not (self.userEmail or "").strip():
                raise ValueError("Perfil 'developer' exige 'userEmail'.")
            if not self.userGroups:
                raise ValueError("Perfil 'developer' exige 'userGroups' não vazio.")
        elif self.profile == PROFILE_SUPER_ADMIN:
            # Absence is tolerated: the store never persists the privileged
            # token, so a reloaded session stays valid without it.
            pass

    @property
    def is_super_admin(self) -> bool:
        return self.profile == PROFILE_SUPER_ADMIN

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        current = now or datetime.now(timezone.utc)
        if self.expiresAt is None:
            return True
        return self.expiresAt <= current
