"""Use-case do `sen publish` — grava o repositório na revisão do ambiente.

É a escrita do `validate` apontada para a revisão de `TARGET_REVISION_NUMBER`,
sem o diagnóstico em volta: não compara com a API-template nem lê completeness
(plano dos comandos §7). Roda só o que impede uma escrita errada, e só na
esteira (V-24 §6).

         só na esteira                          sem rede, antes de autenticar
         revisão alvo pelo número               sem rede — P-1
    E1   carregar o repositório                 sem rede — P-8
    C0   declared OpenAPI contract              no network — aborts BEFORE writing
    E2   API + guarda de identidade             GET      — P-3 / P-4 / P-10
         ambientes com a revisão no ar          do mesmo GET, só informativo
         Custom referenciados existem           GET
         pré-check de tags e governança         GET      — aborta ANTES de escrever
    C1   current swagger and what leaves it     GET      — warns only
    E3   PUT ÚNICO na revisão alvo              ESCRITA
    E3.1 conferência pós-publicação             GET      — 200 não é prova
    C2-4 contract in the swagger + verification WRITE  — problems become warnings
"""

import logging
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from apiops_orchestrator.application.exceptions.validate_exceptions import (
    GovernanceBlockedError,
    InvalidTagError,
    ValidateError,
)
from apiops_orchestrator.application.services.contract_writer import ContractWriter
from apiops_orchestrator.application.services.governance_precheck_service import (
    GovernancePrecheckService,
)
from apiops_orchestrator.application.services.ruler_service import RulerService
from apiops_orchestrator.application.services.revision_writer import RevisionWriter
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.deploy_model import DeployEnvironment
from apiops_orchestrator.domain.models.publish_view import (
    SCHEMA_SEN_PUBLISH_V1,
    PublishView,
    RevisionDeployment,
)
from apiops_orchestrator.domain.models.validate_view import (
    RequiredAttribute,
    GovernanceResult,
    ValidateApi,
    ValidateRevision,
)
from apiops_orchestrator.domain.ports.local_file_importer_port import (
    LocalFileImporterPort,
)
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort
from apiops_orchestrator.domain.services import deployments, revision_payload

logger = logging.getLogger(__name__)

PUBLISH_PIPELINE_ONLY = (
    "A publicação é feita só pela esteira: o comando não roda na sua máquina. "
    "Para conferir o repositório contra a governança, use `sen validate`, que "
    "grava na revisão Draft.\n\nNada foi publicado."
)


def require_pipeline(settings: Settings) -> None:
    """Recusa a publicação fora da esteira."""
    if not settings.pipeline_mode:
        raise ValidateError(PUBLISH_PIPELINE_ONLY)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _no_ar(api: Dict[str, Any], revision: Dict[str, Any]) -> List[RevisionDeployment]:
    """Ambientes em que a revisão está no ar, com o nome dos ligados à API."""
    names = {
        e.get("id"): e.get("name")
        for e in api.get("environments") or []
        if isinstance(e, dict)
    }
    return [
        RevisionDeployment(
            deployment_id=d.get("id"),
            environment=DeployEnvironment(
                manager_id=d["environmentId"], name=names.get(d["environmentId"])
            ),
            deployed_at=deployments.instant(d.get("deployDate")),
        )
        for d in deployments.active_for_revision(revision)
    ]


