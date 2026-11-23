"""Leituras de navegação sobre o estado de uma API no Manager.

Lógica pura: recebe o wire cru de `GET /apis/{id}` (que já traz as revisões com
recursos, operações e interceptors inline) e devolve dicts prontos para a saída
`json`/`yaml` da CLI. Não toca disco nem rede.

É a base dos comandos `sen get ...`, pensados para quem explora o ambiente sem
ter o repositório da API localmente — um humano ou um agente de código. Cada
função responde a um nível de detalhe:

    api_summary       identidade, ambientes, revisões (o que existe)
    structure         raiz → recursos → operações, com contagens (a forma)
    scope_flows       o fluxo de interceptors de cada escopo (o comportamento)
    find_interceptor  um item, com o conteúdo inteiro (o detalhe)

A composição do fluxo efetivo reusa `interceptor_flow.composed_flow`: o escopo
executa o que o pai executa, menos o marcado `REMOVED`, mais o próprio (V-28).
"""

import json
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Sequence, Tuple

from apiops_orchestrator.domain.services import repo_layout as layout
from apiops_orchestrator.domain.services.interceptor_flow import (
    composed_flow,
    partition,
    tombstone_target,
)

STATUS_REMOVED = "REMOVED"
ROOT_SCOPE = "all"

# Chaves de `content` exibidas no resumo de uma linha, por tipo. O resto do
# conteúdo só aparece com `--content`/`--item`.
_SUMMARY_LIMIT = 72


# --------------------------------------------------------------------------- util


def decode_content(raw: Any) -> Any:
    """`content` do wire é STRING JSON; devolve o objeto, ou o texto se não for JSON."""
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return raw
    return raw


def _custom_name(item: Dict[str, Any], content: Any) -> Optional[str]:
    if item.get("type") != "Custom":
        return None
    if isinstance(content, dict):
        name = content.get("name")
        return str(name) if name else None
    return None


def summarize_content(item: Dict[str, Any], content: Any) -> str:
    """Resumo de uma linha do conteúdo: o nome do Custom, ou os primeiros pares."""
    if item.get("type") == "Custom":
        name = _custom_name(item, content)
        custom_id = item.get("customInterceptorId")
        head = f"#{custom_id}" if custom_id is not None else ""
        return " ".join(part for part in (head, f'"{name}"' if name else "") if part)
    if isinstance(content, dict):
        pairs = []
        for key, value in content.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            pairs.append(f"{key}={value}")
        text = " ".join(pairs)
    elif content is None:
        return ""
    else:
        text = str(content)
    text = " ".join(text.split())
    if len(text) > _SUMMARY_LIMIT:
        return text[: _SUMMARY_LIMIT - 1] + "…"
    return text


def describe_item(
    item: Dict[str, Any], *, include_content: bool = False
) -> Dict[str, Any]:
    """Interceptor do wire → leitura estável para a saída.

    Sem `include_content`, o `Custom` ainda carrega `customName`: o script é
    longo e só interessa no zoom (`--item`) ou com `--content`.
    """
    content = decode_content(item.get("content"))
    described: Dict[str, Any] = {
        "id": item.get("id"),
        "position": item.get("position"),
        "executionPoint": (item.get("executionPoint") or "").upper() or None,
        "type": item.get("type"),
        "status": item.get("status"),
        "customInterceptorId": item.get("customInterceptorId"),
        "customName": _custom_name(item, content),
        "summary": summarize_content(item, content),
    }
    if include_content:
        described["content"] = content
    return described


