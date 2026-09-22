from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class ApiCatalogPage:
    """Uma pagina do catalogo (api-finder) com o total do universo.

    `total` vem do header `count` — o server fala o tamanho do universo
    (sondas r5b: count=108 com _limit=10). Serve para rodapes e para
    offset-beyond-total sem guessing.
    """

    rows: list[Dict[str, Any]]
    total: int


class ManagerApiPort(ABC):
    @abstractmethod
    def get_apis(self) -> list[Dict[str, Any]]:
        """Contract to search all APIs (manager cru — fluxo legado/bare)."""
        pass

    @abstractmethod
    def list_catalog_apis(
        self,
        limit: int,
        order_by: str = "apiId",
        sort: str = "asc",
    ) -> ApiCatalogPage:
        """Fonte da LISTAGEM de `sen list api` — catalogo api-finder.

        GET /api-finder/api/v3/apis com onlyMyContextApi=false (visibilidade
        eh calculada pelo CLIENTE sobre contextType/contextGroupName).
        Medido em sondas (r5c, 21/09/2026): o servidor NAO caminha com
        skip/offset/page (inertes) — o `_limit` apenas TRUNCA a janela iniciada
        na posicao 0 da ordenacao; offset profundo eh client-side (service
        pede `_limit = offset + limit` e faz o slice). Row shape:
        {apiId, apiName, description, version, creationDate, updateDate,
        basePath, owner, contextType, contextGroupName, contextUserLogins,
        apiLifeCycle, lastRevision(NUMERO), plans[], ...}.
        """
        pass

    @abstractmethod
    def get_api_by_id(self, api_id: int) -> Dict[str, Any]:
        """Contract to search data from the API by ID (manager)"""
        pass

    @abstractmethod
    def list_api_detail(self, api_id: int) -> Optional[Dict[str, Any]]:
        """Search API detail from the CATALOG (api-finder, customSearch=(apiId:{id}))."""
        pass

    @abstractmethod
    def get_revisions_basic(self) -> list[Dict[str, Any]]:
        """Contract to fetch the basic revisions catalog (one call for all APIs).

        Each row carries {id, api {id, revisionNumber, ...}, workflowId, workflowStageId}.
        The API revisions list for the drill-down is DERIVED HERE by filtering
        api.id — there is no server-side listing (probes 21/09: GET /apis/{id}/revisions
        returns only the LAST revision detail; global /revisions 500s).
        """
        pass

    @abstractmethod
    def get_revision_completeness(self, revision_id: int) -> Dict[str, Any]:
        """Contract to fetch completeness of one revision.

        Backend delegates to Adaptive Governance (maturity-reports) and MAY
        refuse (422 wrapping 403, probes 21/09) — consumers MUST degrade
        gracefully ('-' column) when the map comes empty/unavailable.
        """
        pass

    @abstractmethod
    def get_workflow_stages(self, workflow_id: int) -> list[Dict[str, Any]]:
        """Contract to fetch the stages catalog of one workflow.

        GET /api-governance/api/v3/workflows/{id}/stages (DIFFERENT base path
        from the manager calls) — consumed via a per-execution cache (one call
        per distinct workflow, never per row). Each row:
        {workflowStageId, workflowStageName, position, deployableEnvironments, ...}.
        """
        pass

    @abstractmethod
    def publish_api_changes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Contract to publish new API revisions"""
        pass

    def get_custom_interceptor_by_id(
        self, custom_interceptor_id: int
    ) -> Dict[str, str] | None:
        """Get the content of a custom interceptor"""
        pass
