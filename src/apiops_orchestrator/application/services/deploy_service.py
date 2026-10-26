"""Use-case do `sen deploy` — coloca no ar a revisão do ambiente.

    E0  configuração      só na esteira · revisão ≠ 1 · ambiente       sem rede, antes de autenticar
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
    NO_DEPLOYMENT,
    DeployError,
    DeployFailedError,
    DeployGovernanceBlockedError,
)
from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    INTERNAL_ERROR_MESSAGE,
)
from apiops_orchestrator.application.exceptions.validate_exceptions import (
    IdentityMismatchError,
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
    DeploymentResult,
    DeployState,
    DeployView,
)
from apiops_orchestrator.domain.models.validate_view import (
    RequiredAttribute,
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
from apiops_orchestrator.domain.services import deployments

logger = logging.getLogger(__name__)

DRAFT_REVISION = 1

# Recusas em que o motivo da plataforma diz o que corrigir.
_STATUS_WITH_REASON = frozenset({400, 404, 409, 412, 422})


def require_pipeline(settings: Settings) -> None:
    """Recusa o deploy fora da esteira."""
    if not settings.pipeline_mode:
        raise DeployError(
            "O deploy é feito só pela esteira: o comando não roda na sua máquina. "
            "A promoção para DEV, HML e PRD acontece no merge da branch "
            f"correspondente.\n\n{NO_DEPLOYMENT}"
        )


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _state(record: Optional[Dict[str, Any]]) -> Optional[DeployState]:
    if not record:
        return None
    return DeployState(
        deployment_id=record.get("id"),
        revision_id=record.get("revisionId"),
        revision_number=record.get("revisionNumber"),
        deployed_at=deployments.instant(record.get("deployDate")),
    )


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
        self._governance = GovernancePrecheckService(manager_api)

    def deploy(
        self,
        repo_path: Path,
        *,
        progress: Optional[Callable[[str], None]] = None,
    ) -> DeployView:
        """Coloca a revisão alvo no ar no ambiente alvo e confere o resultado."""
        step = progress or (lambda _: None)

        number, environment_id = self._target()

        step("Lendo o manifesto")
        spec = self._manifest(repo_path)

        step("Consultando a API no Manager")
        api = self._manager_api.get_api_by_id(spec["id"]) or {}
        self._identity(spec, api)
        revision = self._revision(api, number)
        environment = self._environment(api, environment_id)
        previous = _state(deployments.active_in_environment(api, environment_id))

        step("Verificando a governança")
        governance, warnings = self._evaluate_governance(api, revision, environment_id)
        if governance.blocked:
            raise DeployGovernanceBlockedError(
                governance.workflow_id, governance.stage_id, governance.violations
            )

        base = dict(
            schema=SCHEMA_SEN_DEPLOY_V1,
            generated_at=_now(),
            execution_mode=self._settings.EXECUTION_MODE,
            api=ValidateApi(
                manager_id=spec["id"],
                name=api.get("name"),
                version=api.get("version"),
                base_path=api.get("basePath"),
            ),
            revision=ValidateRevision(
                manager_id=revision["id"], revision_number=revision.get("revisionNumber")
            ),
            environment=environment,
            governance=governance,
            previous_state=previous,
            warnings=warnings,
        )

        deployment_id = self._write(revision, environment, base, step)
        new = self._verify(spec["id"], deployment_id, revision, environment, base, step)

        return DeployView(
            **base,
            new_state=new,
            deployment=DeploymentResult(
                attempted=True,
                accepted=True,
                deployment_id=deployment_id,
                verified=True,
                status=STATUS_SUCCESS,
            ),
        )

    # --- E0 / E1 -------------------------------------------------------------

    def _target(self) -> Tuple[int, int]:
        """Modo, número da revisão e id do ambiente alvo, lidos da configuração."""
        require_pipeline(self._settings)
        number = self._settings.TARGET_REVISION_NUMBER
        if number is None:
            raise DeployError(
                "TARGET_REVISION_NUMBER não está definida. Ela diz qual revisão vai "
                "para o ar (2 = DEV, 3 = HML, 4 = PRD).\n\n"
                f"Defina a variável na configuração da esteira.\n\n{NO_DEPLOYMENT}"
            )
        if number == DRAFT_REVISION:
            raise DeployError(
                "TARGET_REVISION_NUMBER está em 1, a revisão Draft. A Draft é "
                "contexto de diagnóstico e não tem deploy: use o número da revisão "
                f"do ambiente (2 = DEV, 3 = HML, 4 = PRD).\n\n{NO_DEPLOYMENT}"
            )
        if number < DRAFT_REVISION:
            raise DeployError(
                f"TARGET_REVISION_NUMBER está em {number}, que não é número de "
                f"revisão.\n\n{NO_DEPLOYMENT}"
            )
        environment = self._settings.TARGET_ENVIRONMENT_ID
        if environment is None:
            raise DeployError(
                "TARGET_ENVIRONMENT_ID não está definida. Ela é o id, no Manager, do "
                "ambiente que recebe o deploy.\n\n"
                f"Defina a variável na configuração da esteira.\n\n{NO_DEPLOYMENT}"
            )
        return number, environment

    def _manifest(self, repo_path: Path) -> Dict[str, Any]:
        """`spec` do `api-basic-info.yaml`."""
        loaded = RepoCanonicalReader(self._importer).load(str(repo_path))
        if not loaded.basic_info:
            unreadable = next(
                (i for i in loaded.unreadable if "api-basic-info" in i.partition(": ")[0]),
                None,
            )
            if unreadable:
                file_path, _, reason = unreadable.partition(": ")
                raise DeployError(
                    f"O arquivo `{file_path}` não pôde ser lido: {reason}.\n\n"
                    f"{NO_DEPLOYMENT}"
                )
            raise DeployError(
                "Não encontrei o `api-basic-info.yaml` no repositório. É dele que "
                f"vem o id da API.\n\n{NO_DEPLOYMENT}"
            )
        spec = loaded.basic_info.get("spec") or {}
        if spec.get("id") is None:
            raise DeployError(
                "O `api-basic-info.yaml` não declara `spec.id`, o id da API no "
                f"Manager.\n\n{NO_DEPLOYMENT}"
            )
        return spec

    # --- E2 ------------------------------------------------------------------

    @staticmethod
    def _identity(spec: Dict[str, Any], api: Dict[str, Any]) -> None:
        """Confere `version` e `basePath` do manifesto contra o Manager."""
        try:
            RevisionWriter.guard_identity(spec, api)
        except IdentityMismatchError as exc:
            raise DeployError(
                "Este repositório parece apontar para outra API. O "
                f"`{exc.field_name}` declarado aqui é {exc.no_repo!r}, mas a API "
                f"{exc.api_id} no Manager tem {exc.no_manager!r}.\n\n"
                f"Confira o `id` em `api-basic-info.yaml`.\n\n{NO_DEPLOYMENT}"
            ) from exc

    @staticmethod
    def _revision(api: Dict[str, Any], number: int) -> Dict[str, Any]:
        """Revisão da API com o número informado."""
        revisions = api.get("revisions") or []
        for revision in revisions:
            if revision.get("revisionNumber") == number and revision.get("id") is not None:
                return revision
        if not revisions:
            available = "a API não tem nenhuma revisão"
        else:
            available = "Disponíveis: " + ", ".join(
                f"{r.get('revisionNumber')} (id {r.get('id')})" for r in revisions
            )
        raise DeployError(
            f"A API {api.get('id')} não tem revisão de número {number}. "
            f"{available}.\n\nCriar revisão é ato humano, pela interface do "
            f"Manager.\n\n{NO_DEPLOYMENT}"
        )

    @staticmethod
    def _environment(api: Dict[str, Any], environment_id: int) -> DeployEnvironment:
        """Ambiente alvo, entre os ligados à API."""
        linked = [e for e in api.get("environments") or [] if isinstance(e, dict)]
        for environment in linked:
            if environment.get("id") == environment_id:
                return DeployEnvironment(manager_id=environment_id, name=environment.get("name"))
        if linked:
            listing = "Ambientes ligados: " + ", ".join(
                f"{e.get('id')} ({e.get('name')})" for e in linked
            )
        else:
            listing = "A API não está ligada a nenhum ambiente"
        raise DeployError(
            f"A API {api.get('id')} não está ligada ao ambiente {environment_id}. "
            f"{listing}.\n\nConfira TARGET_ENVIRONMENT_ID ou ligue a API ao ambiente "
            f"no Manager.\n\n{NO_DEPLOYMENT}"
        )

    # --- E3 ------------------------------------------------------------------

    def _evaluate_governance(
        self, api: Dict[str, Any], revision: Dict[str, Any], environment_id: int
    ) -> Tuple[DeployGovernance, List[str]]:
        """Avalia os critérios do stage da revisão; devolve o resultado e os avisos."""
        precheck = self._governance.evaluate(revision, api.get("apiTags"))
        stage = precheck.stage or {}
        violations: List[str] = []

        allowed = [
            int(e) for e in stage.get("deployableEnvironments") or [] if _number(e) is not None
        ]
        if allowed and environment_id not in allowed:
            violations.append(
                f"O ambiente {environment_id} não está entre os que o stage "
                f"{precheck.stage_id} permite: "
                + ", ".join(str(p) for p in allowed)
                + "."
            )

        required = _number(stage.get("completenessRequisite")) if stage else None
        current: Optional[float] = None
        if required:
            current = self._manager_api.get_revision_completeness(revision["id"]).score
            if current < required:
                violations.append(
                    f"A completeness da revisão é {current:.1f}, e o stage exige "
                    f"{required:.1f}."
                )

        if precheck.missing_names:
            violations.append(
                "Faltam atributos exigidos pelo stage: "
                + ", ".join(str(f.name or f.attribute_id) for f in precheck.missing_names)
                + "."
            )

        logger.info(
            "deploy.governanca workflow=%s stage=%s ambiente=%s violacoes=%d",
            precheck.workflow_id,
            precheck.stage_id,
            environment_id,
            len(violations),
        )
        governance = DeployGovernance(
            workflow_id=precheck.workflow_id,
            stage_id=precheck.stage_id,
            deployable_environments=allowed,
            completeness_required=required,
            completeness_actual=current,
            required=[
                RequiredAttribute(e.attribute_id, e.name, e.tag_id) for e in precheck.required
            ],
            missing=[
                RequiredAttribute(f.attribute_id, f.name, f.tag_id) for f in precheck.missing_names
            ],
            violations=violations,
        )
        return governance, [f"Governança: {a}" for a in precheck.warnings]

    # --- E4 / E5 -------------------------------------------------------------

    def _write(
        self,
        revision: Dict[str, Any],
        environment: DeployEnvironment,
        base: Dict[str, Any],
        step: Callable[[str], None],
    ) -> Optional[int]:
        """Faz o deploy e devolve o id do registro criado."""
        step(f"Fazendo o deploy no ambiente {environment.name or environment.manager_id}")
        try:
            return self._manager_api.deploy_revision(environment.manager_id, revision["id"])
        except ManagerApiGovernanceBlockedError as exc:
            raise DeployGovernanceBlockedError(
                exc.workflow_id, base["governance"].stage_id, exc.messages
            ) from exc
        except ManagerApiTransportRejectedError as exc:
            reasons = exc.messages if exc.status_code in _STATUS_WITH_REASON else []
            logger.info(
                "deploy.recusado status_code=%s motivos=%d", exc.status_code, len(reasons)
            )
            if reasons:
                body = "O Manager recusou o deploy:\n\n" + "\n".join(
                    f"  - {m}" for m in reasons
                )
            else:
                body = manager_failure_message(classify_manager_failure(exc)) or (
                    INTERNAL_ERROR_MESSAGE
                )
            raise self._failure(base, body, attempted=True) from exc
        except ManagerApiError as exc:
            logger.info("deploy.falha_transporte type=%s", type(exc).__name__)
            body = manager_failure_message(classify_manager_failure(exc)) or (
                INTERNAL_ERROR_MESSAGE
            )
            raise self._failure(
                base,
                f"{body}\n\nNão foi possível confirmar se o deploy aconteceu. "
                "Confira o ambiente no Manager antes de rodar de novo.",
                attempted=True,
            ) from exc

    def _verify(
        self,
        api_id: int,
        deployment_id: Optional[int],
        revision: Dict[str, Any],
        environment: DeployEnvironment,
        base: Dict[str, Any],
        step: Callable[[str], None],
    ) -> Optional[DeployState]:
        """Relê a API e confirma o deploy criado; devolve o novo estado do ambiente."""
        step("Conferindo o deploy")
        try:
            after = self._manager_api.get_api_by_id(api_id) or {}
        except ManagerApiError as exc:
            raise self._failure(
                base,
                f"O Manager aceitou o deploy (id {deployment_id}), mas não consegui "
                "reler a API para conferir. Confira o ambiente no Manager.",
                attempted=True,
                accepted=True,
                deployment_id=deployment_id,
            ) from exc

        record = next(
            (
                d
                for d in deployments.api_records(after)
                if d.get("id") == deployment_id
            ),
            None,
        )
        verified = (
            record is not None
            and record.get("status") == deployments.DEPLOYED
            and record.get("environmentId") == environment.manager_id
            and record.get("revisionId") == revision["id"]
        )
        if not verified:
            logger.info(
                "deploy.divergente deployment_id=%s encontrado=%s",
                deployment_id,
                record is not None,
            )
            raise self._failure(
                base,
                f"O Manager aceitou o deploy (id {deployment_id}), mas a releitura "
                f"não mostra a revisão {revision.get('revisionNumber')} deployada no "
                f"ambiente {environment.manager_id}. Confira o ambiente no Manager.",
                attempted=True,
                accepted=True,
                deployment_id=deployment_id,
                new=_state(deployments.active_in_environment(after, environment.manager_id)),
            )
        return _state(record)

    @staticmethod
    def _failure(
        base: Dict[str, Any],
        message: str,
        *,
        attempted: bool,
        accepted: bool = False,
        deployment_id: Optional[int] = None,
        new: Optional[DeployState] = None,
    ) -> DeployFailedError:
        """Erro de deploy com o resultado `FAILED`."""
        view = DeployView(
            **base,
            new_state=new,
            deployment=DeploymentResult(
                attempted=attempted,
                accepted=accepted,
                deployment_id=deployment_id,
                verified=False,
                status=STATUS_FAILED,
                reason=message,
            ),
        )
        return DeployFailedError(message, view)
