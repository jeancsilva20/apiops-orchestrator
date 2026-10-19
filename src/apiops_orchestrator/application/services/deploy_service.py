"""Use-case do `sen deploy` — coloca no ar a revisão do ambiente.

    E0  configuração      modo pipeline · revisão ≠ 1 · ambiente       sem rede
    E1  manifesto         spec.id, version, basePath                   sem rede
    E2  GET /apis/{id}    identidade · revisão · ambiente ligado · estado anterior
    E3  governança        ambiente permitido · completeness · atributos
    E4  POST /deployments ESCRITA
    E5  GET /apis/{id}    conferência
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from apiops_orchestrator.application.exceptions.deploy_exceptions import (
    NENHUM_DEPLOY,
    DeployError,
    DeployFalhouError,
    DeployGovernanceBlockedError,
)
from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    INTERNAL_ERROR_MESSAGE,
)
from apiops_orchestrator.application.exceptions.validate_exceptions import (
    IdentidadeDivergenteError,
)
from apiops_orchestrator.application.services.governance_precheck_service import (
    GovernancePrecheckService,
)
from apiops_orchestrator.application.services.manager_failure_translator import (
    classify_manager_failure,
    manager_failure_message,
)
from apiops_orchestrator.application.services.repo_importer_service import (
    RepoCanonicalReader,
)
from apiops_orchestrator.application.services.revision_writer import RevisionWriter
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.deploy_model import (
    SCHEMA_SEN_DEPLOY_V1,
    STATUS_FAILED,
    STATUS_SUCCESS,
    DeployEnvironment,
    DeployGovernance,
    DeploymentResultado,
    DeployState,
    DeployView,
)
from apiops_orchestrator.domain.models.validate_view import (
    AtributoExigido,
    ValidateApi,
    ValidateRevision,
)
from apiops_orchestrator.domain.ports.local_file_importer_port import (
    LocalFileImporterPort,
)
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiError,
    ManagerApiGovernanceBlockedError,
    ManagerApiPort,
    ManagerApiTransportRejectedError,
)

logger = logging.getLogger(__name__)

REVISAO_DRAFT = 1
DEPLOYED = "DEPLOYED"

# Recusas em que o motivo da plataforma diz o que corrigir.
_STATUS_COM_MOTIVO = frozenset({400, 404, 409, 412, 422})


def _agora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _instante(epoch_ms: Any) -> Optional[str]:
    """Epoch em milissegundos → ISO-8601 UTC."""
    try:
        return datetime.fromtimestamp(int(epoch_ms) / 1000, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _numero(valor: Any) -> Optional[float]:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _deploys(api: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Registros de deploy de todas as revisões da API."""
    return [
        d
        for revisao in api.get("revisions") or []
        for d in revisao.get("deployments") or []
        if isinstance(d, dict)
    ]


def _estado(registro: Optional[Dict[str, Any]]) -> Optional[DeployState]:
    if not registro:
        return None
    return DeployState(
        deployment_id=registro.get("id"),
        revision_id=registro.get("revisionId"),
        revision_number=registro.get("revisionNumber"),
        deployed_at=_instante(registro.get("deployDate")),
    )


def _ativo_no_ambiente(api: Dict[str, Any], ambiente_id: int) -> Optional[Dict[str, Any]]:
    """Deploy `DEPLOYED` mais recente da API no ambiente."""
    ativos = [
        d
        for d in _deploys(api)
        if d.get("status") == DEPLOYED and d.get("environmentId") == ambiente_id
    ]
    if not ativos:
        return None
    return max(ativos, key=lambda d: d.get("deployDate") or 0)


