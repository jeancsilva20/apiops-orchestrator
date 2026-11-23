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


class ManagerApiUnexpectedResponseError(ManagerApiError):
    """The platform answered in a format the port does not recognize."""


@dataclass(frozen=True)
class ApiCatalogPage:
    """Uma pagina do catalogo (api-finder) com o total de registros."""

    rows: List[ApiCatalogEntry]
    total: int


@dataclass(frozen=True)
class CallsPage:
    """Uma página do trace de chamadas (`/calls`) e o total da janela (`callsSize`)."""

    rows: List[Dict[str, Any]]
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
        """LEGADO: cria revisão (`POST /revisions`). Nenhum comando usa; mantido para o versionamento futuro."""
        pass

    @abstractmethod
    def get_revision(self, revision_id: int) -> Dict[str, Any]:
        """Estado completo de uma revisão: interceptors, resources e o `api` aninhado.

        É daqui que saem `workflowId` e `workflowStageId`, que o publish reenvia
        intactos (D-020), e os itens próprios e as marcações de cada escopo (V-28).
        """

    @abstractmethod
    def update_revision(self, revision_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """`PUT` denso na revisão. **Atualiza**, não cria.

        Criar revisão é ato humano (D-005 §9): o orquestrador nunca usa `POST`.
        É neste `PUT` que o Adaptive Governance atua (W-7) — escrever também em
        `PUT /apis/{id}` furaria o gate e deixaria estado meio-aplicado.
        """

    @abstractmethod
    def get_revision_swagger(self, revision_id: int) -> Dict[str, Any]:
        """Swagger of the revision, with the `x-*` extensions."""

    @abstractmethod
    def update_revision_swagger(
        self, revision_id: int, document: Dict[str, Any]
    ) -> Dict[str, Any]:
        """`PUT` of the whole revision swagger."""

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

    # --- catálogos do tenant (leitura; mapeamento APIM/AG) -----------------

    @abstractmethod
    def list_environments(self) -> List[Dict[str, Any]]:
        """`GET /environments?simple=true`: id, name, inboundUrl, isDeployable."""

    @abstractmethod
    def list_workflows(self) -> List[Dict[str, Any]]:
        """`GET /api-governance/.../workflows`: workflows com os stages e requisitos inline."""

    @abstractmethod
    def list_interceptor_catalog(self) -> List[Dict[str, Any]]:
        """`GET /interceptors`: tipos nativos (`DEFAULT`) e customs (`JAVASCRIPT`/`JAVA`).

        O `name` de cada item é o `type` que os interceptors das revisões carregam.
        """

    @abstractmethod
    def get_impact_tree(self, api_id: int, environment_id: int) -> Dict[str, Any]:
        """`GET /api-governance/.../apis/{id}/tree-analysis/{env}`: API → rotas → planos → apps."""

    # --- consumo e infraestrutura (leitura; mapeamento APIM 07/08/14) -------

    @abstractmethod
    def get_environment(self, environment_id: int) -> Dict[str, Any]:
        """`GET /environments/{id}`: inbound, `mapVars` (variáveis) e `revisionsDeployed`."""

    @abstractmethod
    def list_apps(self) -> List[Dict[str, Any]]:
        """`GET /apps`: apps com `apis[].plans[]` (assinaturas) e `accessTokens`."""

    @abstractmethod
    def get_app(self, app_id: int) -> Optional[Dict[str, Any]]:
        """`GET /apps/{id}`; `None` quando não existe."""

    @abstractmethod
    def list_plans(self) -> List[Dict[str, Any]]:
        """`GET /plans?filter=BASIC` paginado até o fim."""

    @abstractmethod
    def get_plan(self, plan_id: int) -> Optional[Dict[str, Any]]:
        """`GET /plans/{id}` com os interceptors do plano; `None` quando não existe."""

    @abstractmethod
    def list_access_tokens(self) -> List[Dict[str, Any]]:
        """`GET /access-tokens`: tokens com app, owner, status e APIs."""

    @abstractmethod
    def list_users(self, keyword: Optional[str] = None) -> List[Dict[str, Any]]:
        """`GET /user-management/v1/users` (username, status, e-mail)."""

    @abstractmethod
    def list_groups(self, keyword: Optional[str] = None) -> List[Dict[str, Any]]:
        """`GET /user-management/v1/groups`: os *Teams* da UI (name, description)."""

    # --- access control (leitura; mapeamento APIM 14: Team = groups, Role = policies)

    @abstractmethod
    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """`GET /user-management/v1/users/{username}`; `None` quando não existe."""

    @abstractmethod
    def get_user_groups(self, username: str) -> List[Dict[str, Any]]:
        """`GET /user-management/v1/users/{username}/groups`: os times do usuário."""

    @abstractmethod
    def get_user_policies(self, username: str) -> List[Dict[str, Any]]:
        """`GET /user-management/v1/users/{username}/policies`: as roles do usuário."""

    @abstractmethod
    def get_group(self, name: str) -> Optional[Dict[str, Any]]:
        """`GET /user-management/v1/groups/{name}`; `None` quando não existe."""

    @abstractmethod
    def get_group_users(self, name: str) -> List[Dict[str, Any]]:
        """`GET /user-management/v1/groups/{name}/users`: membros (`pageContent`)."""

    @abstractmethod
    def list_policies(self, keyword: Optional[str] = None) -> List[Dict[str, Any]]:
        """`GET /user-management/v1/policies`: as *Roles* da UI, com os produtos."""

    @abstractmethod
    def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """`GET /user-management/v1/policies/{id}`; `None` quando não existe."""

    @abstractmethod
    def get_policy_permissions(self, policy_id: str) -> List[Dict[str, Any]]:
        """`GET /user-management/v1/policies/{id}/permissions`: por produto, as permissões."""

    @abstractmethod
    def get_policy_users(self, policy_id: str) -> List[Dict[str, Any]]:
        """`GET /user-management/v1/policies/{id}/users`: quem tem a role."""

    @abstractmethod
    def list_permissions(self, product_name: str) -> List[str]:
        """`GET /user-management/v1/account-settings/permissions?productName=…`: catálogo de códigos."""

    # --- trace de chamadas (leitura; mapeamento APIM 10) ---------------------

    @abstractmethod
    def list_calls(
        self,
        begin: str,
        end: str,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, str]] = None,
    ) -> "CallsPage":
        """`GET /calls`: janela de no máximo 7 dias, datas `yyyy-MM-dd'T'HH:mm:ss` (UTC).

        `filters` são os parâmetros da rota (`apiId`, `environmentId`, `httpStatusFrom`,
        `httpStatusTo`, `uri`, `regex`, `operationId`, `resourceId`, `revisionId`).
        """

    @abstractmethod
    def get_call(self, call_id: str) -> Optional[Dict[str, Any]]:
        """`GET /calls/{id}`: a chamada com headers e o `trace` do pipeline; `None` se não existe."""

    @abstractmethod
    def list_inbounds(self) -> List[Dict[str, Any]]:
        """`GET /inbounds`: endereços de entrada (host, TLS, data plane)."""

    @abstractmethod
    def list_gateway_pools(self) -> List[Dict[str, Any]]:
        """`GET /gateway-pools`: pools de gateway e rotas em uso."""
