"""Revision flow as swagger extensions, and the swagger aligned to it.

Pure logic. The swagger write rebuilds the revision flow from the document `x-*`.
The Manager does not always carry into the swagger what the revision write
changed, so the document to write is compared with the flow read after that write
and, when they differ, aligned to it.
"""

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from apiops_orchestrator.domain.services.openapi_contract import (
    HTTP_METHODS,
    Route,
    document_operations,
    route_label,
)

# Swagger name of the flow types that do not follow the upper-case rule (measured on the 425).
TYPE_NAMES = {
    "Digital signature": "APIKEY_DIGITAL_SIGNATURE",
    "JWT validation": "JWT",
    "Time token validation": "TIMETOKEN_VALIDATION",
    "Time token generator": "TIMETOKEN_GENERATOR",
    "XSLT": "XSL_TRANSFORMATION",
    "GZip pack": "GZIPPACK",
    "GZip unpack": "GZIPUNPACK",
    "Java": "CUSTOM_JAVA",
}
ROOT_EXTENSIONS = ("x-destination", "x-api-broken", "x-interceptors")
RESOURCE_EXTENSIONS = ("x-resource-description", "x-destination", "x-timeout", "x-api-broken", "x-interceptors")
OPERATION_EXTENSIONS = ("x-resource-name", "x-destination", "x-timeout", "x-api-broken", "x-interceptors")
# Flow fields the swagger has no extension for.
UNCARRIED_FIELDS = ("certificateId", "connector", "async", "urls", "instruction")
_LABELS = {
    "x-interceptors": "interceptors",
    "x-destination": "destino",
    "x-timeout": "timeout",
    "x-api-broken": "x-api-broken",
    "x-resource-name": "recurso",
    "x-resource-description": "descrição",
    "description": "descrição",
}


def swagger_type(flow_type: Optional[str]) -> str:
    """Swagger name of a flow interceptor type."""
    return TYPE_NAMES.get(flow_type or "") or (flow_type or "").upper().replace(" ", "_")


@dataclass(frozen=True)
class FlowExtensions:
    """The `x-*` the flow gives the root, each resource and each operation, and the operation descriptions."""

    root: Dict[str, Any] = field(default_factory=dict)
    resources: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    operations: Dict[Route, Dict[str, Any]] = field(default_factory=dict)
    descriptions: Dict[Route, Optional[str]] = field(default_factory=dict)


class _Keys:
    """Local keys numbered over the whole document, by flow interceptor id."""

    def __init__(self) -> None:
        self.next = 1
        self.by_flow_id: Dict[Any, str] = {}

    def take(self, flow_id: Any) -> str:
        key = str(self.next)
        self.next += 1
        self.by_flow_id[flow_id] = key
        return key


def _timeout(value: Any) -> Any:
    return int(value) if isinstance(value, str) and value.isdigit() else value


def _interceptors(items: Any, keys: _Keys) -> Dict[str, Any]:
    found: Dict[str, Any] = {}
    ordered = sorted(
        (i for i in items or [] if isinstance(i, dict)),
        key=lambda i: (i.get("position") or 0, i.get("id") or 0),
    )
    for item in ordered:
        entry = {
            "x-interceptor-position": item.get("position"),
            "x-interceptor-type": swagger_type(item.get("type")),
            "x-interceptor-content": item.get("content"),
            "x-interceptor-execution-point": item.get("executionPoint"),
        }
        if item.get("status") is not None:
            entry["x-interceptor-status"] = item["status"]
        if item.get("customInterceptorId") is not None:
            entry["x-interceptor-custom-interceptor-id"] = item["customInterceptorId"]
        parent = (item.get("parent") or {}).get("id")
        if parent is not None:
            # A parent sits in an upper scope, already numbered; one outside the
            # revision has no key, and `unsupported` stops the alignment.
            key = keys.by_flow_id.get(parent)
            entry["x-interceptor-parent-id"] = int(key) if key is not None else None
        found[keys.take(item.get("id"))] = entry
    return found


