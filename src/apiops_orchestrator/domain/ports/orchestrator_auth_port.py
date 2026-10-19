from abc import abstractmethod, ABC


class OrchestratorAuthError(Exception):
    """Base dos sinais de contrato do port de autenticação do Orchestrator."""


class AuthEndpointNotConfiguredError(OrchestratorAuthError):
    """Endpoint/path de autenticação ausente nas configurações.

    Levantado pelo adapter ANTES de qualquer chamada de rede (fail-fast).
    `missing` contém apenas NOMES de chaves (nunca valores), permitindo que
    a application componha mensagem educativa sem conhecer wire/config.
    """

    def __init__(self, missing_keys: list[str], message: str) -> None:
        self.missing_keys = list(missing_keys)
        super().__init__(message)


class AuthTransportRejectedError(OrchestratorAuthError):
    """A Auth API recusou o pedido (HTTP 4xx). Sinal transport-level."""


class AuthTransportUnavailableError(OrchestratorAuthError):
    """Auth API inalcançável ou 5xx persistente após esgotar retries."""


class OrchestratorAuthPort(ABC):
    """Outbound port for the Orchestrator Auth API (`/orq-auth/v1`).

    Contrato de erros (parte da assinatura do port, à la "exceptions as
    outcomes"): implementações levantam APENAS os sinais tipados abaixo;
    exceções de transporte concretas (requests, HttpClient*, frameworks)
    NÃO atravessam o port — quem chama não precisa conhecê-las.
    """

    @abstractmethod
    def login(self, credential_b64: str) -> dict:
        """Performs the login request with the Base64 credential passed intact and returns the raw response dict."""
        pass

    @abstractmethod
    def validate_access_token(self, access_token: str) -> dict:
        """Validates an existing access token and returns the raw response dict."""
        pass