class PublishService:
    def __init__(
        self,
        manager_api: ManagerApiPort,
        importer: LocalFileImporterPort,
        settings: Settings,
    ):
        self._manager_api = manager_api
        self._settings = settings
        self._writer = RevisionWriter(manager_api, importer, command="publish")
        self._contract = ContractWriter(manager_api, command="publish")
        self._governance = GovernancePrecheckService(manager_api)
        # Só a verificação de `Custom`: a régua em si não é lida pelo publish.
        self._customs = RulerService(manager_api, settings)

    def publish(
        self,
        repo_path: Path,
        *,
        progress: Optional[Callable[[str], None]] = None,
    ) -> PublishView:
        """Grava o repositório na revisão alvo e confere o que ficou gravado."""
        step = progress or (lambda _: None)

        # Configuração primeiro: uma esteira mal configurada não deve gastar
        # autenticação nem rede para descobrir isso.
        require_pipeline(self._settings)
        number = self._target_number()

        step("Lendo o repositório")
        loaded = self._writer.load(repo_path)
        # Short descriptions are not repeated here: the completeness suggestions
        # of the pipeline already list them.
        contract, _ = self._contract.validate(loaded)
        spec = loaded.basic_info.get("spec") or {}

        step("Consultando a API no Manager")
        api = self._manager_api.get_api_by_id(spec.get("id")) or {}
        self._writer.guard_identity(spec, api)
        revision = self._writer.revision_by_number(api, number)
        target = self._manager_api.get_revision(revision["id"]) or {}

        # Antes da montagem: o `content` de um `Custom` novo vem do catálogo, e
        # um `Custom` ausente precisa abortar com o escopo que o declara.
        step("Verificando os interceptors Custom")
        self._customs.check_customs(self._writer.referenced_customs(loaded))

        assembled = revision_payload.assemble(
            draft=target,
            basic_info=loaded.basic_info,
            root=loaded.root,
            resources=loaded.resources,
            resolver_custom=self._writer.resolver_custom,
        )

        step("Verificando a governança")
        precheck = self._governance.evaluate(target, spec.get("apiTags"))
        warnings = list(assembled.warnings)
        warnings += [f"Governança: {warning}" for warning in precheck.warnings]
        # Antes do bloqueio: com tag inválida o Manager aceitaria e apagaria
        # todas as `apiTags` — é o erro mais destrutivo, e é do repositório.
        if precheck.invalid_tags:
            raise InvalidTagError(precheck.invalid_tags)
        if precheck.blocked:
            raise GovernanceBlockedError(
                workflow_id=precheck.workflow_id,
                stage_id=precheck.stage_id,
                missing=[
                    {"attributeId": f.attribute_id, "name": f.name}
                    for f in precheck.missing_names
                ],
            )

        prepared = self._contract.prepare(revision["id"], contract, step)
        warnings += prepared.warnings

        written = self._writer.write_and_verify(
            revision,
            assembled,
            step=step,
            write_label=f"Gravando a revisão {number} no Manager",
            rejection_target=f"da revisão {number}",
        )
        documentation = replace(
            self._contract.write(revision["id"], prepared, written.published, step),
            warnings=list(prepared.warnings),
        )
        if documentation.reason and documentation.reason not in warnings:
            warnings.append(documentation.reason)
        publication = written.result

        return PublishView(
            schema=SCHEMA_SEN_PUBLISH_V1,
            generated_at=_now(),
            execution_mode=self._settings.EXECUTION_MODE,
            api=ValidateApi(
                manager_id=spec.get("id"),
                name=api.get("name"),
                version=api.get("version"),
                base_path=api.get("basePath"),
            ),
            revision=ValidateRevision(
                manager_id=revision["id"], revision_number=revision.get("revisionNumber")
            ),
            governance=GovernanceResult(
                workflow_id=precheck.workflow_id,
                stage_id=precheck.stage_id,
                required=[
                    RequiredAttribute(e.attribute_id, e.name, e.tag_id)
                    for e in precheck.required
                ],
                missing=[],
                blocked=False,
            ),
            publication=publication,
            documentation=documentation,
            warnings=warnings,
            deployments=_no_ar(api, revision),
        )

    def _target_number(self) -> int:
        """Número da revisão alvo (V-24 P-1), obrigatório na esteira."""
        number = self._settings.TARGET_REVISION_NUMBER
        if number is None:
            raise ValidateError(
                "TARGET_REVISION_NUMBER não está definida. Na esteira ela é "
                "obrigatória: diz em qual revisão o repositório será gravado "
                "(2 = DEV, 3 = HML, 4 = PRD).\n\n"
                "Defina a variável na configuração da esteira e rode o comando "
                "novamente.\n\nNada foi publicado."
            )
        return number