def flow_extensions(revision: Dict[str, Any]) -> FlowExtensions:
    """The flow of the revision as swagger extensions, keys numbered root first, then each resource and its operations."""
    keys = _Keys()
    root = {
        "x-destination": revision.get("destination"),
        "x-api-broken": revision.get("apiBroken"),
        "x-interceptors": _interceptors(revision.get("interceptors"), keys),
    }
    resources: Dict[str, Dict[str, Any]] = {}
    operations: Dict[Route, Dict[str, Any]] = {}
    descriptions: Dict[Route, Optional[str]] = {}
    for resource in revision.get("resources") or []:
        name = resource.get("name")
        resources[name] = {
            "x-resource-description": resource.get("description") or None,
            "x-destination": resource.get("destination"),
            "x-timeout": _timeout(resource.get("timeout")),
            "x-api-broken": resource.get("apiBroken"),
            "x-interceptors": _interceptors(resource.get("interceptors"), keys),
        }
        for operation in resource.get("operations") or []:
            route = (str(operation.get("method") or "").upper(), operation.get("path"))
            operations[route] = {
                "x-resource-name": name,
                "x-destination": operation.get("destination"),
                "x-timeout": _timeout(operation.get("timeout")),
                "x-api-broken": operation.get("apiBroken"),
                "x-interceptors": _interceptors(operation.get("interceptors"), keys),
            }
            descriptions[route] = operation.get("description") or None
    return FlowExtensions(root=root, resources=resources, operations=operations, descriptions=descriptions)


def unsupported(revision: Dict[str, Any]) -> List[str]:
    """What in the flow the swagger cannot carry, so the document cannot be aligned to it."""
    found: List[str] = []
    ids = {i.get("id") for i in _all_interceptors(revision)}
    for item in _all_interceptors(revision):
        parent = (item.get("parent") or {}).get("id")
        if parent is not None and parent not in ids:
            found.append(f"interceptor {item.get('type')} com o pai fora da revisão")
    for resource in revision.get("resources") or []:
        found += _uncarried(f"recurso {resource.get('name')}", resource)
        for operation in resource.get("operations") or []:
            label = route_label((str(operation.get("method") or "").upper(), operation.get("path")))
            found += _uncarried(label, operation)
    return found


def _uncarried(label: str, scope: Dict[str, Any]) -> List[str]:
    return [f"{label}: {name}" for name in UNCARRIED_FIELDS if scope.get(name) not in (None, False, [], "")]


