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
  impedir: daí `api_tag_problems`, que aborta antes de qualquer escrita.
"""

import logging
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from apiops_orchestrator.domain.ports.governance_api_port import GovernanceApiPort

logger = logging.getLogger(__name__)

UNKNOWN_ATTRIBUTE = "unknown_attribute"
ATTRIBUTE_WITHOUT_CATALOG_TAGS = "attribute_without_catalog_tags"
MISSING_TAG = "missing_tag"
INVALID_TAG = "invalid_tag"


@dataclass(frozen=True)
class RequiredAttribute:
    attribute_id: int
    name: Optional[str] = None
    tag_id: Optional[int] = None


@dataclass(frozen=True)
class ApiTagProblem:
    """An `apiTags` entry that does not match the attribute catalog."""

    kind: str
    attribute_name: str
    tag: Optional[str] = None
    valid: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PrecheckResult:
    workflow_id: Optional[int]
    stage_id: Optional[int]
    required: List[RequiredAttribute] = field(default_factory=list)
    missing_names: List[RequiredAttribute] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    api_tag_problems: List[ApiTagProblem] = field(default_factory=list)
    # Stage da revisão como veio do workflow; `None` quando não foi encontrado.
    stage: Optional[Dict[str, Any]] = None
    # False when the Manager has no Adaptive Governance: nothing was evaluated.
    available: bool = True

    @property
    def blocked(self) -> bool:
        return bool(self.missing_names)


@dataclass(frozen=True)
class _Attribute:
    attribute_id: int
    name: Optional[str]
    tags: List[str]


class GovernancePrecheckService:
    def __init__(self, governance_api: GovernanceApiPort):
        self._governance_api = governance_api
        self._attributes: Optional[List[_Attribute]] = None

    def governance_available(self) -> bool:
        """Whether the Manager may have the Adaptive Governance; only a confirmed absence is False."""
        return not self._governance_api.availability().absent

    def evaluate(
        self, revision: Dict[str, Any], api_tags: Optional[Sequence[Dict[str, Any]]]
    ) -> PrecheckResult:
        """Calcula o que falta para o stage da revisão alvo aceitar a publicação.

        As `apiTags` são conferidas contra o catálogo sempre, com ou sem
        requisito no stage. Sem Adaptive Governance, nada é avaliado.
        """
        if not self.governance_available():
            logger.info(
                "governanca.precheck.skipped reason=governance_disabled api_tags_ignored=%d",
                len(api_tags or []),
            )
            return PrecheckResult(None, None, available=False)

        workflow_id = revision.get("workflowId")
        stage_id = revision.get("workflowStageId")
        warnings: List[str] = []
        invalid = self._api_tag_problems(api_tags)

        if workflow_id is None or stage_id is None:
            warnings.append(
                "a revisão alvo não declara `workflowId`/`workflowStageId`; "
                "o Adaptive Governance não pode ser antecipado"
            )
            return PrecheckResult(
                workflow_id, stage_id, warnings=warnings, api_tag_problems=invalid
            )

        workflow = self._governance_api.get_workflow(workflow_id) or {}
        stage = self._find_stage(workflow, stage_id)
        if stage is None:
            # A plataforma já exibiu esse estado uma vez (V-23 §3): a revisão
            # apontava um stage de outro workflow. Degradar com mensagem é
            # melhor do que assumir que não há requisito.
            warnings.append(
                f"o stage {stage_id} não existe no workflow {workflow_id}. O "
                "pré-check não pôde ser calculado, e o veredito virá da própria "
                "publicação."
            )
            return PrecheckResult(
                workflow_id, stage_id, warnings=warnings, api_tag_problems=invalid
            )

        requirements = [
            r for r in (stage.get("attributesRequisites") or []) if r.get("mustHave")
        ]
        if not requirements:
            return PrecheckResult(
                workflow_id,
                stage_id,
                warnings=warnings,
                api_tag_problems=invalid,
                stage=stage,
            )

        catalog = self._catalog()
        required = [
            RequiredAttribute(
                attribute_id=r.get("attributeId"),
                name=catalog.get(r.get("attributeId")),
                tag_id=r.get("tagId"),
            )
            for r in requirements
        ]

        present = self._present(api_tags)
        missing_names = [e for e in required if e.attribute_id not in present]

        logger.info(
            "governanca.precheck workflow=%s stage=%s exigidos=%d faltantes=%d "
            "api_tag_problems=%d",
            workflow_id,
            stage_id,
            len(required),
            len(missing_names),
            len(invalid),
        )
        return PrecheckResult(
            workflow_id, stage_id, required, missing_names, warnings, invalid, stage=stage
        )

    # --- apoio ---------------------------------------------------------------

    @staticmethod
    def _find_stage(
        workflow: Dict[str, Any], stage_id: int
    ) -> Optional[Dict[str, Any]]:
        for stage in workflow.get("stages") or []:
            if stage.get("workflowStageId") == stage_id:
                return stage
        return None

    def _load_attributes(self) -> List[_Attribute]:
        """Catálogo lido uma vez por execução: serve aos requisitos e às tags."""
        if self._attributes is None:
            self._attributes = [
                _Attribute(
                    attribute_id=a.get("id"),
                    name=a.get("name"),
                    tags=[str(t) for t in (a.get("tags") or [])],
                )
                for a in (self._governance_api.list_attributes() or [])
                if a.get("id") is not None
            ]
        return self._attributes

    def _catalog(self) -> Dict[int, str]:
        return {a.attribute_id: a.name for a in self._load_attributes()}

    def _by_name(self) -> Dict[str, _Attribute]:
        return {a.name: a for a in self._load_attributes() if a.name}

    def _api_tag_problems(
        self, api_tags: Optional[Sequence[Dict[str, Any]]]
    ) -> List[ApiTagProblem]:
        """Checks each declared attribute and its tags against the attribute catalog."""
        if not api_tags:
            return []
        by_name = self._by_name()
        problems: List[ApiTagProblem] = []
        for declared in api_tags:
            name = str(declared.get("attributeName") or "")
            tags = [str(t) for t in (declared.get("tags") or [])]
            attribute = by_name.get(name)
            if attribute is None:
                problems.append(
                    ApiTagProblem(
                        UNKNOWN_ATTRIBUTE, name, suggestions=_similar_names(name, by_name)
                    )
                )
            elif not attribute.tags:
                problems.append(ApiTagProblem(ATTRIBUTE_WITHOUT_CATALOG_TAGS, name))
            elif not tags:
                problems.append(ApiTagProblem(MISSING_TAG, name, valid=list(attribute.tags)))
            else:
                problems.extend(
                    ApiTagProblem(INVALID_TAG, name, tag=tag, valid=list(attribute.tags))
                    for tag in tags
                    if tag not in attribute.tags
                )
        return problems

    def _present(self, api_tags: Optional[Sequence[Dict[str, Any]]]) -> set:
        """Ids dos atributos que o repositório declara de forma válida.

        O manifesto declara `attributeName`, não id — o catálogo faz a tradução.
        Um nome que não existe no catálogo é ignorado aqui: ele não satisfaz
        requisito nenhum, e o atributo faltante correspondente aparecerá na conta.
        Atributo com tags cadastradas só conta se declarar ao menos uma tag: com
        `tags: []` a plataforma o trata como ausente (412).
        """
        by_name = self._by_name()
        present = set()
        for declared in api_tags or []:
            attribute = by_name.get(declared.get("attributeName"))
            if attribute is None:
                continue
            if attribute.tags and not (declared.get("tags") or []):
                continue
            present.add(attribute.attribute_id)
        return present


def _fold(text: str) -> str:
    """Returns the text without accents and in lower case."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _similar_names(name: str, catalog_names: Iterable[str]) -> List[str]:
    """Catalog names that differ from `name` only in accents or letter case."""
    folded = _fold(name)
    return sorted(n for n in catalog_names if _fold(n) == folded)
