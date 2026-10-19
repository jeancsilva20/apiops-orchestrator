class LoginError(Exception):
    """Base for categorized failures of the `sen login` flow."""

    exit_code = 1

    def __init__(self, message: str, exit_code: int | None = None):
        self.message = message
        if exit_code is not None:
            self.exit_code = exit_code
        super().__init__(self.message)


class CredentialNotFoundError(LoginError):
    """No SEN_CREDENTIALS available before any network call."""

    exit_code = 2


class AuthenticationRejectedError(LoginError):
    """Auth API refused the credential (HTTP 4xx surfaced by the shared HTTP client)."""

    exit_code = 3


class AuthenticationUnavailableError(LoginError):
    """Auth API unreachable or exhausted 5xx retries."""

    exit_code = 1


class LoginProtocolError(LoginError):
    """Successful HTTP response missing/invalid required session fields."""

    exit_code = 4


class SessionPersistenceError(LoginError):
    """Failed to write/read the local hidden session file."""

    exit_code = 5