class DeployService:
    def __init__(
        self,
        manager_api: ManagerApiPort,
        importer: LocalFileImporterPort,
        settings: Settings,
    ):
        self._manager_api = manager_api
        self._importer = importer
        self._settings = settings
        self._governanca = GovernancePrecheckService(manager_api)

    def deploy(
        self,
        repo_path: Path,
        *,
        progresso: Optional[Callable[[str], None]] = None,
    ) -> DeployView:
        """Coloca a revisão alvo no ar no ambiente alvo e confere o resultado."""
        etapa = progresso or (lambda _: None)

        numero, ambiente_id = self._alvo()

        etapa("Lendo o manifesto")
        spec = self._manifesto(repo_path)

        etapa("Consultando a API no Manager")
        api = self._manager_api.get_api_by_id(spec["id"]) or {}
        self._identidade(spec, api)
        revisao = self._revisao(api, numero)
        ambiente = self._ambiente(api, ambiente_id)
        anterior = _estado(_ativo_no_ambiente(api, ambiente_id))

        etapa("Verificando a governança")
        governanca, avisos = self._avaliar_governanca(api, revisao, ambiente_id)
        if governanca.blocked:
            raise DeployGovernanceBlockedError(
                governanca.workflow_id, governanca.stage_id, governanca.violations
            )

        base = dict(
            schema=SCHEMA_SEN_DEPLOY_V1,
            generated_at=_agora(),
            execution_mode=self._settings.EXECUTION_MODE,
            api=ValidateApi(
                manager_id=spec["id"],
                name=api.get("name"),
                version=api.get("version"),
                base_path=api.get("basePath"),
            ),
            revision=ValidateRevision(
                manager_id=revisao["id"], revision_number=revisao.get("revisionNumber")
            ),
            environment=ambiente,
            governanca=governanca,
            previous_state=anterior,
            avisos=avisos,
        )

        deployment_id = self._escrever(revisao, ambiente, base, etapa)
        novo = self._conferir(spec["id"], deployment_id, revisao, ambiente, base, etapa)

        return DeployView(
            **base,
            new_state=novo,
            deployment=DeploymentResultado(
                attempted=True,
                accepted=True,
                deployment_id=deployment_id,
                verified=True,
                status=STATUS_SUCCESS,
            ),
        )

    # --- E0 / E1 -------------------------------------------------------------

    def _alvo(self) -> Tuple[int, int]:
        """Modo, número da revisão e id do ambiente alvo, lidos da configuração."""
        if not self._settings.modo_pipeline:
            raise DeployError(
                "O deploy é feito só pela esteira: o comando não roda na máquina "
                "local (EXECUTION_MODE=local). A promoção para DEV, HML e PRD "
                f"acontece no merge da branch correspondente.\n\n{NENHUM_DEPLOY}"
            )
        numero = self._settings.TARGET_REVISION_NUMBER
        if numero is None:
            raise DeployError(
                "TARGET_REVISION_NUMBER não está definida. Ela diz qual revisão vai "
                "para o ar (2 = DEV, 3 = HML, 4 = PRD).\n\n"
                f"Defina a variável na configuração da esteira.\n\n{NENHUM_DEPLOY}"
            )
        if numero == REVISAO_DRAFT:
            raise DeployError(
                "TARGET_REVISION_NUMBER está em 1, a revisão Draft. A Draft é "
                "contexto de diagnóstico e não tem deploy: use o número da revisão "
                f"do ambiente (2 = DEV, 3 = HML, 4 = PRD).\n\n{NENHUM_DEPLOY}"
            )
        if numero < REVISAO_DRAFT:
            raise DeployError(
                f"TARGET_REVISION_NUMBER está em {numero}, que não é número de "
                f"revisão.\n\n{NENHUM_DEPLOY}"
            )
        ambiente = self._settings.TARGET_ENVIRONMENT_ID
        if ambiente is None:
            raise DeployError(
                "TARGET_ENVIRONMENT_ID não está definida. Ela é o id, no Manager, do "
                "ambiente que recebe o deploy.\n\n"
                f"Defina a variável na configuração da esteira.\n\n{NENHUM_DEPLOY}"
            )
        return numero, ambiente

    def _manifesto(self, repo_path: Path) -> Dict[str, Any]:
        """`spec` do `api-basic-info.yaml`."""
        lido = RepoCanonicalReader(self._importer).carregar(str(repo_path))
        if not lido.basic_info:
            ilegivel = next(
                (i for i in lido.ilegiveis if "api-basic-info" in i.partition(": ")[0]),
                None,
            )
            if ilegivel:
                caminho, _, motivo = ilegivel.partition(": ")
                raise DeployError(
                    f"O arquivo `{caminho}` não pôde ser lido: {motivo}.\n\n"
                    f"{NENHUM_DEPLOY}"
                )
            raise DeployError(
                "Não encontrei o `api-basic-info.yaml` no repositório. É dele que "
                f"vem o id da API.\n\n{NENHUM_DEPLOY}"
            )
        spec = lido.basic_info.get("spec") or {}
        if spec.get("id") is None:
            raise DeployError(
                "O `api-basic-info.yaml` não declara `spec.id`, o id da API no "
                f"Manager.\n\n{NENHUM_DEPLOY}"
            )
        return spec

    # --- E2 ------------------------------------------------------------------

    @staticmethod
    def _identidade(spec: Dict[str, Any], api: Dict[str, Any]) -> None:
        """Confere `version` e `basePath` do manifesto contra o Manager."""
        try:
            RevisionWriter.guarda_identidade(spec, api)
        except IdentidadeDivergenteError as exc:
            raise DeployError(
                "Este repositório parece apontar para outra API. O "
                f"`{exc.campo}` declarado aqui é {exc.no_repo!r}, mas a API "
                f"{exc.api_id} no Manager tem {exc.no_manager!r}.\n\n"
                f"Confira o `id` em `api-basic-info.yaml`.\n\n{NENHUM_DEPLOY}"
            ) from exc

    @staticmethod
    def _revisao(api: Dict[str, Any], numero: int) -> Dict[str, Any]:
        """Revisão da API com o número informado."""
        revisoes = api.get("revisions") or []
        for revisao in revisoes:
            if revisao.get("revisionNumber") == numero and revisao.get("id") is not None:
                return revisao
        if not revisoes:
            disponiveis = "a API não tem nenhuma revisão"
        else:
            disponiveis = "Disponíveis: " + ", ".join(
                f"{r.get('revisionNumber')} (id {r.get('id')})" for r in revisoes
            )
        raise DeployError(
            f"A API {api.get('id')} não tem revisão de número {numero}. "
            f"{disponiveis}.\n\nCriar revisão é ato humano, pela interface do "
            f"Manager.\n\n{NENHUM_DEPLOY}"
        )

    @staticmethod
    def _ambiente(api: Dict[str, Any], ambiente_id: int) -> DeployEnvironment:
        """Ambiente alvo, entre os ligados à API."""
        ligados = [e for e in api.get("environments") or [] if isinstance(e, dict)]
        for ambiente in ligados:
            if ambiente.get("id") == ambiente_id:
                return DeployEnvironment(manager_id=ambiente_id, name=ambiente.get("name"))
        if ligados:
            lista = "Ambientes ligados: " + ", ".join(
                f"{e.get('id')} ({e.get('name')})" for e in ligados
            )
        else:
            lista = "A API não está ligada a nenhum ambiente"
        raise DeployError(
            f"A API {api.get('id')} não está ligada ao ambiente {ambiente_id}. "
            f"{lista}.\n\nConfira TARGET_ENVIRONMENT_ID ou ligue a API ao ambiente "
            f"no Manager.\n\n{NENHUM_DEPLOY}"
        )

    # --- E3 ------------------------------------------------------------------

    def _avaliar_governanca(
        self, api: Dict[str, Any], revisao: Dict[str, Any], ambiente_id: int
    ) -> Tuple[DeployGovernance, List[str]]:
        """Avalia os critérios do stage da revisão; devolve o resultado e os avisos."""
        precheck = self._governanca.avaliar(revisao, api.get("apiTags"))
        stage = precheck.stage or {}
        violacoes: List[str] = []

        permitidos = [
            int(e) for e in stage.get("deployableEnvironments") or [] if _numero(e) is not None
        ]
        if permitidos and ambiente_id not in permitidos:
            violacoes.append(
                f"O ambiente {ambiente_id} não está entre os que o stage "
                f"{precheck.stage_id} permite: "
                + ", ".join(str(p) for p in permitidos)
                + "."
            )

        exigida = _numero(stage.get("completenessRequisite")) if stage else None
        atual: Optional[float] = None
        if exigida:
            atual = self._manager_api.get_revision_completeness(revisao["id"]).score
            if atual < exigida:
                violacoes.append(
                    f"A completeness da revisão é {atual:.1f}, e o stage exige "
                    f"{exigida:.1f}."
                )

        if precheck.faltantes:
            violacoes.append(
                "Faltam atributos exigidos pelo stage: "
                + ", ".join(str(f.name or f.attribute_id) for f in precheck.faltantes)
                + "."
            )

        logger.info(
            "deploy.governanca workflow=%s stage=%s ambiente=%s violacoes=%d",
            precheck.workflow_id,
            precheck.stage_id,
            ambiente_id,
            len(violacoes),
        )
        governanca = DeployGovernance(
            workflow_id=precheck.workflow_id,
            stage_id=precheck.stage_id,
            deployable_environments=permitidos,
            completeness_required=exigida,
            completeness_actual=atual,
            required=[
                AtributoExigido(e.attribute_id, e.name, e.tag_id) for e in precheck.exigidos
            ],
            missing=[
                AtributoExigido(f.attribute_id, f.name, f.tag_id) for f in precheck.faltantes
            ],
            violations=violacoes,
        )
        return governanca, [f"Governança: {a}" for a in precheck.avisos]

    # --- E4 / E5 -------------------------------------------------------------

    def _escrever(
        self,
        revisao: Dict[str, Any],
        ambiente: DeployEnvironment,
        base: Dict[str, Any],
        etapa: Callable[[str], None],
    ) -> Optional[int]:
        """Faz o deploy e devolve o id do registro criado."""
        etapa(f"Fazendo o deploy no ambiente {ambiente.name or ambiente.manager_id}")
        try:
            return self._manager_api.deploy_revision(ambiente.manager_id, revisao["id"])
        except ManagerApiGovernanceBlockedError as exc:
            raise DeployGovernanceBlockedError(
                exc.workflow_id, base["governanca"].stage_id, exc.messages
            ) from exc
        except ManagerApiTransportRejectedError as exc:
            motivos = exc.messages if exc.status_code in _STATUS_COM_MOTIVO else []
            logger.info(
                "deploy.recusado status_code=%s motivos=%d", exc.status_code, len(motivos)
            )
            if motivos:
                corpo = "O Manager recusou o deploy:\n\n" + "\n".join(
                    f"  - {m}" for m in motivos
                )
            else:
                corpo = manager_failure_message(classify_manager_failure(exc)) or (
                    INTERNAL_ERROR_MESSAGE
                )
            raise self._falha(base, corpo, attempted=True) from exc
        except ManagerApiError as exc:
            logger.info("deploy.falha_transporte type=%s", type(exc).__name__)
            corpo = manager_failure_message(classify_manager_failure(exc)) or (
                INTERNAL_ERROR_MESSAGE
            )
            raise self._falha(
                base,
                f"{corpo}\n\nNão foi possível confirmar se o deploy aconteceu. "
                "Confira o ambiente no Manager antes de rodar de novo.",
                attempted=True,
            ) from exc

    def _conferir(
        self,
        api_id: int,
        deployment_id: Optional[int],
        revisao: Dict[str, Any],
        ambiente: DeployEnvironment,
        base: Dict[str, Any],
        etapa: Callable[[str], None],
    ) -> Optional[DeployState]:
        """Relê a API e confirma o deploy criado; devolve o novo estado do ambiente."""
        etapa("Conferindo o deploy")
        try:
            depois = self._manager_api.get_api_by_id(api_id) or {}
        except ManagerApiError as exc:
            raise self._falha(
                base,
                f"O Manager aceitou o deploy (id {deployment_id}), mas não consegui "
                "reler a API para conferir. Confira o ambiente no Manager.",
                attempted=True,
                accepted=True,
                deployment_id=deployment_id,
            ) from exc

        registro = next(
            (d for d in _deploys(depois) if d.get("id") == deployment_id), None
        )
        conferido = (
            registro is not None
            and registro.get("status") == DEPLOYED
            and registro.get("environmentId") == ambiente.manager_id
            and registro.get("revisionId") == revisao["id"]
        )
        if not conferido:
            logger.info(
                "deploy.divergente deployment_id=%s encontrado=%s",
                deployment_id,
                registro is not None,
            )
            raise self._falha(
                base,
                f"O Manager aceitou o deploy (id {deployment_id}), mas a releitura "
                f"não mostra a revisão {revisao.get('revisionNumber')} no ar no "
                f"ambiente {ambiente.manager_id}. Confira o ambiente no Manager.",
                attempted=True,
                accepted=True,
                deployment_id=deployment_id,
                novo=_estado(_ativo_no_ambiente(depois, ambiente.manager_id)),
            )
        return _estado(registro)

    @staticmethod
    def _falha(
        base: Dict[str, Any],
        mensagem: str,
        *,
        attempted: bool,
        accepted: bool = False,
        deployment_id: Optional[int] = None,
        novo: Optional[DeployState] = None,
    ) -> DeployFalhouError:
        """Erro de deploy com o resultado `FAILED`."""
        view = DeployView(
            **base,
            new_state=novo,
            deployment=DeploymentResultado(
                attempted=attempted,
                accepted=accepted,
                deployment_id=deployment_id,
                verified=False,
                status=STATUS_FAILED,
                reason=mensagem,
            ),
        )
        return DeployFalhouError(mensagem, view)
