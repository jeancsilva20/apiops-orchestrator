"""Use-case do `sen validate` — orquestra a cascata E1→E4.

Recebe **ports**, nunca adapters concretos, espelhando o `CompletenessService`.

    E1   carregar o repositório                       sem rede
         ── guarda 1: version e basePath (D-11) ──    aborta antes de escrever
    E2   régua + conformidade + Custom                GET
         ── pré-check de governança ──                aborta ANTES de escrever
         ── guarda 2: confirmação ──                  só em EXECUTION_MODE=local
    E3   PUT ÚNICO na revisão alvo                    ESCRITA
    E3.1 conferência pós-publicação                   GET — 200 não é prova
    E4   completeness                                 GET — informativo
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from apiops_orchestrator.application.exceptions.validate_exceptions import (
    GovernanceBlockedError,
    TagInvalidaError,
    TemplateNaoConfiguradaError,
    ValidateError,
)
from apiops_orchestrator.application.services.governance_precheck_service import (
    GovernancePrecheckService,
)
from apiops_orchestrator.application.services.regua_service import ReguaService
from apiops_orchestrator.application.services.repo_importer_service import (
    RepositorioCarregado,
)
from apiops_orchestrator.application.services.revision_writer import RevisionWriter
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.models.validate_view import (
    SCHEMA_SEN_VALIDATE_V1,
    ESCOPO_REPOSITORIO,
    SEVERIDADE_WARNING,
    Achado,
    AtributoExigido,
    CompletenessResumo,
    GovernancaResultado,
    PublicacaoResultado,
    ReguaSnapshot,
    ValidateApi,
    ValidateRevision,
    ValidateView,
)
from apiops_orchestrator.domain.ports.local_file_importer_port import (
    LocalFileImporterPort,
)
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort
from apiops_orchestrator.domain.services import revision_payload
from apiops_orchestrator.domain.services.interceptor_flow import (
    fluxo_efetivo,
    particionar,
)
from apiops_orchestrator.domain.services.template_conformance import comparar

logger = logging.getLogger(__name__)

GATE_COMPLETENESS = 70.0


def _agora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _so_herda(no: Dict[str, Any]) -> bool:
    """Sem lista governada própria, o escopo executa o fluxo do escopo acima."""
    return not particionar(no.get("interceptors"))[0]


@dataclass
class _DonoDoFluxo:
    """Escopo com fluxo próprio, e quantos escopos abaixo dele só o herdam."""

    escopo: str
    efetivo: List[Dict[str, Any]]
    recursos: int = 0
    rotas: int = 0

    def sufixo_dos_herdeiros(self) -> str:
        partes = []
        if self.recursos:
            partes.append(f"{self.recursos} recurso" + ("s" if self.recursos > 1 else ""))
        if self.rotas:
            partes.append(f"{self.rotas} rota" + ("s" if self.rotas > 1 else ""))
        if not partes:
            return ""
        return f" — vale também para {' e '.join(partes)} que herdam este fluxo"


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
        self._session = session
        self._regua = ReguaService(manager_api, settings)
        self._governanca = GovernancePrecheckService(manager_api)
        self._escrita = RevisionWriter(manager_api, importer, comando="validate")

    # --- cascata -------------------------------------------------------------

    def validate(
        self,
        repo_path: Path,
        *,
        confirmar: Callable[[str], bool],
        progresso: Optional[Callable[[str], None]] = None,
    ) -> ValidateView:
        """Executa a cascata E1..E4.

        `progresso` é opcional e serve só à apresentação: a borda usa para
        narrar em que etapa a espera está. Como o comando faz cinco chamadas de
        rede em sequência, uma barra sem rótulo deixaria o dev sem saber se o
        que demora é a leitura da template ou a publicação. O serviço não sabe
        o que a borda faz com o texto — pode ser barra, log ou nada.
        """
        etapa = progresso or (lambda _: None)

        # Configuração primeiro: uma esteira mal configurada não deve gastar
        # autenticação nem rede para descobrir isso.
        if self._settings.modo_pipeline and self._settings.TEMPLATE_API_ID is None:
            raise TemplateNaoConfiguradaError()

        etapa("Lendo o repositório")
        lido = self._escrita.carregar(repo_path)
        spec = lido.basic_info.get("spec") or {}

        etapa("Consultando a API no Manager")
        api = self._manager_api.get_api_by_id(spec.get("id")) or {}
        self._escrita.guarda_identidade(spec, api)

        revisao = self._revisao_alvo(api)
        draft = self._manager_api.get_revision(revisao["id"]) or {}

        # O payload é montado ANTES da conformidade, de propósito: a E2 precisa
        # avaliar o fluxo que SERÁ publicado, não o que está lá. Avaliar o
        # remoto faria o comando relatar o estado anterior à edição do dev —
        # ele só veria o efeito da própria mudança rodando o comando de novo.
        # A montagem é pura; o payload é o mesmo objeto usado na E3.
        etapa("Lendo a API-template")
        regua = self._e2_regua(lido)

        etapa("Comparando com o padrão")
        montado = revision_payload.montar(
            draft=draft,
            basic_info=lido.basic_info,
            raiz=lido.raiz,
            recursos=lido.recursos,
            resolver_custom=self._escrita.resolver_custom,
        )
        achados = self._conformidade(montado.corpo, regua)
        # Em local, o que vai sair do Manager é mostrado na confirmação, antes
        # da gravação, e não se repete no resultado. Na esteira não há pergunta.
        if self._settings.modo_pipeline:
            achados.extend(
                Achado(
                    severity=SEVERIDADE_WARNING,
                    scope=ESCOPO_REPOSITORIO,
                    message=aviso,
                )
                for aviso in montado.avisos
            )

        etapa("Verificando a governança")
        precheck = self._governanca.avaliar(draft, spec.get("apiTags"))
        # Os avisos dizem quando o pré-check não pôde antecipar a governança
        # (revisão sem workflow, stage ausente, tag específica): o dev precisa
        # saber que o veredito virá da gravação.
        achados.extend(
            Achado(
                severity=SEVERIDADE_WARNING,
                scope=ESCOPO_REPOSITORIO,
                message=f"Governança: {aviso}",
            )
            for aviso in precheck.avisos
        )
        # Antes do bloqueio de governança: com tag inválida o Manager aceitaria e
        # apagaria todas as `apiTags` — é o erro mais destrutivo, e é do repositório.
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

        publicacao = self._e3_publicar(montado, revisao, confirmar, etapa)

        if publicacao.attempted:
            etapa("Calculando o quality score")
            completeness = self._e4_completeness(revisao["id"])
        else:
            completeness = CompletenessResumo()

        return ValidateView(
            schema=SCHEMA_SEN_VALIDATE_V1,
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
            regua=ReguaSnapshot(
                template_id=regua.template_id,
                revision_number=regua.revision_number,
                flow_hash=regua.flow_hash,
                interceptors_count=regua.total,
            ),
            achados=achados,
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
            completeness=completeness,
        )

    # --- revisão alvo ---------------------------------------------------------

    def _revisao_alvo(self, api: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve a revisão pelo NÚMERO (V-24); ausente vale como Draft."""
        numero = self._settings.TARGET_REVISION_NUMBER or 1
        if not self._settings.modo_pipeline and numero != 1:
            raise ValidateError(
                f"Em modo local a única revisão publicável é a 1 (Draft), e "
                f"TARGET_REVISION_NUMBER está em {numero}. A Draft não é ambiente "
                "e não tem deploy: publicar nela é diagnóstico, não promoção."
            )
        return self._escrita.revisao_por_numero(api, numero)

    # --- E2 ------------------------------------------------------------------

    def _e2_regua(self, lido: RepositorioCarregado):
        """Lê a régua e verifica os `Custom` referenciados — ambos abortam se falham."""
        regua = self._regua.carregar(lido.basic_info)
        self._regua.verificar_customs(self._escrita.customs_referenciados(lido))
        return regua

    def _conformidade(self, payload: Dict[str, Any], regua) -> List[Achado]:
        """Compara com a régua o fluxo efetivo DO PAYLOAD, escopo a escopo.

        Escopo que só herda executa o mesmo fluxo do escopo acima: compará-lo
        repetiria os mesmos achados em cada recurso e rota. O achado sai uma vez,
        no escopo dono do fluxo, dizendo quantos recursos e rotas também o
        executam.
        """
        raiz = _DonoDoFluxo("raiz da revision", fluxo_efetivo(payload.get("interceptors"), []))
        donos = [raiz]
        for recurso in payload.get("resources") or []:
            if _so_herda(recurso):
                dono_do_recurso = raiz
                raiz.recursos += 1
            else:
                dono_do_recurso = _DonoDoFluxo(
                    f"resource {recurso.get('name')}",
                    fluxo_efetivo(recurso.get("interceptors"), raiz.efetivo),
                )
                donos.append(dono_do_recurso)
            for op in recurso.get("operations") or []:
                if _so_herda(op):
                    dono_do_recurso.rotas += 1
                    continue
                donos.append(
                    _DonoDoFluxo(
                        f"{str(op.get('method') or '').upper()} {op.get('path')}",
                        fluxo_efetivo(op.get("interceptors"), dono_do_recurso.efetivo),
                    )
                )

        achados: List[Achado] = []
        for dono in donos:
            sufixo = dono.sufixo_dos_herdeiros()
            achados.extend(
                self._traduzir(comparar(dono.efetivo, regua.interceptors, dono.escopo), sufixo)
            )
        return achados

    @staticmethod
    def _traduzir(achados, sufixo: str = "") -> List[Achado]:
        return [
            Achado(
                severity=a.severidade,
                scope=a.escopo,
                message=a.mensagem + sufixo,
                interceptor_type=a.tipo,
                custom_interceptor_id=a.custom_interceptor_id,
            )
            for a in achados
        ]

    # --- E3 / E3.1 -----------------------------------------------------------

    def _e3_publicar(
        self,
        montado: "revision_payload.PayloadMontado",
        revisao: Dict[str, Any],
        confirmar: Callable[[str], bool],
        etapa: Callable[[str], None] = lambda _: None,
    ) -> PublicacaoResultado:
        # Guarda 2 (D-9): em local a escrita é ato deliberado do dev.
        #
        # O texto diz o que o comando faz, não o nome da operação interna: a
        # versão anterior ("Publicar na revisão N") parecia anunciar uma subida
        # para ambiente com deploy. O que acontece aqui é uma gravação no
        # rascunho, que é o único jeito de obter o veredito da governança.
        if not self._settings.modo_pipeline:
            # A pergunta em si ("Deseja prosseguir?") fica na borda: o serviço
            # não sabe que a confirmação é um sim/não de terminal.
            pergunta = self._escrita.texto_de_confirmacao(
                "Para validar a sua API, uma versão de rascunho será gravada no "
                f"API Manager, na revisão {revisao.get('revisionNumber')} "
                f"(id {revisao['id']}).\n"
                "Nenhum ambiente recebe deploy, e nada é promovido.",
                montado.avisos,
            )
            if not confirmar(pergunta):
                return PublicacaoResultado(attempted=False)

        # E3 + E3.1: UM ÚNICO PUT (W-7) e a conferência — 200 não é prova (W-8).
        return self._escrita.gravar_e_conferir(
            revisao,
            montado,
            etapa=etapa,
            rotulo_gravacao="Gravando o rascunho no Manager",
            alvo_recusa="do rascunho",
        )

    # --- E4 ------------------------------------------------------------------

    def _e4_completeness(self, revision_id: int) -> CompletenessResumo:
        """Informativa: o gate de 70% trava em DEV+, não na Draft."""
        try:
            leitura = self._manager_api.get_revision_completeness(revision_id)
        except Exception as exc:  # degrada: não é o veredito do comando
            logger.info("validate.completeness.indisponivel motivo=%s", exc)
            return CompletenessResumo()
        return CompletenessResumo(
            score=getattr(leitura, "score", None),
            gate_percent=GATE_COMPLETENESS,
            suggestions=list(getattr(leitura, "suggestions", []) or []),
        )
