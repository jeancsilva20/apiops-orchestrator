"""Use-case do `sen validate` — orquestra a cascata E1→E4.

Recebe **ports**, nunca adapters concretos, espelhando o `CompletenessService`.

    E1   carregar o repositório                       sem rede
         ── visibilidade da API (api-visibility) ──   aborta logo após o GET da API
         ── guarda 1: version e basePath (D-11) ──    aborta antes de escrever
    E2   régua + conformidade + Custom                GET
         ── pré-check de governança ──                aborta ANTES de escrever
         ── guarda 2: confirmação ──                  só fora da esteira
    E3   PUT ÚNICO na revisão alvo                    ESCRITA
    E3.1 conferência pós-publicação                   GET — 200 não é prova
    E4   completeness                                 GET — informativo
"""

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from apiops_orchestrator.application.exceptions.validate_exceptions import (
    ApiInaccessibleError,
    GovernanceBlockedError,
    InvalidTagError,
    TemplateNotConfiguredError,
)
from apiops_orchestrator.application.enums.manager_failure_kind_enum import (
    ManagerFailureKind,
)
from apiops_orchestrator.application.services.api_access_guard import ApiAccessGuard
from apiops_orchestrator.application.services.contract_writer import (
    ContractWriter,
    PreparedContract,
)
from apiops_orchestrator.application.services.manager_failure_translator import (
    classify_manager_failure,
)
from apiops_orchestrator.application.services.governance_precheck_service import (
    GovernancePrecheckService,
)
from apiops_orchestrator.application.services.ruler_service import RulerService
from apiops_orchestrator.application.services.repo_importer_service import (
    LoadedRepository,
)
from apiops_orchestrator.application.services.revision_writer import (
    RevisionWriter,
    WrittenRevision,
)
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.models.validate_view import (
    SCHEMA_SEN_VALIDATE_V1,
    DOCUMENTATION_SCOPE,
    REPOSITORY_SCOPE,
    SEVERITY_WARNING,
    DocumentationResult,
    Finding,
    RequiredAttribute,
    CompletenessSummary,
    GovernanceResult,
    PublicationResult,
    RulerSnapshot,
    ValidateApi,
    ValidateRevision,
    ValidateView,
)
from apiops_orchestrator.domain.ports.local_file_importer_port import (
    LocalFileImporterPort,
)
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiPort,
    ManagerApiTransportRejectedError,
)
from apiops_orchestrator.domain.services import revision_payload
from apiops_orchestrator.domain.services.api_visibility import from_api_payload
from apiops_orchestrator.domain.services.interceptor_flow import (
    composed_flow,
    partition,
)
from apiops_orchestrator.domain.services.template_conformance import compare

logger = logging.getLogger(__name__)

GATE_COMPLETENESS = 70.0
DRAFT_REVISION = 1


def api_visible(
    manager_api: ManagerApiPort, access: ApiAccessGuard, api_id: Any
) -> Optional[Dict[str, Any]]:
    """`GET /apis/{id}` da API do repositório; `None` se ela não existe ou a sessão não a enxerga."""
    try:
        api = manager_api.get_api_by_id(api_id) or {}
    except ManagerApiTransportRejectedError as exc:
        if classify_manager_failure(exc) is not ManagerFailureKind.NOT_FOUND:
            raise
        return None
    return api if access.can_see(from_api_payload(api)) else None


def target_number(settings: Settings) -> int:
    """Número da revisão gravada: o configurado na esteira, sempre a Draft fora dela."""
    if not settings.pipeline_mode:
        return DRAFT_REVISION
    return settings.TARGET_REVISION_NUMBER or DRAFT_REVISION


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _only_inherits(no: Dict[str, Any]) -> bool:
    """Sem lista governada própria, o escopo executa o fluxo do escopo acima."""
    return not partition(no.get("interceptors"))[0]


def _repository_warnings(warnings: Sequence[str], scope: str = REPOSITORY_SCOPE) -> List[Finding]:
    return [Finding(severity=SEVERITY_WARNING, scope=scope, message=warning) for warning in warnings]


@dataclass
class _FlowOwner:
    """Escopo com fluxo próprio, e quantos escopos abaixo dele só o herdam."""

    scope: str
    effective: List[Dict[str, Any]]
    resources: int = 0
    routes: int = 0

    def heirs_suffix(self) -> str:
        parts = []
        if self.resources:
            parts.append(f"{self.resources} recurso" + ("s" if self.resources > 1 else ""))
        if self.routes:
            parts.append(f"{self.routes} rota" + ("s" if self.routes > 1 else ""))
        if not parts:
            return ""
        return f" — vale também para {' e '.join(parts)} que herdam este fluxo"


