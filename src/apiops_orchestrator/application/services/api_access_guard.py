from typing import Optional

from apiops_orchestrator.domain.models.api_visibility_model import ApiVisibility
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.services.api_visibility import visible_to


class ApiAccessGuard:
    """Aplica a regra de `api-visibility` à sessão do usuário.

    Devolve só a decisão: cada comando responde à API invisível com a própria
    exceção, como responde à API inexistente.
    """

    def __init__(self, session: Optional[LoginSession]):
        self._session = session

    def sees_everything(self) -> bool:
        """Sem sessão ou sessão de super admin: nenhuma API é escondida."""
        return self._session is None or self._session.is_super_admin

    def can_see(self, visibility: ApiVisibility) -> bool:
        """Diz se a sessão enxerga a API com essa visibilidade."""
        if self._session is None:
            return True
        return visible_to(
            visibility,
            self._session.userName,
            list(self._session.userGroups or []),
            self._session.is_super_admin,
        )