def _all_interceptors(revision: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = list(revision.get("interceptors") or [])
    for resource in revision.get("resources") or []:
        items += resource.get("interceptors") or []
        for operation in resource.get("operations") or []:
            items += operation.get("interceptors") or []
    return [i for i in items if isinstance(i, dict)]


# --- comparison -----------------------------------------------------------------


def _document_items(document: Dict[str, Any]) -> Dict[str, Any]:
    items = dict(document.get("x-interceptors") or {})
    for resource in (document.get("x-resources") or {}).values():
        if isinstance(resource, dict):
            items.update(resource.get("x-interceptors") or {})
    for _, operation in document_operations(document):
        items.update(operation.get("x-interceptors") or {})
    return items


def _comparable(scope: Dict[str, Any], names: tuple, items: Dict[str, Any]) -> Dict[str, Any]:
    """The extensions without local keys, the parent as its fields, and absent, null and defaults alike."""
    found: Dict[str, Any] = {}
    for name in names:
        value = scope.get(name)
        if value in (None, "", {}) or (name == "x-api-broken" and value is False):
            continue
        if name == "x-timeout":
            value = str(value)
        if name == "x-interceptors":
            entries = []
            for item in value.values() if isinstance(value, dict) else []:
                entry = {k: v for k, v in item.items() if k != "x-interceptor-parent-id"}
                parent = item.get("x-interceptor-parent-id")
                if parent is not None:
                    target = items.get(str(parent))
                    entry["parent"] = (
                        [target.get("x-interceptor-position"), target.get("x-interceptor-type"),
                         target.get("x-interceptor-content")]
                        if isinstance(target, dict)
                        else f"chave {parent} inexistente"
                    )
                entries.append(json.dumps(entry, sort_keys=True, default=str))
            value = sorted(entries)
        found[name] = value
    return found


def _changed(label: str, a: Dict[str, Any], b: Dict[str, Any]) -> List[str]:
    names = [_LABELS.get(k, k) for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    return [f"{label}: {', '.join(dict.fromkeys(names))}"] if names else []


def differences(document: Dict[str, Any], revision: Dict[str, Any]) -> List[str]:
    """Where the swagger does not describe the flow: routes and resources missing or extra, and changed extensions."""
    flow = flow_extensions(revision)
    flow_items = _document_items(_aligned_extensions_only(flow))
    document_items = _document_items(document)
    found: List[str] = []

    found += _changed(
        "raiz",
        _comparable(flow.root, ROOT_EXTENSIONS, flow_items),
        _comparable(document, ROOT_EXTENSIONS, document_items),
    )

    current_resources = document.get("x-resources") or {}
    for name, extensions in flow.resources.items():
        current = current_resources.get(name)
        if not isinstance(current, dict):
            found.append(f"recurso {name}: criado")
            continue
        found += _changed(
            f"recurso {name}",
            _comparable(extensions, RESOURCE_EXTENSIONS, flow_items),
            _comparable(current, RESOURCE_EXTENSIONS, document_items),
        )
    found += [f"recurso {name}: tirado" for name in current_resources if name not in flow.resources]

    current_operations = dict(document_operations(document))
    for route, extensions in flow.operations.items():
        label = route_label(route)
        current = current_operations.get(route)
        if current is None:
            found.append(f"{label}: criada")
            continue
        mine = _comparable(extensions, OPERATION_EXTENSIONS, flow_items)
        theirs = _comparable(current, OPERATION_EXTENSIONS, document_items)
        mine["description"] = flow.descriptions.get(route)
        theirs["description"] = current.get("description") or None
        found += _changed(label, mine, theirs)
    found += [f"{route_label(r)}: tirada" for r in current_operations if r not in flow.operations]
    return found


def _aligned_extensions_only(flow: FlowExtensions) -> Dict[str, Any]:
    """A document holding only the flow extensions, to resolve parent keys."""
    paths: Dict[str, Any] = {}
    for (method, path), extensions in flow.operations.items():
        paths.setdefault(path, {})[method.lower()] = extensions
    return {**flow.root, "x-resources": flow.resources, "paths": paths}


# --- alignment ------------------------------------------------------------------


def _put(target: Dict[str, Any], name: str, value: Any) -> None:
    if value is None:
        target.pop(name, None)
    else:
        target[name] = copy.deepcopy(value)


def align(document: Dict[str, Any], revision: Dict[str, Any]) -> Dict[str, Any]:
    """The document with every flow extension, route and resource taken from the flow.

    A route the swagger lacks is created with the flow description only; the
    contract fields come from the repository afterwards.
    """
    flow = flow_extensions(revision)
    aligned = copy.deepcopy(document)
    for name in ROOT_EXTENSIONS:
        _put(aligned, name, flow.root.get(name))

    current_resources = aligned.get("x-resources") or {}
    resources: Dict[str, Any] = {}
    for name, extensions in flow.resources.items():
        current = current_resources.get(name)
        resource = {
            k: v for k, v in (current if isinstance(current, dict) else {}).items() if k not in RESOURCE_EXTENSIONS
        }
        for key in RESOURCE_EXTENSIONS:
            _put(resource, key, extensions.get(key))
        resources[name] = resource
    aligned["x-resources"] = resources

    paths = aligned.setdefault("paths", {})
    for path, item in list(paths.items()):
        if not isinstance(item, dict):
            continue
        for method in HTTP_METHODS:
            if isinstance(item.get(method), dict) and (method.upper(), path) not in flow.operations:
                del item[method]
        if not any(isinstance(item.get(m), dict) for m in HTTP_METHODS):
            del paths[path]
    for (method, path), extensions in flow.operations.items():
        item = paths.setdefault(path, {})
        operation = item.setdefault(method.lower(), {})
        _put(operation, "description", flow.descriptions.get((method, path)))
        for key in OPERATION_EXTENSIONS:
            _put(operation, key, extensions.get(key))
    return aligned
