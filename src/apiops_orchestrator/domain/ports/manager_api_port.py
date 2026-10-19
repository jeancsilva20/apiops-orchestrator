from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from apiops_orchestrator.domain.models.catalog_revision_model import (
    CatalogRevisionCompleteness,
)
from apiops_orchestrator.domain.models.workflow_stage_model import WorkflowStage


class ManagerApiError(Exception):
    """Base dos sinais de contrato do port do API Manager/Finder."""


class ManagerApiTransportRejectedError(ManagerApiError):
    """A plataforma Manager/Finder recusou o pedido (HTTP 4xx).

    Carrega `status_code` para diagnóstico; mensagem é neutra de tecnologia.
    `code` (código de erro do corpo) e `request_id` (id da requisição no
    gateway) servem só ao log — nunca à saída do usuário. `messages` são os
    motivos em texto humano que a plataforma devolveu, já desembrulhados do
    envelope; quem decide exibi-los é o caso de uso (ex.: recusa de escrita).
    """

    def __init__(
        self,
        status_code: int,
        title: str,
        code: Optional[str] = None,
        request_id: Optional[str] = None,
        messages: Optional[List[str]] = None,
    ) -> None:
        self.status_code = status_code
        self.title = title
        self.code = code
        self.request_id = request_id
        self.messages = list(messages or [])
        super().__init__(f"Manager API rejected the request (HTTP {status_code}: {title})")


class ManagerApiResponseTooLargeError(ManagerApiTransportRejectedError):
    """A plataforma recusou entregar a resposta por tamanho (HTTP 413).

    Subclasse de propósito: quem pagina captura só este sinal para pedir menos
    registros; quem já trata `ManagerApiTransportRejectedError` segue igual.
    """


class ManagerApiGovernanceBlockedError(ManagerApiTransportRejectedError):
    """O Adaptive Governance recusou a escrita (HTTP 412 de `/api-governance/.../validate`).

    Bloqueio de governança não é falha de transporte (V-23 §4): o sinal carrega
    o `workflow_id` lido do `path` do erro — que pode diferir do gravado na
    revisão (V-23 §3) — e o envelope original em `raw`, intacto. `messages`
    é evidência em texto livre: nunca fonte do atributo faltante.
    """

    def __init__(
        self,
        status_code: int,
        title: str,
        workflow_id: Optional[int] = None,
        raw: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(status_code, title, **kwargs)
        self.workflow_id = workflow_id
        self.raw = raw or {}


class ManagerApiTransportUnavailableError(ManagerApiError):
    """Manager/Finder inalcançável ou 5xx persistente após esgotar retries."""


@dataclass(frozen=True)
class ApiCatalogPage:
    """Uma pagina do catalogo (api-finder) com o total de registros."""

    rows: List[ApiCatalogEntry]
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
        offset: int = 0,
        query: Optional[str] = None,
    ) -> ApiCatalogPage:
        """Contract to read one page of the APIs catalog, with optional query filter.

        Raises `ManagerApiResponseTooLargeError` when the platform refuses the
        page size; the caller decides whether to retry with a smaller page.
        """
        pass

    @abstractmethod
    def get_api_by_id(self, api_id: Optional[int] = None) -> Dict[str, Any]:
        """Contract to search data from the API by ID (manager)"""
        pass

    @abstractmethod
    def list_api_detail(self, api_id: int) -> Optional[ApiCatalogEntry]:
        """Search API detail from the CATALOG."""
        pass

    @abstractmethod
    def get_revision_completeness(self, revision_id: int) -> CatalogRevisionCompleteness:
        """Contract to fetch the completeness report of one revision."""
        pass

    @abstractmethod
    def get_workflow_stages(self, workflow_id: int) -> List[WorkflowStage]:
        """Contract to fetch the stages catalog of one workflow."""
        pass

    @abstractmethod
    def publish_api_changes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Contract to publish new API revisions"""
        pass

    @abstractmethod
    def get_revision(self, revision_id: int) -> Dict[str, Any]:
        """Estado completo de uma revisão: interceptors, resources e o `api` aninhado.

        É daqui que saem `workflowId` e `workflowStageId`, que o publish reenvia
        intactos (D-020), e o fluxo **resolvido** de cada escopo (W-4).
        """

    @abstractmethod
    def update_revision(self, revision_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """`PUT` denso na revisão. **Atualiza**, não cria.

        Criar revisão é ato humano (D-005 §9): o orquestrador nunca usa `POST`.
        É neste `PUT` que o Adaptive Governance atua (W-7) — escrever também em
        `PUT /apis/{id}` furaria o gate e deixaria estado meio-aplicado.
        """

    @abstractmethod
    def deploy_revision(self, environment_id: int, revision_id: int) -> Optional[int]:
        """Coloca a revisão no ar no ambiente e devolve o id do deploy."""

    @abstractmethod
    def get_workflow(self, workflow_id: int) -> Dict[str, Any]:
        """Workflow do Adaptive Governance, com `stages[].attributesRequisites`."""

    @abstractmethod
    def list_attributes(self) -> List[Dict[str, Any]]:
        """Catálogo `id ↔ name` dos atributos do AG.

        Lido a cada execução: os requisitos são configuração mutável do tenant —
        entre 2026-10-14 e 2026-10-15 o stage 1402 trocou um dos atributos que
        exige (D-020 §3.4).
        """

    def get_custom_interceptor_by_id(
        self, custom_interceptor_id: int
    ) -> Dict[str, str] | None:
        """Get the content of a custom interceptor"""
        pass
