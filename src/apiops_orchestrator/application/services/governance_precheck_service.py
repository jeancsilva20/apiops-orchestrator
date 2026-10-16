"""Pré-check do Adaptive Governance — roda ANTES da escrita.

O faltante é **calculado**, nunca extraído de `messages[]`. A mensagem do erro
(`"API must contain attribute CLI"`) é texto livre; derivar o nome do atributo
dali seria heurística frágil, e o comportamento precisa ser determinístico
(V-23 §4).

    exigidos(mustHave do stage) − presentes(apiTags do repositório) = faltantes

O par `workflowId`/`workflowStageId` vem da **revisão alvo**, lido em runtime e
nunca configurado (D-020). Nada aqui pode ser fixado em código: os requisitos
são configuração mutável do tenant — entre 2026-10-14 e 2026-10-15 o stage 1402
trocou `96 CLI` por `231 teste giroto` sem que o orquestrador mudasse.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AtributoExigido:
    attribute_id: int
    name: Optional[str] = None
    tag_id: Optional[int] = None


@dataclass(frozen=True)
class PrecheckResultado:
    workflow_id: Optional[int]
    stage_id: Optional[int]
    exigidos: List[AtributoExigido] = field(default_factory=list)
    faltantes: List[AtributoExigido] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)

    @property
    def bloqueado(self) -> bool:
        return bool(self.faltantes)


class GovernancePrecheckService:
    def __init__(self, manager_api: ManagerApiPort):
        self._manager_api = manager_api

    def avaliar(
        self, revisao: Dict[str, Any], api_tags: Optional[Sequence[Dict[str, Any]]]
    ) -> PrecheckResultado:
        """Calcula o que falta para o stage da revisão alvo aceitar a publicação."""
        workflow_id = revisao.get("workflowId")
        stage_id = revisao.get("workflowStageId")
        avisos: List[str] = []

        if workflow_id is None or stage_id is None:
            avisos.append(
                "a revisão alvo não declara `workflowId`/`workflowStageId`; "
                "o Adaptive Governance não pode ser antecipado"
            )
            return PrecheckResultado(workflow_id, stage_id, avisos=avisos)

        workflow = self._manager_api.get_workflow(workflow_id) or {}
        stage = self._encontrar_stage(workflow, stage_id)
        if stage is None:
            # A plataforma já exibiu esse estado uma vez (V-23 §3): a revisão
            # apontava um stage de outro workflow. Degradar com mensagem é
            # melhor do que assumir que não há requisito.
            avisos.append(
                f"o stage {stage_id} não existe no workflow {workflow_id}. O "
                "pré-check não pôde ser calculado, e o veredito virá da própria "
                "publicação."
            )
            return PrecheckResultado(workflow_id, stage_id, avisos=avisos)

        requisitos = [
            r for r in (stage.get("attributesRequisites") or []) if r.get("mustHave")
        ]
        if not requisitos:
            return PrecheckResultado(workflow_id, stage_id, avisos=avisos)

        catalogo = self._catalogo()
        exigidos = [
            AtributoExigido(
                attribute_id=r.get("attributeId"),
                name=catalogo.get(r.get("attributeId")),
                tag_id=r.get("tagId"),
            )
            for r in requisitos
        ]

        presentes = self._presentes(api_tags, catalogo)
        faltantes = [e for e in exigidos if e.attribute_id not in presentes]

        logger.info(
            "governanca.precheck workflow=%s stage=%s exigidos=%d faltantes=%d",
            workflow_id,
            stage_id,
            len(exigidos),
            len(faltantes),
        )
        return PrecheckResultado(workflow_id, stage_id, exigidos, faltantes, avisos)

    # --- apoio ---------------------------------------------------------------

    @staticmethod
    def _encontrar_stage(
        workflow: Dict[str, Any], stage_id: int
    ) -> Optional[Dict[str, Any]]:
        for stage in workflow.get("stages") or []:
            if stage.get("workflowStageId") == stage_id:
                return stage
        return None

    def _catalogo(self) -> Dict[int, str]:
        return {
            a.get("id"): a.get("name")
            for a in (self._manager_api.list_attributes() or [])
            if a.get("id") is not None
        }

    @staticmethod
    def _presentes(
        api_tags: Optional[Sequence[Dict[str, Any]]], catalogo: Dict[int, str]
    ) -> set:
        """Ids dos atributos que o repositório declara.

        O manifesto declara `attributeName`, não id — o catálogo faz a tradução.
        Um nome que não existe no catálogo é ignorado aqui: ele não satisfaz
        requisito nenhum, e o atributo faltante correspondente aparecerá na conta.
        """
        por_nome = {nome: ident for ident, nome in catalogo.items() if nome}
        presentes = set()
        for tag in api_tags or []:
            nome = tag.get("attributeName")
            if nome in por_nome:
                presentes.add(por_nome[nome])
        return presentes
