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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from apiops_orchestrator.application.exceptions.validate_exceptions import (
    GovernanceBlockedError,
    IdentidadeDivergenteError,
    LayoutInvalidoError,
    PublicacaoDivergenteError,
    ValidateError,
)
from apiops_orchestrator.application.services.governance_precheck_service import (
    GovernancePrecheckService,
)
from apiops_orchestrator.application.services.regua_service import ReguaService
from apiops_orchestrator.application.services.repo_importer_service import (
    RepoCanonicalReader,
    RepositorioCarregado,
)
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
from apiops_orchestrator.domain.services.interceptor_flow import fluxo_efetivo
from apiops_orchestrator.domain.services.template_conformance import comparar

logger = logging.getLogger(__name__)

GATE_COMPLETENESS = 70.0


def _agora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
        self._cache_custom: Dict[int, Optional[Dict[str, Any]]] = {}

    def _resolver_custom(self, custom_id: int) -> Optional[Dict[str, Any]]:
        """`{id, name, script}` do catálogo, para o `content` de um `Custom` novo.

        A existência já foi verificada na E2 e aborta lá se faltar; aqui o
        objetivo é só o conteúdo. O cache evita repetir o GET quando o mesmo
        `Custom` aparece em vários escopos.
        """
        if custom_id not in self._cache_custom:
            self._cache_custom[custom_id] = self._manager_api.get_custom_interceptor_by_id(
                custom_id
            )
        return self._cache_custom[custom_id]

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

        etapa("Lendo o repositório")
        lido = self._e1_carregar(repo_path)
        spec = lido.basic_info.get("spec") or {}

        etapa("Consultando a API no Manager")
        api = self._manager_api.get_api_by_id(spec.get("id")) or {}
        self._guarda_identidade(spec, api)

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
            resolver_custom=self._resolver_custom,
        )
        achados = self._conformidade(montado.corpo, regua)
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

    # --- E1 ------------------------------------------------------------------

    def _e1_carregar(self, repo_path: Path) -> RepositorioCarregado:
        """Carrega o repositório. Sem rede — é o que permite abortar antes."""
        lido = RepoCanonicalReader(self._importer).carregar(str(repo_path))
        if lido.faltando:
            ausente = lido.faltando[0]
            pista = ""
            if lido.ignorados:
                pista = f"Arquivos não reconhecidos na mesma árvore: {', '.join(lido.ignorados[:3])}."
            raise LayoutInvalidoError(ausente, pista or None)
        if lido.ilegiveis:
            raise LayoutInvalidoError(
                lido.ilegiveis[0].split(":")[0],
                "O arquivo existe mas não pôde ser lido: " + lido.ilegiveis[0],
            )
        return lido

    def _guarda_identidade(self, spec: Dict[str, Any], api: Dict[str, Any]) -> None:
        """Guarda 1 (D-11): `version` e `basePath` definem a identidade da API.

        `spec.id` NÃO aborta — é o endereço do GET, não a identidade funcional.
        """
        for campo in ("version", "basePath"):
            no_repo = spec.get(campo)
            no_manager = api.get(campo)
            if no_repo is not None and str(no_repo) != str(no_manager):
                raise IdentidadeDivergenteError(
                    campo, str(no_repo), str(no_manager), spec.get("id")
                )

    def _revisao_alvo(self, api: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve a revisão pelo NÚMERO (V-24); o id é detalhe de transporte."""
        numero = self._settings.TARGET_REVISION_NUMBER
        if not self._settings.modo_pipeline and numero != 1:
            raise ValidateError(
                f"Em modo local a única revisão publicável é a 1 (Draft), e "
                f"TARGET_REVISION_NUMBER está em {numero}. A Draft não é ambiente "
                "e não tem deploy: publicar nela é diagnóstico, não promoção."
            )
        for revisao in api.get("revisions") or []:
            if revisao.get("revisionNumber") == numero:
                return revisao
        raise ValidateError(
            f"A API não tem revisão de número {numero}. Disponíveis: "
            + ", ".join(
                str(r.get("revisionNumber")) for r in (api.get("revisions") or [])
            )
        )

    # --- E2 ------------------------------------------------------------------

    def _e2_regua(self, lido: RepositorioCarregado):
        """Lê a régua e verifica os `Custom` referenciados — ambos abortam se falham."""
        regua = self._regua.carregar(lido.basic_info)
        self._regua.verificar_customs(self._customs_referenciados(lido))
        return regua

    def _conformidade(self, payload: Dict[str, Any], regua) -> List[Achado]:
        """Compara com a régua o fluxo efetivo DO PAYLOAD, escopo a escopo."""
        achados: List[Achado] = []
        raiz = fluxo_efetivo(payload.get("interceptors"), [])
        achados.extend(
            self._traduzir(comparar(raiz, regua.interceptors, "raiz da revision"))
        )
        for recurso in payload.get("resources") or []:
            nome = recurso.get("name")
            efetivo = fluxo_efetivo(recurso.get("interceptors"), raiz)
            achados.extend(
                self._traduzir(comparar(efetivo, regua.interceptors, f"resource {nome}"))
            )
            for op in recurso.get("operations") or []:
                rotulo = f"{str(op.get('method') or '').upper()} {op.get('path')}"
                achados.extend(
                    self._traduzir(
                        comparar(
                            fluxo_efetivo(op.get("interceptors"), efetivo),
                            regua.interceptors,
                            rotulo,
                        )
                    )
                )
        return achados

    @staticmethod
    def _customs_referenciados(lido: RepositorioCarregado):
        """Pares `(id, escopo)` de todo `Custom` que o repositório declara."""
        def do_bloco(bloco: Dict[str, Any], escopo: str):
            for chave in ("interceptors_request", "interceptors_response"):
                for item in bloco.get(chave) or []:
                    if item.get("type") == "Custom" and item.get("id") is not None:
                        yield (item["id"], escopo)

        yield from do_bloco(lido.raiz, "all.yaml")
        for recurso in lido.recursos:
            yield from do_bloco(recurso.dados or {}, recurso.caminho)
            for op in recurso.operacoes:
                yield from do_bloco(op.dados or {}, op.caminho)

    @staticmethod
    def _traduzir(achados) -> List[Achado]:
        return [
            Achado(
                severity=a.severidade,
                scope=a.escopo,
                message=a.mensagem,
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
            pergunta = (
                "Para validar a sua API, uma versão de rascunho será gravada no "
                f"API Manager, na revisão {revisao.get('revisionNumber')} "
                f"(id {revisao['id']}).\n"
                "Nenhum ambiente recebe deploy, e nada é promovido."
            )
            if not confirmar(pergunta):
                return PublicacaoResultado(attempted=False)

        # E3: UM ÚNICO PUT (W-7). `workflowId`/`workflowStageId` viajam na cópia
        # profunda do estado remoto — nada aqui os reescreve (D-020).
        etapa("Gravando o rascunho no Manager")
        self._manager_api.update_revision(revisao["id"], montado.corpo)

        # E3.1: HTTP 200 não é prova de sucesso (W-8).
        etapa("Conferindo o que foi gravado")
        publicado = self._manager_api.get_revision(revisao["id"]) or {}
        divergencias = revision_payload.conferir(montado.corpo, publicado)
        if divergencias:
            raise PublicacaoDivergenteError(divergencias)

        return PublicacaoResultado(attempted=True, accepted=True, verified=True)

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
