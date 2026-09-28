from datetime import datetime, timezone
from typing import Optional

from apiops_orchestrator.application.exceptions.completeness_exceptions import (
    CompletenessDenied,
    CompletenessError,
    CompletenessNotFound,
    CompletenessPlatformError,
    CompletenessUnauthorized,
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
from apiops_orchestrator.domain.services.catalog_visibility import finder_row_visible_to
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

    def get_completeness(self, api_id: int, revision_id: int) -> CompletenessView:
        reading = self._fetch_reading(revision_id)
        entry = self._soft_lookup_identity(api_id)
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
        except ManagerApiTransportRejectedError as exc:
            raise self._translate_rejection(revision_id, exc) from exc
        except ManagerApiTransportUnavailableError as exc:
            raise CompletenessPlatformError(
                "Manager indisponível ou falha de conexão"
            ) from exc

    @staticmethod
    def _translate_rejection(
        revision_id: int, exc: ManagerApiTransportRejectedError
    ) -> CompletenessError:
        if exc.status_code == 404:
            return CompletenessNotFound(revision_id)
        if exc.status_code == 401:
            return CompletenessUnauthorized()
        if exc.status_code == 403:
            return CompletenessDenied(revision_id)
        return CompletenessPlatformError(f"HTTP {exc.status_code}: {exc.title}")

    def _soft_lookup_identity(self, api_id: int) -> Optional[ApiCatalogEntry]:
        try:
            entry = self.manager_api.list_api_detail(api_id)
        except Exception:
            # Satélite de identidade é degradável: falha nunca derruba o comando.
            return None
        return self._visible(entry)

    def _visible(self, entry: Optional[ApiCatalogEntry]) -> Optional[ApiCatalogEntry]:
        """Matriz de visibilidade r5 (regra do domínio, idêntica à `sen list`).

        Entry invisível degrada igual lookup falho (identidade cega) — nunca
        erro sintético: a autorização de fato da consulta é do servidor (403).
        """
        if entry is None or self.session is None:
            return entry
        visible = finder_row_visible_to(
            entry,
            self.session.userName,
            list(self.session.userGroups or []),
            self.session.is_super_admin,
        )
        return entry if visible else None

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
