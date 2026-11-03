"""Access rules of a session: APIOps team, write scope and pipeline credential."""

from enum import Enum
from typing import Any, Iterable, Optional

from apiops_orchestrator.domain.models.login_session_model import LoginSession

APIOPS_TEAM = "apiops"
WRITE_SCOPE = "write"


class Access(Enum):
    """A requirement a command places on the session."""

    APIOPS_TEAM = "apiops-team"
    WRITE = "write"
    PIPELINE = "pipeline"


def _fold(value: Any) -> str:
    return str(value or "").strip().lower()


def meets(session: LoginSession, access: Access) -> bool:
    """Tells whether the session meets the requirement; super-admin meets all."""
    if session.is_super_admin:
        return True
    if access is Access.APIOPS_TEAM:
        return any(_fold(group) == APIOPS_TEAM for group in session.userGroups or [])
    if access is Access.WRITE:
        return _fold(session.scope) == WRITE_SCOPE
    return False


def first_unmet(session: LoginSession, required: Iterable[Access]) -> Optional[Access]:
    """First requirement, in the given order, that the session does not meet."""
    return next((access for access in required if not meets(session, access)), None)
