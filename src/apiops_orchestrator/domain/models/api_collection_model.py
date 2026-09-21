from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from apiops_orchestrator.infrastructure.utils.text_normalizer import accent_fold


class ApiCollectionError(ValueError):
    """Erro de regra de colecao (traduzido pela CLI para msg humana)."""


class InvalidWindowError(ApiCollectionError):
    """Janela de paginacao invalida (ex.: --limit <= 0)."""


class InsufficientSessionError(ApiCollectionError):
    """Sessao de usuario insuficiente para aplicar visibilidade (bloqueio)."""


QUERY_FIELDS = ("name", "description")


def _matches_query(item: Dict[str, Any], folded_query: str) -> bool:
    if not folded_query:
        return True
    return any(
        folded_query in accent_fold(item.get(field_name))
        for field_name in QUERY_FIELDS
    )


def _fold_stripped(value: Any) -> str:
    """Normaliza p/ comparacao de visibilidade: trim + casefold + sem acentos."""
    return accent_fold(value).strip()


def last_revision_number(item: Dict[str, Any]) -> Optional[int]:
    """Regra: numero da ultima revisao de uma API (dict cru da port).

    Ordem de fonte: `lastRevision` dedicado; fallback para a ultima entrada
    de `revisions`; None quando o payload nao traz (degrada para '-' na CLI).
    """
    last_revision = item.get("lastRevision") or {}
    if isinstance(last_revision, dict) and last_revision.get("revisionNumber"):
        return last_revision["revisionNumber"]
    revisions = item.get("revisions") or []
    if revisions and isinstance(revisions[-1], dict):
        revision_number = revisions[-1].get("revisionNumber")
        if revision_number:
            return revision_number
    return None


def life_cycle_of(item: Dict[str, Any]) -> Optional[str]:
    """Regra: ciclo de vida declarado da API; None quando ausente."""
    value = item.get("lifeCycle")
    return str(value) if value else None


def revision_basic_map(rows: List[Dict[str, Any]]) -> Dict[Any, int]:
    """Regra: mapa {apiId -> maior revisionNumber} a partir de /revisions/basic.

    Cada linha tem {id, api {id, revisionNumber, ...}, workflowId, ...};
    ha N linhas por api, vale a de maior revisionNumber.
    """
    mapping: Dict[Any, int] = {}
    for row in rows or []:
        api = row.get("api") or {}
        api_id = api.get("id")
        revision = api.get("revisionNumber") or 0
        if api_id is None:
            continue
        mapping[api_id] = max(mapping.get(api_id, 0), revision)
    return mapping


def attach_last_revision(
    items: List[Dict[str, Any]], revision_map: Dict[Any, int]
) -> List[Dict[str, Any]]:
    """Anexa `lastRevision` derivado ao item sem mutar o original.

    Nunca SOBRESCREVE um lastRevision real do payload (fonte prioritaria).
    """
    enriched = []
    for item in items or []:
        if (item.get("lastRevision") or {}).get("revisionNumber"):
            enriched.append(item)
            continue
        revision = revision_map.get(item.get("id"))
        if not revision:
            enriched.append(item)
            continue
        decorated = dict(item)
        decorated["lastRevision"] = {"revisionNumber": revision}
        enriched.append(decorated)
    return enriched


def _sort_key(item: Dict[str, Any]):
    raw_id = item.get("id")
    if isinstance(raw_id, int):
        return (0, raw_id)
    if isinstance(raw_id, str):
        try:
            return (0, int(raw_id))
        except ValueError:
            return (1, 0)
    return (1, 0)


@dataclass(frozen=True)
class ApiCollection:
    """Comportamento sobre uma colecao de APIs (dicts crus da port).

    Referencia as chaves do contrato ApiPartialInfo (id, name, description...)
    sem replicar o shape nem parsar pydantic nesta fatia. Imutavel: cada
    metodo devolve uma nova colecao.
    """

    items: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw_items: Optional[List[Dict[str, Any]]]) -> "ApiCollection":
        return cls(items=list(raw_items or []))

    def filtered_by(self, query: Optional[str]) -> "ApiCollection":
        if not query:
            return self
        folded_query = accent_fold(query)
        return ApiCollection(
            items=[item for item in self.items if _matches_query(item, folded_query)]
        )

    def visible_to(
        self,
        username: Optional[str],
        groups: Optional[List[str]],
        super_admin: bool = False,
    ) -> "ApiCollection":
        """Filtro de visibilidade client-side sobre dicts crus da port.

        Regras (tabela da spec do change add-sen-list):
          - super_admin: mantem tudo
          - ORGANIZATION: mantem
          - ME: mantem somente se owner casa com username
          - GROUP: mantem SOMENTE se groupVisibility.name casa com algum
            grupo da sessao (owner NAO influi na regra GROUP)
          - tipo ausente/desconhecido: descarta (deny-by-default)

        Compara com trim + casefold + accent-fold em ambos os lados.
        """
        if super_admin:
            return self
        folded_username = _fold_stripped(username)
        folded_groups = {_fold_stripped(group) for group in (groups or [])}
        kept = []
        for item in self.items:
            visibility = item.get("visibility") or {}
            visibility_type = _fold_stripped(visibility.get("visibilityType"))
            if visibility_type == "organization":
                kept.append(item)
                continue
            if visibility_type == "me":
                if folded_username and _fold_stripped(visibility.get("owner")) == folded_username:
                    kept.append(item)
                continue
            if visibility_type == "group":
                group_name = _fold_stripped(
                    (visibility.get("groupVisibility") or {}).get("name")
                )
                if group_name and group_name in folded_groups:
                    kept.append(item)
        return ApiCollection(items=kept)

    def sorted_by_id(self) -> "ApiCollection":
        return ApiCollection(items=sorted(self.items, key=_sort_key))

    def window(
        self, offset: Optional[int] = None, limit: Optional[int] = None
    ) -> "ApiCollection":
        start = 0
        if offset is not None:
            if int(offset) < 0:
                raise InvalidWindowError(
                    "--offset deve ser maior ou igual a zero."
                )
            start = int(offset)
        if limit is not None:
            if int(limit) <= 0:
                raise InvalidWindowError("--limit deve ser maior que zero.")
            return ApiCollection(items=self.items[start : start + int(limit)])
        if start > 0:
            return ApiCollection(items=self.items[start:])
        return self

    def rows(self) -> List[Dict[str, Any]]:
        return list(self.items)

    def __len__(self) -> int:
        return len(self.items)
