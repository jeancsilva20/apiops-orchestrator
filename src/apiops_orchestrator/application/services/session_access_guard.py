from typing import Optional

from apiops_orchestrator.application.exceptions.access_exceptions import (
    AccessDeniedError,
)
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.services.session_access import Access, first_unmet

TEAM_DENIED = (
    "Sua sessão não pertence ao time APIOps. Peça acesso ao time e faça "
    "`sen login` de novo."
)
WRITE_DENIED = (
    "O `sen {command}` grava no Manager e exige o scope `write`; sua sessão "
    "tem `{scope}`. Peça a permissão e faça `sen login` de novo."
)
PIPELINE_DENIED = "O `sen {command}` só roda com a credencial da esteira."

_MESSAGES = {
    Access.APIOPS_TEAM: TEAM_DENIED,
    Access.WRITE: WRITE_DENIED,
    Access.PIPELINE: PIPELINE_DENIED,
}


def require_access(
    session: Optional[LoginSession],
    *required: Access,
    command: str = "",
    outcome: str = "",
) -> None:
    """Refuses a session outside the APIOps team or missing any of `required`.

    Without a session it does nothing: resolving the admin token refuses it
    with the `sen login` message.
    """
    if session is None:
        return
    unmet = first_unmet(session, (Access.APIOPS_TEAM, *required))
    if unmet is None:
        return
    message = _MESSAGES[unmet].format(command=command, scope=session.scope)
    raise AccessDeniedError(f"{message}\n\n{outcome}" if outcome else message)
