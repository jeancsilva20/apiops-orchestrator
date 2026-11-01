"""Use-cases dos comandos de navegação: `sen get ...` e `sen export api`.

Tudo aqui é leitura. O serviço lê a API inteira uma vez (`GET /apis/{id}`, que
já traz as revisões com recursos e interceptors inline) e delega a leitura ao
domínio (`api_navigation`, `repo_materializer`). Visibilidade segue a regra dos
demais comandos: quem não vê tudo passa pelo catálogo e pela guarda antes de
ler o Manager cru; API invisível e inexistente respondem o mesmo.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from apiops_orchestrator.application.enums.manager_failure_kind_enum import (
    ManagerFailureKind,
)
from apiops_orchestrator.application.exceptions.navigation_exceptions import (
    NavigationApiNotFound,
    NavigationCustomNotFound,
    NavigationError,
    NavigationInterceptorNotFound,
    NavigationPlatformError,
    NavigationRevisionNotFound,
    NavigationScopeNotFound,
)
from apiops_orchestrator.application.services.api_access_guard import ApiAccessGuard
from apiops_orchestrator.application.services.manager_failure_translator import (
    classify_manager_failure,
    manager_failure_message,
)
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiError,
    ManagerApiPort,
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)
from apiops_orchestrator.domain.services import api_navigation as nav
from apiops_orchestrator.domain.services.repo_materializer import (
    MaterializationResult,
    materialize,
)

logger = logging.getLogger(__name__)

_PORT_FAILURES = (ManagerApiTransportRejectedError, ManagerApiTransportUnavailableError)


def _revision_label(number: Optional[int], revision_id: Optional[int]) -> str:
    if revision_id is not None:
        return f"de id {revision_id}"
    return f"de número {number}"


class ApiNavigationService:
    def __init__(
        self, manager_api: ManagerApiPort, session: Optional[LoginSession] = None
    ):
        self.manager_api = manager_api
        self.session = session
        self._guard = ApiAccessGuard(session)

    # ------------------------------------------------------------------ leitura

    def load_api(self, api_id: int) -> Dict[str, Any]:
        """A API crua do Manager, já com a visibilidade conferida."""
        try:
            if not self._guard.sees_everything():
                entry = self.manager_api.list_api_detail(api_id)
                if entry is None or not self._guard.can_see(entry.visibility()):
                    raise NavigationApiNotFound(api_id)
            api = self.manager_api.get_api_by_id(api_id)
        except _PORT_FAILURES as exc:
            raise self._translate(exc, api_id=api_id) from exc
        if not isinstance(api, dict) or api.get("id") is None:
            raise NavigationApiNotFound(api_id)
        return api

    def revision(
        self,
        api_id: int,
        number: Optional[int] = None,
        revision_id: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """`(api, revisão)`: pelo número da UI, pelo id, ou a corrente."""
        api = self.load_api(api_id)
        revision = nav.select_revision(api, number=number, revision_id=revision_id)
        if revision is None:
            raise NavigationRevisionNotFound(
                api_id,
                _revision_label(number, revision_id),
                nav.available_revision_numbers(api),
            )
        return api, revision

    # ------------------------------------------------------------------ níveis

    def api_detail(self, api_id: int) -> Dict[str, Any]:
        return nav.api_summary(self.load_api(api_id))

    def structure(
        self,
        api_id: int,
        number: Optional[int] = None,
        revision_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        api, revision = self.revision(api_id, number, revision_id)
        return nav.structure(api, revision)

    def interceptors(
        self,
        api_id: int,
        number: Optional[int] = None,
        revision_id: Optional[int] = None,
        *,
        resource: Optional[str] = None,
        operation: Optional[str] = None,
        effective: bool = False,
        include_content: bool = False,
    ) -> Dict[str, Any]:
        api, revision = self.revision(api_id, number, revision_id)
        document = nav.scope_flows(
            api,
            revision,
            resource=resource,
            operation=operation,
            effective=effective,
            include_content=include_content,
        )
        if document is None:
            selector = " ".join(
                part
                for part in (
                    f"--resource {resource!r}" if resource else "",
                    f"--operation {operation!r}" if operation else "",
                )
                if part
            )
            raise NavigationScopeNotFound(api_id, selector)
        return document

    def interceptor(
        self,
        api_id: int,
        item_id: int,
        number: Optional[int] = None,
        revision_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        api, revision = self.revision(api_id, number, revision_id)
        found = nav.find_interceptor(revision, item_id)
        if found is None:
            raise NavigationInterceptorNotFound(api_id, item_id)
        scope, item = found
        return nav.describe_interceptor(api, revision, scope, item)

    def custom_interceptor(self, custom_id: int) -> Dict[str, Any]:
        try:
            custom = self.manager_api.get_custom_interceptor_by_id(custom_id)
        except _PORT_FAILURES as exc:
            raise self._translate(exc) from exc
        if not custom:
            raise NavigationCustomNotFound(custom_id)
        return {
            "id": custom.get("id"),
            "name": custom.get("name"),
            "script": custom.get("script"),
        }

    def swagger(
        self,
        api_id: int,
        number: Optional[int] = None,
        revision_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        _, revision = self.revision(api_id, number, revision_id)
        try:
            return self.manager_api.get_revision_swagger(int(revision["id"]))
        except _PORT_FAILURES as exc:
            raise self._translate(exc) from exc
        except ManagerApiError as exc:
            # Resposta fora do contrato (ex.: swagger que não é JSON).
            logger.info("navigation.swagger.unexpected type=%s", type(exc).__name__)
            raise NavigationPlatformError(
                manager_failure_message(ManagerFailureKind.INTERNAL) or str(exc)
            ) from exc

    def export(
        self,
        api_id: int,
        number: Optional[int] = None,
        revision_id: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], MaterializationResult]:
        """Árvore canônica da revisão (o mesmo layout que `sen validate` lê)."""
        api, revision = self.revision(api_id, number, revision_id)
        return api, revision, materialize(api, revision)

    # ------------------------------------------------------------------ falhas

    @staticmethod
    def _translate(
        exc: ManagerApiTransportRejectedError | ManagerApiTransportUnavailableError,
        api_id: Optional[int] = None,
    ) -> NavigationError:
        kind = classify_manager_failure(exc)
        if kind is ManagerFailureKind.NOT_FOUND and api_id is not None:
            return NavigationApiNotFound(api_id)
        if kind is ManagerFailureKind.NOT_FOUND:
            kind = ManagerFailureKind.INTERNAL
        return NavigationPlatformError(manager_failure_message(kind) or str(exc))
