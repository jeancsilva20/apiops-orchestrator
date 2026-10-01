from abc import abstractmethod, ABC
from datetime import datetime
from typing import Optional

from apiops_orchestrator.domain.models.login_session_model import LoginSession


class SessionStoreError(Exception):
    """Falha de persistência/leitura da sessão local.

    Nunca carrega conteúdo da sessão (apenas orientação de ação). Parte do
    contrato do port: `save` levanta este sinal; `load` NUNCA levanta —
    sessão ausente, corrompida ou expirada é `None` ("session absent").
    """


class SessionStorePort(ABC):
    """Outbound port de persistência da sessão autenticada (`sen login`).

    A models são a autoridade de validação: implementações gravam/lem o
    estado tipado; corrupt/legacy/expired/truncated resolvidos por elas.
    """

    @abstractmethod
    def save(self, session: LoginSession) -> None:
        """Persiste a sessão completa de forma atômica; falha → SessionStoreError."""
        pass

    @abstractmethod
    def load(self, now: Optional[datetime] = None) -> Optional[LoginSession]:
        """Devolve a sessão válida armazenada ou `None` (ausente/inválida/expirada)."""
        pass
