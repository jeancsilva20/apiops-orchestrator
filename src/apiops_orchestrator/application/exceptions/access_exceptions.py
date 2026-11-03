from apiops_orchestrator.application.exceptions.login_exceptions import LoginError


class AccessDeniedError(LoginError):
    """The session lacks the team, scope or credential the command requires."""
