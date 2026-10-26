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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from apiops_orchestrator.application.exceptions.validate_exceptions import (
    GovernanceBlockedError,
    TagInvalidaError,
    ValidateError,
)
from apiops_orchestrator.application.services.contract_writer import ContractWriter
from apiops_orchestrator.application.services.governance_precheck_service import (
    GovernancePrecheckService,
)
from apiops_orchestrator.application.services.regua_service import ReguaService
from apiops_orchestrator.application.services.revision_writer import RevisionWriter
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.deploy_model import DeployEnvironment
from apiops_orchestrator.domain.models.publish_view import (
    SCHEMA_SEN_PUBLISH_V1,
    PublishView,
    RevisionDeployment,
)
from apiops_orchestrator.domain.models.validate_view import (
    AtributoExigido,
    GovernancaResultado,
    ValidateApi,
    ValidateRevision,
)
from apiops_orchestrator.domain.ports.local_file_importer_port import (
    LocalFileImporterPort,
)
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort
from apiops_orchestrator.domain.services import deployments, revision_payload

logger = logging.getLogger(__name__)

PUBLISH_SO_NA_ESTEIRA = (
    "A publicação é feita só pela esteira: o comando não roda na sua máquina. "
    "Para conferir o repositório contra a governança, use `sen validate`, que "
    "grava na revisão Draft.\n\nNada foi publicado."
)


def exigir_esteira(settings: Settings) -> None:
    """Recusa a publicação fora da esteira."""
    if not settings.modo_pipeline:
        raise ValidateError(PUBLISH_SO_NA_ESTEIRA)


def _agora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _no_ar(api: Dict[str, Any], revisao: Dict[str, Any]) -> List[RevisionDeployment]:
    """Ambientes em que a revisão está no ar, com o nome dos ligados à API."""
    nomes = {
        e.get("id"): e.get("name")
        for e in api.get("environments") or []
        if isinstance(e, dict)
    }
    return [
        RevisionDeployment(
            deployment_id=d.get("id"),
            environment=DeployEnvironment(
                manager_id=d["environmentId"], name=nomes.get(d["environmentId"])
            ),
            deployed_at=deployments.instante(d.get("deployDate")),
        )
        for d in deployments.ativos_da_revisao(revisao)
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
        self._escrita = RevisionWriter(manager_api, importer, comando="publish")
        self._contract = ContractWriter(manager_api, command="publish")
        self._governanca = GovernancePrecheckService(manager_api)
        # Só a verificação de `Custom`: a régua em si não é lida pelo publish.
        self._customs = ReguaService(manager_api, settings)

    def publish(
        self,
        repo_path: Path,
        *,
        progresso: Optional[Callable[[str], None]] = None,
    ) -> PublishView:
        """Grava o repositório na revisão alvo e confere o que ficou gravado."""
        etapa = progresso or (lambda _: None)

        # Configuração primeiro: uma esteira mal configurada não deve gastar
        # autenticação nem rede para descobrir isso.
        exigir_esteira(self._settings)
        numero = self._numero_alvo()

        etapa("Lendo o repositório")
        lido = self._escrita.carregar(repo_path)
        contract, contract_warnings = self._contract.validate(lido)
        spec = lido.basic_info.get("spec") or {}

        etapa("Consultando a API no Manager")
        api = self._manager_api.get_api_by_id(spec.get("id")) or {}
        self._escrita.guarda_identidade(spec, api)
        revisao = self._escrita.revisao_por_numero(api, numero)
        alvo = self._manager_api.get_revision(revisao["id"]) or {}

        # Antes da montagem: o `content` de um `Custom` novo vem do catálogo, e
        # um `Custom` ausente precisa abortar com o escopo que o declara.
        etapa("Verificando os interceptors Custom")
        self._customs.verificar_customs(self._escrita.customs_referenciados(lido))

        montado = revision_payload.montar(
            draft=alvo,
            basic_info=lido.basic_info,
            raiz=lido.raiz,
            recursos=lido.recursos,
            resolver_custom=self._escrita.resolver_custom,
        )

        etapa("Verificando a governança")
        precheck = self._governanca.avaliar(alvo, spec.get("apiTags"))
        avisos = list(montado.avisos)
        avisos += [f"Governança: {aviso}" for aviso in precheck.avisos]
        # Antes do bloqueio: com tag inválida o Manager aceitaria e apagaria
        # todas as `apiTags` — é o erro mais destrutivo, e é do repositório.
        if precheck.tags_invalidas:
            raise TagInvalidaError(precheck.tags_invalidas)
        if precheck.bloqueado:
            raise GovernanceBlockedError(
                workflow_id=precheck.workflow_id,
                stage_id=precheck.stage_id,
                missing=[
                    {"attributeId": f.attribute_id, "name": f.name}
                    for f in precheck.faltantes
                ],
            )

        prepared = self._contract.prepare(revisao["id"], contract, etapa)
        avisos += contract_warnings + prepared.warnings

        written = self._escrita.gravar_e_conferir(
            revisao,
            montado,
            etapa=etapa,
            rotulo_gravacao=f"Gravando a revisão {numero} no Manager",
            alvo_recusa=f"da revisão {numero}",
        )
        avisos += self._contract.write(revisao["id"], prepared, written.published, etapa)
        publicacao = written.result

        return PublishView(
            schema=SCHEMA_SEN_PUBLISH_V1,
            generated_at=_agora(),
            execution_mode=self._settings.EXECUTION_MODE,
            api=ValidateApi(
                manager_id=spec.get("id"),
                name=api.get("name"),
                version=api.get("version"),
                base_path=api.get("basePath"),
            ),
            revision=ValidateRevision(
                manager_id=revisao["id"], revision_number=revisao.get("revisionNumber")
            ),
            governanca=GovernancaResultado(
                workflow_id=precheck.workflow_id,
                stage_id=precheck.stage_id,
                required=[
                    AtributoExigido(e.attribute_id, e.name, e.tag_id)
                    for e in precheck.exigidos
                ],
                missing=[],
                blocked=False,
            ),
            publicacao=publicacao,
            avisos=avisos,
            deployments=_no_ar(api, revisao),
        )

    def _numero_alvo(self) -> int:
        """Número da revisão alvo (V-24 P-1), obrigatório na esteira."""
        numero = self._settings.TARGET_REVISION_NUMBER
        if numero is None:
            raise ValidateError(
                "TARGET_REVISION_NUMBER não está definida. Na esteira ela é "
                "obrigatória: diz em qual revisão o repositório será gravado "
                "(2 = DEV, 3 = HML, 4 = PRD).\n\n"
                "Defina a variável na configuração da esteira e rode o comando "
                "novamente.\n\nNada foi publicado."
            )
        return numero
