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

Regras de `apiTags` observadas na plataforma:

* atributo declarado com `tags: []`, quando o catálogo cadastra tags para ele,
  conta como **ausente** — a plataforma respondeu 412 "API must contain
  attribute My new";
* tag que não existe na lista do atributo é **aceita com 200 e apaga todas as
  `apiTags` da API**, sem erro e sem a governança barrar. Só o pré-check pode
  impedir: daí `tags_invalidas`, que aborta antes de qualquer escrita.
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
class TagInvalida:
    """Tag declarada em `apiTags` que não existe na lista do atributo no catálogo."""

    attribute_name: str
    tag: str
    validas: List[str]


@dataclass(frozen=True)
class PrecheckResultado:
    workflow_id: Optional[int]
    stage_id: Optional[int]
    exigidos: List[AtributoExigido] = field(default_factory=list)
    faltantes: List[AtributoExigido] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)
    tags_invalidas: List[TagInvalida] = field(default_factory=list)

    @property
    def bloqueado(self) -> bool:
        return bool(self.faltantes)


@dataclass(frozen=True)
class _Atributo:
    attribute_id: int
    name: Optional[str]
    tags: List[str]


class GovernancePrecheckService:
    def __init__(self, manager_api: ManagerApiPort):
        self._manager_api = manager_api
        self._atributos: Optional[List[_Atributo]] = None

    def avaliar(
        self, revisao: Dict[str, Any], api_tags: Optional[Sequence[Dict[str, Any]]]
    ) -> PrecheckResultado:
        """Calcula o que falta para o stage da revisão alvo aceitar a publicação.

        As tags inválidas são conferidas sempre, com ou sem requisito no stage:
        a perda de `apiTags` acontece em qualquer workflow.
        """
        workflow_id = revisao.get("workflowId")
        stage_id = revisao.get("workflowStageId")
        avisos: List[str] = []
        invalidas = self._tags_invalidas(api_tags)

        if workflow_id is None or stage_id is None:
            avisos.append(
                "a revisão alvo não declara `workflowId`/`workflowStageId`; "
                "o Adaptive Governance não pode ser antecipado"
            )
            return PrecheckResultado(
                workflow_id, stage_id, avisos=avisos, tags_invalidas=invalidas
            )

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
            return PrecheckResultado(
                workflow_id, stage_id, avisos=avisos, tags_invalidas=invalidas
            )

        requisitos = [
            r for r in (stage.get("attributesRequisites") or []) if r.get("mustHave")
        ]
        if not requisitos:
            return PrecheckResultado(
                workflow_id, stage_id, avisos=avisos, tags_invalidas=invalidas
            )

        catalogo = self._catalogo()
        exigidos = [
            AtributoExigido(
                attribute_id=r.get("attributeId"),
                name=catalogo.get(r.get("attributeId")),
                tag_id=r.get("tagId"),
            )
            for r in requisitos
        ]

        presentes = self._presentes(api_tags)
        faltantes = [e for e in exigidos if e.attribute_id not in presentes]

        logger.info(
            "governanca.precheck workflow=%s stage=%s exigidos=%d faltantes=%d "
            "tags_invalidas=%d",
            workflow_id,
            stage_id,
            len(exigidos),
            len(faltantes),
            len(invalidas),
        )
        return PrecheckResultado(
            workflow_id, stage_id, exigidos, faltantes, avisos, invalidas
        )

    # --- apoio ---------------------------------------------------------------

    @staticmethod
    def _encontrar_stage(
        workflow: Dict[str, Any], stage_id: int
    ) -> Optional[Dict[str, Any]]:
        for stage in workflow.get("stages") or []:
            if stage.get("workflowStageId") == stage_id:
                return stage
        return None

    def _carregar_atributos(self) -> List[_Atributo]:
        """Catálogo lido uma vez por execução: serve aos requisitos e às tags."""
        if self._atributos is None:
            self._atributos = [
                _Atributo(
                    attribute_id=a.get("id"),
                    name=a.get("name"),
                    tags=[str(t) for t in (a.get("tags") or [])],
                )
                for a in (self._manager_api.list_attributes() or [])
                if a.get("id") is not None
            ]
        return self._atributos

    def _catalogo(self) -> Dict[int, str]:
        return {a.attribute_id: a.name for a in self._carregar_atributos()}

    def _por_nome(self) -> Dict[str, _Atributo]:
        return {a.name: a for a in self._carregar_atributos() if a.name}

    def _tags_invalidas(
        self, api_tags: Optional[Sequence[Dict[str, Any]]]
    ) -> List[TagInvalida]:
        """Tags declaradas que não existem na lista do atributo no catálogo.

        Só confere atributos que o catálogo conhece **e** para os quais cadastra
        tags: sem lista cadastrada não há contra o que comparar (comportamento da
        plataforma nesse caso não foi medido).
        """
        if not api_tags:
            return []
        por_nome = self._por_nome()
        invalidas: List[TagInvalida] = []
        for declarado in api_tags:
            atributo = por_nome.get(declarado.get("attributeName"))
            if atributo is None or not atributo.tags:
                continue
            for tag in declarado.get("tags") or []:
                if str(tag) not in atributo.tags:
                    invalidas.append(
                        TagInvalida(str(atributo.name), str(tag), list(atributo.tags))
                    )
        return invalidas

    def _presentes(self, api_tags: Optional[Sequence[Dict[str, Any]]]) -> set:
        """Ids dos atributos que o repositório declara de forma válida.

        O manifesto declara `attributeName`, não id — o catálogo faz a tradução.
        Um nome que não existe no catálogo é ignorado aqui: ele não satisfaz
        requisito nenhum, e o atributo faltante correspondente aparecerá na conta.
        Atributo com tags cadastradas só conta se declarar ao menos uma tag: com
        `tags: []` a plataforma o trata como ausente (412).
        """
        por_nome = self._por_nome()
        presentes = set()
        for declarado in api_tags or []:
            atributo = por_nome.get(declarado.get("attributeName"))
            if atributo is None:
                continue
            if atributo.tags and not (declarado.get("tags") or []):
                continue
            presentes.add(atributo.attribute_id)
        return presentes
