from datetime import datetime, timezone
from typing import Optional

from apiops_orchestrator.application.exceptions.completeness_exceptions import (
    CompletenessApiNotFound,
    CompletenessDenied,
    CompletenessError,
    CompletenessNotFound,
    CompletenessPlatformError,
    CompletenessUnauthorized,
)
from apiops_orchestrator.application.enums.manager_failure_kind_enum import (
    ManagerFailureKind,
)
from apiops_orchestrator.application.services.api_access_guard import ApiAccessGuard
from apiops_orchestrator.application.services.manager_failure_translator import (
    classify_manager_failure,
    manager_failure_message,
)
from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from apiops_orchestrator.domain.models.catalog_revision_model import (
    CatalogRevisionCompleteness,
)
from apiops_orchestrator.domain.models.completeness_view import (
    CompletenessApi,
    CompletenessContext,
    CompletenessSuggestion,
    CompletenessView,
)
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiPort,
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)

SCHEMA_SEN_COMPLETENESS_V1 = "apiops.sen-completeness/v1"
GATE_PERCENT_V1 = 70.0


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class CompletenessService:
    """Use-case do `sen completeness`: espelho integral de completude por revisão.
    """

    def __init__(self, manager_api: ManagerApiPort, session: Optional[LoginSession] = None):
        self.manager_api = manager_api
        self.session = session
        self._guard = ApiAccessGuard(session)

    def get_completeness(self, api_id: int, revision_id: int) -> CompletenessView:
        entry: Optional[ApiCatalogEntry]
        if self._guard.sees_everything():
            reading = self._fetch_reading(revision_id)
            entry = self._soft_lookup_identity(api_id)
        else:
            # A leitura é pelo id da revisão: sem conferir a API antes, o
            # `--id` de uma API visível abriria a revisão de outra.
            entry = self._required_identity(api_id, revision_id)
            reading = self._fetch_reading(revision_id)
        revision_number = self._resolve_revision_number(entry, revision_id)
        return self._build_view(api_id, revision_id, revision_number, reading, entry)

    @staticmethod
    def _resolve_revision_number(
        entry: Optional[ApiCatalogEntry], revision_id: int
    ) -> Optional[int]:
        """REV # via mapa id→número do frame (dado ou nada; nunca o id disfarçado)."""
        if entry is None:
            return None
        for revision in entry.revisions:
            if revision.id == revision_id and revision.revisionNumber is not None:
                return int(revision.revisionNumber)
        return None

    def _fetch_reading(self, revision_id: int) -> CatalogRevisionCompleteness:
        try:
            return self.manager_api.get_revision_completeness(revision_id)
        except (ManagerApiTransportRejectedError, ManagerApiTransportUnavailableError) as exc:
            raise self._translate_failure(revision_id, exc) from exc

    @staticmethod
    def _translate_failure(
        revision_id: int,
        exc: ManagerApiTransportRejectedError | ManagerApiTransportUnavailableError,
    ) -> CompletenessError:
        """Classificação compartilhada; 404/403 mantêm a leitura de revisão inexistente."""
        kind = classify_manager_failure(exc)
        if kind is ManagerFailureKind.NOT_FOUND:
            return CompletenessNotFound(revision_id)
        if kind is ManagerFailureKind.FORBIDDEN:
            return CompletenessDenied(revision_id)
        if kind is ManagerFailureKind.UNAUTHORIZED:
            return CompletenessUnauthorized()
        return CompletenessPlatformError(manager_failure_message(kind))

    def _soft_lookup_identity(self, api_id: int) -> Optional[ApiCatalogEntry]:
        """Identidade da API para quem vê tudo; falha degrada para identidade cega."""
        try:
            return self.manager_api.list_api_detail(api_id)
        except Exception:
            return None

    def _required_identity(self, api_id: int, revision_id: int) -> ApiCatalogEntry:
        """Identidade da API para sessão de dev: existe, é visível e tem a revisão."""
        try:
            entry = self.manager_api.list_api_detail(api_id)
        except (ManagerApiTransportRejectedError, ManagerApiTransportUnavailableError) as exc:
            raise self._translate_lookup_failure(api_id, exc) from exc
        if entry is None or not self._guard.can_see(entry.visibility()):
            raise CompletenessApiNotFound(api_id)
        if not any(revision.id == revision_id for revision in entry.revisions):
            raise CompletenessNotFound(revision_id)
        return entry

    @staticmethod
    def _translate_lookup_failure(
        api_id: int,
        exc: ManagerApiTransportRejectedError | ManagerApiTransportUnavailableError,
    ) -> CompletenessError:
        """Classificação compartilhada; 404 do catálogo é API inexistente."""
        kind = classify_manager_failure(exc)
        if kind is ManagerFailureKind.NOT_FOUND:
            return CompletenessApiNotFound(api_id)
        if kind is ManagerFailureKind.UNAUTHORIZED:
            return CompletenessUnauthorized()
        return CompletenessPlatformError(manager_failure_message(kind))

    def _build_api_block(
        self, api_id: int, entry: Optional[ApiCatalogEntry]
    ) -> CompletenessApi:
        name = entry.name if entry else None
        version = entry.version if entry else None
        context: Optional[CompletenessContext] = None
        if entry is not None:
            context_type = str(entry.contextType.value) if entry.contextType else None
            if context_type or entry.contextGroupName or entry.owner:
                context = CompletenessContext(
                    type=context_type,
                    group_name=entry.contextGroupName,
                    owner=entry.owner,
                )
        return CompletenessApi(
            manager_id=api_id,
            name=name,
            version=version,
            context=context,
        )

    def _build_view(
        self,
        api_id: int,
        revision_id: int,
        revision_number: Optional[int],
        reading: CatalogRevisionCompleteness,
        entry: Optional[ApiCatalogEntry],
    ) -> CompletenessView:
        return CompletenessView(
            schema=SCHEMA_SEN_COMPLETENESS_V1,
            generated_at=_utc_now_iso(),
            api=self._build_api_block(api_id, entry),
            revision_id=revision_id,
            revision_number=revision_number,
            score=reading.score,
            gate_percent=GATE_PERCENT_V1,
            suggestions=[
                CompletenessSuggestion(index=position + 1, text=text)
                for position, text in enumerate(reading.suggestions)
            ],
        )