def _by_point(items: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    request = [i for i in items if (i.get("executionPoint") or "").upper() == "FIRST"]
    response = [i for i in items if (i.get("executionPoint") or "").upper() == "SECOND"]
    return {"request": request, "response": response}


def _other_points(items: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Itens fora de FIRST/SECOND (ex.: THIRD): não governados, mas existem e executam."""
    _, preserved = partition(items)
    return sorted(preserved, key=lambda i: (str(i.get("executionPoint") or ""), i.get("position") or 0))


def _live(items: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Governados vivos: FIRST/SECOND sem a marcação REMOVED, por `position`."""
    governed, _ = partition(items)
    return sorted(
        (i for i in governed if i.get("status") != STATUS_REMOVED),
        key=lambda i: i.get("position") or 0,
    )


def _tombstones(items: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    governed, _ = partition(items)
    return [i for i in governed if i.get("status") == STATUS_REMOVED]


def _preserved(items: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    _, preserved = partition(items)
    return preserved


def _removals(
    tombstones: Sequence[Dict[str, Any]], inherited: Sequence[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """O que o escopo deixa de herdar, apontando o item do pai quando ele existe."""
    by_id = {i.get("id"): i for i in inherited if i.get("id") is not None}
    removals = []
    for tombstone in tombstones:
        target = tombstone_target(tombstone)
        parent = by_id.get(target)
        removals.append(
            {
                "targetId": target,
                "type": (parent or tombstone).get("type"),
                "executionPoint": ((parent or tombstone).get("executionPoint") or "").upper()
                or None,
                "resolved": parent is not None,
            }
        )
    return removals


# --------------------------------------------------------------------------- revisão


def revision_number(revision: Dict[str, Any]) -> Optional[int]:
    try:
        return int(revision.get("revisionNumber"))
    except (TypeError, ValueError):
        return None


def available_revision_numbers(api: Dict[str, Any]) -> List[int]:
    numbers = {
        n for n in (revision_number(r) for r in api.get("revisions") or []) if n is not None
    }
    return sorted(numbers)


def select_revision(
    api: Dict[str, Any],
    number: Optional[int] = None,
    revision_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Revisão pelo NÚMERO (o que a UI mostra) ou pelo id; sem os dois, a corrente.

    Devolve `None` quando não há revisão que case — quem chamou decide a
    mensagem, porque só ele sabe listar as disponíveis.
    """
    revisions = [r for r in api.get("revisions") or [] if isinstance(r, dict)]
    if revision_id is not None:
        return next((r for r in revisions if r.get("id") == revision_id), None)
    if number is not None:
        return next((r for r in revisions if revision_number(r) == number), None)
    last = api.get("lastRevision")
    if isinstance(last, dict) and last.get("id") is not None:
        inline = next((r for r in revisions if r.get("id") == last.get("id")), None)
        return inline or last
    if revisions:
        return max(revisions, key=lambda r: revision_number(r) or 0)
    return None


def _count_operations(revision: Dict[str, Any]) -> int:
    return sum(len(r.get("operations") or []) for r in revision.get("resources") or [])


def _deployed_environments(api: Dict[str, Any]) -> Dict[int, List[str]]:
    """revisionId → nomes dos ambientes onde ela está no ar, lidos de `environments[]`."""
    deployed: Dict[int, List[str]] = {}
    for env in api.get("environments") or []:
        if not isinstance(env, dict):
            continue
        live = env.get("revisionDeployed")
        if isinstance(live, dict) and live.get("revisionId") is not None:
            deployed.setdefault(int(live["revisionId"]), []).append(str(env.get("name")))
    return deployed


def revision_header(api: Dict[str, Any], revision: Dict[str, Any]) -> Dict[str, Any]:
    """Cabeçalho comum das leituras de uma revisão."""
    deployed = _deployed_environments(api)
    return {
        "id": revision.get("id"),
        "number": revision_number(revision),
        "lifeCycle": revision.get("lifeCycle"),
        "workflowId": revision.get("workflowId"),
        "workflowStageId": revision.get("workflowStageId"),
        "deployedIn": deployed.get(revision.get("id"), []),
    }


def api_header(api: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": api.get("id"),
        "name": api.get("name"),
        "version": api.get("version"),
        "basePath": api.get("basePath"),
    }


# --------------------------------------------------------------------------- nível 1


def api_summary(api: Dict[str, Any]) -> Dict[str, Any]:
    """Identidade, visibilidade, ambientes e a lista de revisões com contagens."""
    visibility = api.get("visibility") if isinstance(api.get("visibility"), dict) else {}
    group = visibility.get("groupVisibility") or {}
    responsible = api.get("apiResponsible") or {}
    deployed = _deployed_environments(api)
    last = api.get("lastRevision") if isinstance(api.get("lastRevision"), dict) else {}

    revisions = []
    for revision in sorted(
        (r for r in api.get("revisions") or [] if isinstance(r, dict)),
        key=lambda r: revision_number(r) or 0,
    ):
        root_live = _live(revision.get("interceptors"))
        revisions.append(
            {
                "number": revision_number(revision),
                "id": revision.get("id"),
                "lifeCycle": revision.get("lifeCycle"),
                "workflowId": revision.get("workflowId"),
                "workflowStageId": revision.get("workflowStageId"),
                "creationDate": revision.get("creationDate"),
                "resources": len(revision.get("resources") or []),
                "operations": _count_operations(revision),
                "rootInterceptors": len(root_live),
                "deployedIn": deployed.get(revision.get("id"), []),
                "current": revision.get("id") == last.get("id"),
            }
        )

    environments = []
    for env in api.get("environments") or []:
        if not isinstance(env, dict):
            continue
        live = env.get("revisionDeployed") if isinstance(env.get("revisionDeployed"), dict) else None
        environments.append(
            {
                "id": env.get("id"),
                "name": env.get("name"),
                "inboundUrl": env.get("inboundUrl"),
                "deployedRevision": (
                    {"number": live.get("revisionNumber"), "id": live.get("revisionId")}
                    if live
                    else None
                ),
            }
        )

    return {
        **api_header(api),
        "description": api.get("description"),
        "apiType": api.get("apiType"),
        "privateAPI": api.get("privateAPI"),
        "identityApi": api.get("identityApi"),
        "creationDate": api.get("creationDate"),
        "visibility": {
            "type": visibility.get("visibilityType"),
            "owner": visibility.get("owner"),
            "groupName": group.get("name") if isinstance(group, dict) else None,
            "users": [
                u.get("username") if isinstance(u, dict) else u
                for u in visibility.get("users") or []
            ],
        },
        "responsible": {
            "username": responsible.get("username"),
            "groupName": responsible.get("groupName"),
        },
        "apiTags": [
            {"attributeName": t.get("attributeName"), "tags": list(t.get("tags") or [])}
            for t in api.get("apiTags") or []
            if isinstance(t, dict)
        ],
        "plans": [p.get("name") for p in api.get("plans") or [] if isinstance(p, dict)],
        "lastRevisionNumber": revision_number(last) if last else None,
        "environments": environments,
        "revisions": revisions,
    }


# --------------------------------------------------------------------------- escopos


@dataclass(frozen=True)
class Scope:
    """Um ponto da árvore (raiz, recurso ou operação) e os seus fluxos."""

    kind: str  # root | resource | operation
    key: str  # "all" | "<slug-do-recurso>" | "<METODO> <path>"
    label: str
    raw: Dict[str, Any]
    own: List[Dict[str, Any]]
    removals: List[Dict[str, Any]]
    preserved: int
    effective: List[Dict[str, Any]]
    inherited_count: int
    resource_key: Optional[str] = None
    children: List["Scope"] = field(default_factory=list)

    @property
    def inherits(self) -> Optional[bool]:
        """`None` na raiz (não herda de ninguém); `False` quando marca remoções."""
        if self.kind == "root":
            return None
        return not self.removals


def _scope(
    kind: str,
    key: str,
    label: str,
    raw: Dict[str, Any],
    inherited: Sequence[Dict[str, Any]],
    resource_key: Optional[str] = None,
) -> Scope:
    items = raw.get("interceptors")
    own = _live(items)
    effective = composed_flow(items, inherited) if kind != "root" else composed_flow(items)
    return Scope(
        kind=kind,
        key=key,
        label=label,
        raw=raw,
        own=own,
        removals=_removals(_tombstones(items), inherited),
        preserved=len(_preserved(items)),
        effective=effective,
        inherited_count=len(inherited),
        resource_key=resource_key,
    )


def operation_key(operation: Dict[str, Any]) -> str:
    return f"{(operation.get('method') or '').upper()} {operation.get('path') or ''}".strip()


def scope_tree(revision: Dict[str, Any]) -> Scope:
    """Raiz → recursos → operações, cada um com o próprio e o efetivo já compostos."""
    root = _scope("root", ROOT_SCOPE, ROOT_SCOPE, revision, [])
    resources = [r for r in revision.get("resources") or [] if isinstance(r, dict)]
    children: List[Scope] = []
    for resource in resources:
        key = layout.folder_name(resource, resources)
        scope = _scope(
            "resource", key, str(resource.get("name") or key), resource, root.effective
        )
        operations: List[Scope] = []
        for operation in resource.get("operations") or []:
            if not isinstance(operation, dict):
                continue
            operations.append(
                _scope(
                    "operation",
                    operation_key(operation),
                    operation_key(operation),
                    operation,
                    scope.effective,
                    resource_key=key,
                )
            )
        children.append(replace(scope, children=operations))
    return replace(root, children=children)


def iter_scopes(tree: Scope):
    yield tree
    for child in tree.children:
        yield from iter_scopes(child)


def _matches_resource(scope: Scope, selector: str) -> bool:
    wanted = selector.strip()
    if not wanted:
        return False
    raw = scope.raw
    if wanted.isdigit() and raw.get("id") == int(wanted):
        return True
    if wanted == scope.key:
        return True
    name = str(raw.get("name") or "")
    return name.lower() == wanted.lower() or layout.slug(name) == layout.slug(wanted)


def _matches_operation(scope: Scope, selector: str) -> bool:
    wanted = " ".join(selector.split()).strip()
    if not wanted:
        return False
    raw = scope.raw
    if wanted.isdigit() and raw.get("id") == int(wanted):
        return True
    parts = wanted.split(" ", 1)
    if len(parts) == 2:
        method, path = parts[0].upper(), parts[1].strip()
        return (
            (raw.get("method") or "").upper() == method
            and (raw.get("path") or "").rstrip("/") == path.rstrip("/")
        )
    # Só o path: casa qualquer método naquela rota.
    return (raw.get("path") or "").rstrip("/") == wanted.rstrip("/")


def select_scopes(
    tree: Scope,
    resource: Optional[str] = None,
    operation: Optional[str] = None,
) -> List[Scope]:
    """Recorte da árvore pelo seletor.

    * nada            → todos os escopos, em ordem de árvore;
    * `resource`      → o recurso e as suas operações;
    * `operation`     → só a operação (dentro do recurso, se ele veio junto).

    Lista vazia significa seletor sem correspondência.
    """
    if resource is None and operation is None:
        return list(iter_scopes(tree))

    resources = [s for s in tree.children if s.kind == "resource"]
    if resource is not None:
        resources = [s for s in resources if _matches_resource(s, resource)]
        if operation is None:
            return [s for r in resources for s in iter_scopes(r)]

    assert operation is not None
    return [
        op
        for r in resources
        for op in r.children
        if op.kind == "operation" and _matches_operation(op, operation)
    ]


# --------------------------------------------------------------------------- nível 2


def _destination(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {"url": raw.get("destination") or None, "timeout": raw.get("timeout") or None}


def _counts(scope: Scope) -> Dict[str, int]:
    return {
        "own": len(scope.own),
        "removes": len(scope.removals),
        "inherited": scope.inherited_count,
        "effective": len(scope.effective),
        "preserved": scope.preserved,
    }


def structure(api: Dict[str, Any], revision: Dict[str, Any]) -> Dict[str, Any]:
    """Raiz, recursos e operações com destino, timeout e contagens de interceptors."""
    tree = scope_tree(revision)
    resources = []
    for resource in tree.children:
        resources.append(
            {
                "id": resource.raw.get("id"),
                "name": resource.raw.get("name"),
                "slug": resource.key,
                "description": resource.raw.get("description") or None,
                "destination": _destination(resource.raw),
                "inherits": resource.inherits,
                "interceptors": _counts(resource),
                "operations": [
                    {
                        "id": op.raw.get("id"),
                        "method": (op.raw.get("method") or "").upper(),
                        "path": op.raw.get("path"),
                        "description": op.raw.get("description") or None,
                        "destination": _destination(op.raw),
                        "inherits": op.inherits,
                        "interceptors": _counts(op),
                    }
                    for op in resource.children
                ],
            }
        )
    return {
        "api": api_header(api),
        "revision": revision_header(api, revision),
        "root": {
            "scope": ROOT_SCOPE,
            "destination": _destination(revision),
            "interceptors": _counts(tree),
        },
        "resources": resources,
        "totals": {
            "resources": len(resources),
            "operations": sum(len(r["operations"]) for r in resources),
        },
    }


# --------------------------------------------------------------------------- nível 3


def describe_scope(
    scope: Scope, *, effective: bool = False, include_content: bool = False
) -> Dict[str, Any]:
    document: Dict[str, Any] = {
        "scope": scope.key,
        "kind": scope.kind,
        "label": scope.label,
        "id": scope.raw.get("id"),
        "destination": _destination(scope.raw),
        "inherits": scope.inherits,
        "counts": _counts(scope),
        "removes": list(scope.removals),
        "own": {
            point: [describe_item(i, include_content=include_content) for i in items]
            for point, items in _by_point(scope.own).items()
        },
    }
    document["other"] = [
        describe_item(i, include_content=include_content) for i in _other_points(scope.raw.get("interceptors"))
    ]
    if scope.resource_key is not None:
        document["resource"] = scope.resource_key
    if effective:
        document["effective"] = {
            point: [describe_item(i, include_content=include_content) for i in items]
            for point, items in _by_point(scope.effective).items()
        }
    return document


def scope_flows(
    api: Dict[str, Any],
    revision: Dict[str, Any],
    *,
    resource: Optional[str] = None,
    operation: Optional[str] = None,
    effective: bool = False,
    include_content: bool = False,
    point: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Fluxos de interceptors dos escopos selecionados; `None` se o seletor não casa.

    `point` (FIRST/SECOND/THIRD ou request/response/third) deixa só esse ponto
    de execução em cada escopo; os outros pontos saem vazios.
    """
    tree = scope_tree(revision)
    scopes = select_scopes(tree, resource=resource, operation=operation)
    if not scopes:
        return None
    wanted = normalize_point(point)
    documents = [describe_scope(s, effective=effective, include_content=include_content) for s in scopes]
    if wanted is not None:
        for document in documents:
            for bucket in ("own", "effective"):
                if bucket in document:
                    for key in list(document[bucket]):
                        if _POINT_OF_BUCKET[key] != wanted:
                            document[bucket][key] = []
            document["other"] = [i for i in document["other"] if i.get("executionPoint") == wanted]
            document["removes"] = [r for r in document["removes"] if r.get("executionPoint") == wanted]
    return {
        "api": api_header(api),
        "revision": revision_header(api, revision),
        "mode": "effective" if effective else "own",
        "point": wanted,
        "scopes": documents,
    }


_POINT_ALIASES = {
    "FIRST": "FIRST", "REQUEST": "FIRST", "1": "FIRST",
    "SECOND": "SECOND", "RESPONSE": "SECOND", "2": "SECOND",
    "THIRD": "THIRD", "3": "THIRD",
}
_POINT_OF_BUCKET = {"request": "FIRST", "response": "SECOND"}


def normalize_point(point: Optional[str]) -> Optional[str]:
    """`request`/`FIRST`/`1` → FIRST; `response`/`SECOND`/`2` → SECOND; `third`/`3` → THIRD."""
    if point is None or not str(point).strip():
        return None
    key = str(point).strip().upper()
    if key not in _POINT_ALIASES:
        raise ValueError(f"ponto de execução desconhecido: {point!r} (use FIRST, SECOND ou THIRD)")
    return _POINT_ALIASES[key]


# --------------------------------------------------------------------------- nível 4


def find_interceptor(
    revision: Dict[str, Any], item_id: int
) -> Optional[Tuple[Scope, Dict[str, Any]]]:
    """Localiza um interceptor pelo `id` do Manager em qualquer escopo da revisão."""
    for scope in iter_scopes(scope_tree(revision)):
        for item in scope.raw.get("interceptors") or []:
            if isinstance(item, dict) and item.get("id") == item_id:
                return scope, item
    return None


def describe_interceptor(
    api: Dict[str, Any], revision: Dict[str, Any], scope: Scope, item: Dict[str, Any]
) -> Dict[str, Any]:
    described = describe_item(item, include_content=True)
    described.pop("summary", None)
    from apiops_orchestrator.domain.services.interceptor_types import check_fields

    reference = check_fields(item.get("type"), described.get("content"))
    return {
        "api": api_header(api),
        "revision": revision_header(api, revision),
        "scope": {
            "scope": scope.key,
            "kind": scope.kind,
            "label": scope.label,
            "id": scope.raw.get("id"),
            "resource": scope.resource_key,
        },
        "interceptor": {
            **described,
            "parentType": item.get("parentType"),
            "parentId": tombstone_target(item) if item.get("status") == STATUS_REMOVED else None,
            "governed": layout.is_governed(item.get("executionPoint")),
        },
        "reference": reference,
    }
