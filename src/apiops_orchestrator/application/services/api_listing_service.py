from typing import Any, Dict, List, Optional

from apiops_orchestrator.domain.models.api_collection_model import (
    ApiCollection,
    InsufficientSessionError,
    attach_last_revision,
    revision_basic_map,
)
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort

_INSUFFICIENT_GROUPS_MESSAGE = (
    "Sua sessão não possui grupos de acesso, refaça `sen login` ou "
    "acione o time de acesso."
)


class ApiListingService:
    def __init__(
        self,
        manager_api: ManagerApiPort,
        session: Optional[LoginSession] = None,
    ):
        self.manager_api = manager_api
        self.session = session

    def list_apis(
        self,
        api_id: Optional[int] = None,
        query: Optional[str] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves APIs. With api_id, returns the single API detail.
        Otherwise, full listing with visibility filtering (when a user
        session is injected by the composition root), then filter/order/
        window client-side.

        Without an injected session the listing is passed through unfiltered —
        legacy pipeline behavior preserved (visibility applies only to `sen list api`).
        """
        if api_id is not None:
            api = self.manager_api.get_api_by_id(api_id)
            return [api]

        if self.session is not None:
            super_admin = self.session.is_super_admin
            groups = list(self.session.userGroups or [])
            if not super_admin and not groups:
                # Fail-fast: bloqueio antes de qualquer requisicao.
                raise InsufficientSessionError(_INSUFFICIENT_GROUPS_MESSAGE)

        collection = ApiCollection.from_raw(self.manager_api.get_apis())

        # Enriquecimento LAST REV: 1 chamada unica; degrada silenciosamente
        # para '-' quando o catalogo nao estiver disponivel.
        try:
            revision_map = revision_basic_map(self.manager_api.get_revisions_basic())
            collection = ApiCollection.from_raw(
                attach_last_revision(collection.rows(), revision_map)
            )
        except Exception:
            pass

        if self.session is not None:
            collection = collection.visible_to(
                self.session.userName,
                list(self.session.userGroups or []),
                self.session.is_super_admin,
            )

        return (
            collection.filtered_by(query)
            .sorted_by_id()
            .window(offset, limit)
            .rows()
        )