class ValidateService:
    def __init__(
        self,
        manager_api: ManagerApiPort,
        importer: LocalFileImporterPort,
        settings: Settings,
        session: Optional[LoginSession] = None,
    ):
        self._manager_api = manager_api
        self._importer = importer
        self._settings = settings
        self._access = ApiAccessGuard(session)
        self._ruler = RulerService(manager_api, settings)
        self._governance = GovernancePrecheckService(manager_api)
        self._writer = RevisionWriter(manager_api, importer, command="validate")
        self._contract = ContractWriter(manager_api, command="validate")

    # --- cascata -------------------------------------------------------------

    def validate(
        self,
        repo_path: Path,
        *,
        confirm: Callable[[str], bool],
        progress: Optional[Callable[[str], None]] = None,
    ) -> ValidateView:
        """Executa a cascata E1..E4.

        `progress` é opcional e serve só à apresentação: a borda usa para
        narrar em que etapa a espera está. Como o comando faz cinco chamadas de
        rede em sequência, uma barra sem rótulo deixaria o dev sem saber se o
        que demora é a leitura da template ou a publicação. O serviço não sabe
        o que a borda faz com o texto — pode ser barra, log ou nada.
        """
        step = progress or (lambda _: None)

        # Configuração primeiro: uma esteira mal configurada não deve gastar
        # autenticação nem rede para descobrir isso.
        if self._settings.pipeline_mode and self._settings.TEMPLATE_API_ID is None:
            raise TemplateNotConfiguredError()

        step("Lendo o repositório")
        loaded = self._writer.load(repo_path)
        unread_warnings = self._writer.unread_files_warnings(loaded)
        contract, contract_warnings = self._contract.validate(loaded)
        spec = loaded.basic_info.get("spec") or {}

        step("Consultando a API no Manager")
        api = api_visible(self._manager_api, self._access, spec.get("id"))
        if api is None:
            raise ApiInaccessibleError(spec.get("id"))
        self._writer.guard_identity(spec, api)

        revision = self._target_revision(api)
        draft = self._manager_api.get_revision(revision["id"]) or {}

        # O payload é montado ANTES da conformidade, de propósito: a E2 precisa
        # avaliar o fluxo que SERÁ publicado, não o que está lá. Avaliar o
        # remoto faria o comando relatar o estado anterior à edição do dev —
        # ele só veria o efeito da própria mudança rodando o comando de novo.
        # A montagem é pura; o payload é o mesmo objeto usado na E3.
        step("Lendo a API-template")
        ruler = self._e2_ruler(loaded)

        step("Comparando com o padrão")
        assembled = revision_payload.assemble(
            draft=draft,
            basic_info=loaded.basic_info,
            root=loaded.root,
            resources=loaded.resources,
            resolver_custom=self._writer.resolver_custom,
        )
        findings = self._conformance(assembled.body, ruler)
        # Em local, o que vai sair do Manager é mostrado na confirmação, antes
        # da gravação, e não se repete no resultado. Na esteira não há pergunta.
        if self._settings.pipeline_mode:
            findings.extend(_repository_warnings(unread_warnings + list(assembled.warnings)))

        step("Verificando a governança")
        precheck = self._governance.evaluate(draft, spec.get("apiTags"))
        # Os avisos dizem quando o pré-check não pôde antecipar a governança
        # (revisão sem workflow, stage ausente, tag específica): o dev precisa
        # saber que o veredito virá da gravação.
        findings.extend(
            Finding(
                severity=SEVERITY_WARNING,
                scope=REPOSITORY_SCOPE,
                message=f"Governança: {warning}",
            )
            for warning in precheck.warnings
        )
        # Antes do bloqueio de governança: com tag inválida o Manager aceitaria e
        # apagaria todas as `apiTags` — é o erro mais destrutivo, e é do repositório.
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
        # Short descriptions go only to the confirmation: after the write, the
        # completeness suggestions already list them. What leaves the
        # documentation goes to the confirmation in local and to the output in
        # the pipeline, where there is no confirmation.
        reported = list(prepared.warnings) if self._settings.pipeline_mode else []
        findings.extend(_repository_warnings(reported, DOCUMENTATION_SCOPE))

        written = self._e3_publish(
            assembled,
            revision,
            confirm,
            step,
            prepared,
            list(contract_warnings) + list(prepared.warnings),
            repository_warnings=unread_warnings,
        )
        publication = written.result if written else PublicationResult(attempted=False)

        documentation = DocumentationResult(warnings=reported)
        if written is not None:
            documentation = replace(
                self._contract.write(revision["id"], prepared, written.published, step),
                warnings=reported,
            )
            if documentation.reason and documentation.reason not in reported:
                findings.extend(_repository_warnings([documentation.reason], DOCUMENTATION_SCOPE))
            step("Calculando o quality score")
            completeness = self._e4_completeness(revision["id"])
        else:
            completeness = CompletenessSummary()

        return ValidateView(
            schema=SCHEMA_SEN_VALIDATE_V1,
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
            ruler=RulerSnapshot(
                template_id=ruler.template_id,
                revision_number=ruler.revision_number,
                flow_hash=ruler.flow_hash,
                interceptors_count=ruler.total,
            ),
            findings=findings,
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
            completeness=completeness,
        )

    # --- revisão alvo ---------------------------------------------------------

    def _target_revision(self, api: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve a revisão pelo NÚMERO (V-24); fora da esteira é sempre a Draft (V-24 §6)."""
        return self._writer.revision_by_number(api, target_number(self._settings))

    # --- E2 ------------------------------------------------------------------

    def _e2_ruler(self, loaded: LoadedRepository):
        """Lê a régua e verifica os `Custom` referenciados — ambos abortam se falham."""
        ruler = self._ruler.load(loaded.basic_info)
        self._ruler.check_customs(self._writer.referenced_customs(loaded))
        return ruler

    def _conformance(self, payload: Dict[str, Any], ruler) -> List[Finding]:
        """Compara com a régua o fluxo efetivo DO PAYLOAD, escopo a escopo.

        Escopo que só herda executa o mesmo fluxo do escopo acima: compará-lo
        repetiria os mesmos achados em cada recurso e rota. O achado sai uma vez,
        no escopo dono do fluxo, dizendo quantos recursos e rotas também o
        executam.
        """
        root = _FlowOwner("raiz da revision", composed_flow(payload.get("interceptors")))
        owners = [root]
        for resource in payload.get("resources") or []:
            if _only_inherits(resource):
                resource_owner = root
                root.resources += 1
            else:
                resource_owner = _FlowOwner(
                    f"resource {resource.get('name')}",
                    composed_flow(resource.get("interceptors"), root.effective),
                )
                owners.append(resource_owner)
            for op in resource.get("operations") or []:
                if _only_inherits(op):
                    resource_owner.routes += 1
                    continue
                owners.append(
                    _FlowOwner(
                        f"{str(op.get('method') or '').upper()} {op.get('path')}",
                        composed_flow(op.get("interceptors"), resource_owner.effective),
                    )
                )

        findings: List[Finding] = []
        for owner in owners:
            suffix = owner.heirs_suffix()
            findings.extend(
                self._translate(compare(owner.effective, ruler.interceptors, owner.scope), suffix)
            )
        return findings

    @staticmethod
    def _translate(findings, suffix: str = "") -> List[Finding]:
        return [
            Finding(
                severity=a.severity,
                scope=a.scope,
                message=a.message + suffix,
                interceptor_type=a.kind,
                custom_interceptor_id=a.custom_interceptor_id,
            )
            for a in findings
        ]

    # --- E3 / E3.1 -----------------------------------------------------------

    def _e3_publish(
        self,
        assembled: "revision_payload.AssembledPayload",
        revision: Dict[str, Any],
        confirm: Callable[[str], bool],
        step: Callable[[str], None] = lambda _: None,
        prepared: Optional[PreparedContract] = None,
        documentation_warnings: Sequence[str] = (),
        repository_warnings: Sequence[str] = (),
    ) -> Optional[WrittenRevision]:
        # Guarda 2 (D-9): em local a escrita é ato deliberado do dev.
        #
        # O texto diz o que o comando faz, não o nome da operação interna: a
        # versão anterior ("Publicar na revisão N") parecia anunciar uma subida
        # para ambiente com deploy. O que acontece aqui é uma gravação no
        # rascunho, que é o único jeito de obter o veredito da governança.
        if not self._settings.pipeline_mode:
            # A pergunta em si ("Deseja prosseguir?") fica na borda: o serviço
            # não sabe que a confirmação é um sim/não de terminal.
            contract_line = (
                "O swagger da revisão também recebe o contrato OpenAPI do repositório.\n"
                if prepared is not None and prepared.write
                else ""
            )
            question = self._writer.confirmation_text(
                "Para validar a sua API, uma versão de rascunho será gravada no "
                f"API Manager, na revisão {revision.get('revisionNumber')} "
                f"(id {revision['id']}).\n"
                f"{contract_line}"
                "Nenhum ambiente recebe deploy, e nada é promovido.",
                list(repository_warnings)
                + list(assembled.warnings)
                + list(documentation_warnings),
            )
            if not confirm(question):
                return None

        # E3 + E3.1: UM ÚNICO PUT (W-7) e a conferência — 200 não é prova (W-8).
        return self._writer.write_and_verify(
            revision,
            assembled,
            step=step,
            write_label="Gravando o rascunho no Manager",
            rejection_target="do rascunho",
        )

    # --- E4 ------------------------------------------------------------------

    def _e4_completeness(self, revision_id: int) -> CompletenessSummary:
        """Informativa: o gate de 70% trava em DEV+, não na Draft."""
        try:
            reading = self._manager_api.get_revision_completeness(revision_id)
        except Exception as exc:  # degrada: não é o veredito do comando
            logger.info("validate.completeness.indisponivel motivo=%s", exc)
            return CompletenessSummary()
        return CompletenessSummary(
            score=getattr(reading, "score", None),
            gate_percent=GATE_COMPLETENESS,
            suggestions=list(getattr(reading, "suggestions", []) or []),
        )
