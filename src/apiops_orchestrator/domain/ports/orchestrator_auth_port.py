from abc import abstractmethod, ABC


class OrchestratorAuthPort(ABC):
    """Outbound port for the Orchestrator Auth API (`/orq-auth/v1`)."""

    @abstractmethod
    def login(self, credential_b64: str) -> dict:
        """Performs the login request with the Base64 credential passed intact and returns the raw response dict."""
        pass

    @abstractmethod
    def validate_access_token(self, access_token: str) -> dict:
        """Validates an existing access token and returns the raw response dict."""
        pass
