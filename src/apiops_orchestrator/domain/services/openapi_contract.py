"""OpenAPI contract: extraction from the repository, merge into the revision swagger and comparison.

Pure logic. The written document starts from the swagger the Manager returns and
only the fields the repository governs are replaced; everything else is kept.
"""

import copy
import datetime
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

GOVERNED_SECTIONS = (
    "schemas",
    "securitySchemes",
    "responses",
    "requestBodies",
    "headers",
    "examples",
)
ROOT_FIELDS = ("contact", "tags", "security")
OPERATION_FIELDS = (
    "operationId",
    "summary",
    "tags",
    "security",
    "parameters",
    "requestBody",
    "responses",
)
HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
# Extensions that carry the runtime flow, not the documentation.
FLOW_EXTENSIONS = frozenset({"x-interceptors", "x-destination", "x-timeout"})

Route = Tuple[str, Optional[str]]


@dataclass(frozen=True)
class RepositoryContract:
    """Contract declared in the repository, already normalized."""

    root: Dict[str, Any] = field(default_factory=dict)
    components: Dict[str, Any] = field(default_factory=dict)
    operations: Dict[Route, Dict[str, Any]] = field(default_factory=dict)


def normalize_yaml(value: Any) -> Any:
    """Turns YAML dates into ISO text and numeric keys into text."""
    if isinstance(value, dict):
        return {
            (str(k) if isinstance(k, (int, float)) and not isinstance(k, bool) else k): normalize_yaml(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [normalize_yaml(v) for v in value]
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def parameter_key(parameter: Any) -> Optional[Tuple[Any, Any]]:
    """`(name, in)` of a parameter."""
    if not isinstance(parameter, dict):
        return None
    return (parameter.get("name"), parameter.get("in"))


def merge_parameters(
    resource_parameters: Sequence[Any], operation_parameters: Sequence[Any]
) -> List[Any]:
    """Resource parameters followed by the operation ones; on the same `name`+`in`, the operation wins."""
    own = {parameter_key(p) for p in operation_parameters}
    inherited = [p for p in resource_parameters if parameter_key(p) not in own]
    return copy.deepcopy(inherited) + copy.deepcopy(list(operation_parameters))


def extract_contract(
    *,
    basic_info: Dict[str, Any],
    components: Dict[str, Any],
    resources: Sequence[Any],
) -> RepositoryContract:
    """Contract declared in the repository, with the resource parameters in each operation."""
    spec = (basic_info or {}).get("spec") or {}
    root = {f: normalize_yaml(spec[f]) for f in ROOT_FIELDS if spec.get(f) is not None}

    governed = {
        section: normalize_yaml(value)
        for section, value in (components or {}).items()
        if section in GOVERNED_SECTIONS and value is not None
    }

    operations: Dict[Route, Dict[str, Any]] = {}
    for resource in resources:
        resource_parameters = normalize_yaml((resource.data or {}).get("parameters") or [])
        for operation in resource.operations:
            data = operation.data or {}
            fields = {
                f: normalize_yaml(data[f]) for f in OPERATION_FIELDS if data.get(f) is not None
            }
            fields["parameters"] = merge_parameters(
                resource_parameters, fields.get("parameters") or []
            )
            if not fields.get("summary") and data.get("description"):
                fields["summary"] = data["description"]
            operations[(str(operation.method or "").upper(), data.get("path"))] = fields

    return RepositoryContract(root=root, components=governed, operations=operations)


def is_swagger_2(document: Dict[str, Any]) -> bool:
    """The document is in Swagger 2.0."""
    return "openapi" not in document and str(document.get("swagger", "")).startswith("2")


def document_operations(document: Dict[str, Any]) -> Iterator[Tuple[Route, Dict[str, Any]]]:
    """Each operation of the document, with its `(METHOD, path)` route."""
    for path, item in (document.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method in HTTP_METHODS:
            operation = item.get(method)
            if isinstance(operation, dict):
                yield (method.upper(), path), operation


def route_label(route: Route) -> str:
    return f"{route[0]} {route[1]}"


def missing_routes(document: Dict[str, Any], contract: RepositoryContract) -> List[str]:
    """Repository routes the document does not have."""
    in_document = {route for route, _ in document_operations(document)}
    return sorted(route_label(r) for r in contract.operations if r not in in_document)


def _replace(target: Dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        target.pop(key, None)
    else:
        target[key] = copy.deepcopy(value)


def apply_contract(current: Dict[str, Any], contract: RepositoryContract) -> Dict[str, Any]:
    """Swagger to write: the current one with the governed fields replaced by the repository ones.

    Operations outside the repository are dropped, and so is a path left without operations.
    """
    document = copy.deepcopy(current)

    _replace(document.setdefault("info", {}), "contact", contract.root.get("contact"))
    for key in ("tags", "security"):
        _replace(document, key, contract.root.get(key))

    components = document.get("components")
    components = components if isinstance(components, dict) else {}
    for section in GOVERNED_SECTIONS:
        _replace(components, section, contract.components.get(section))
    if components or "components" in document:
        document["components"] = components

    paths = document.get("paths") or {}
    for path, item in list(paths.items()):
        if not isinstance(item, dict):
            continue
        path_parameters = item.pop("parameters", None)
        dropped = False
        for method in HTTP_METHODS:
            operation = item.get(method)
            if not isinstance(operation, dict):
                continue
            fields = contract.operations.get((method.upper(), path))
            if fields is None:
                # The flow write already removed it, but the Manager may keep it in
                # the swagger, and writing it back would put it in the flow again.
                del item[method]
                dropped = True
                continue
            current_parameters = operation.get("parameters")
            for name in OPERATION_FIELDS:
                _replace(operation, name, fields.get(name))
            _keep_parameter_extensions(operation, current_parameters, path_parameters)
        if dropped and not any(isinstance(item.get(m), dict) for m in HTTP_METHODS):
            del paths[path]

    return document


def _keep_parameter_extensions(operation: Dict[str, Any], *current: Any) -> None:
    """Copies into each repository parameter the `x-*` of the current one with the same `name`+`in`."""
    extensions: Dict[Tuple[Any, Any], Dict[str, Any]] = {}
    for parameters in current:
        for parameter in parameters if isinstance(parameters, list) else []:
            if not isinstance(parameter, dict) or parameter.get("name") is None:
                continue
            found = {k: v for k, v in parameter.items() if isinstance(k, str) and k.startswith("x-")}
            if found:
                extensions.setdefault(parameter_key(parameter), found)
    for parameter in operation.get("parameters") or []:
        if isinstance(parameter, dict):
            for name, value in extensions.get(parameter_key(parameter), {}).items():
                parameter.setdefault(name, copy.deepcopy(value))


def removed_items(current: Dict[str, Any], contract: RepositoryContract) -> List[str]:
    """Items the current document has in the governed fields and the repository does not declare."""
    items: List[str] = []

    if (current.get("info") or {}).get("contact") and "contact" not in contract.root:
        items.append("info.contact")
    for key in ("tags", "security"):
        if current.get(key) and key not in contract.root:
            items.append(key)

    components = current.get("components") or {}
    for section in GOVERNED_SECTIONS:
        declared = contract.components.get(section) or {}
        for name in components.get(section) or {}:
            if name not in declared:
                items.append(f"components.{section}.{name}")

    # A path-item parameter moves into each operation on write: it only leaves a
    # repository route that does not declare it. A route only in the Manager is
    # removed by the flow write, which already warns about it.
    for path, item in (current.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        shared = [p for p in item.get("parameters") or [] if isinstance(p, dict) and "$ref" not in p]
        for route, fields in contract.operations.items():
            if route[1] != path:
                continue
            declared = {parameter_key(p) for p in fields.get("parameters") or []}
            for parameter in shared:
                if parameter_key(parameter) not in declared:
                    items.append(
                        f"{route_label(route)} · parâmetro {parameter.get('name')} ({parameter.get('in')})"
                    )

    for route, operation in document_operations(current):
        fields = contract.operations.get(route)
        if fields is None:
            continue
        label = route_label(route)
        for name in ("operationId", "tags", "security", "requestBody"):
            if name in operation and name not in fields:
                items.append(f"{label} · {name}")
        declared_responses = fields.get("responses") or {}
        for status in operation.get("responses") or {}:
            if str(status) not in declared_responses:
                items.append(f"{label} · resposta {status}")
        declared_parameters = {parameter_key(p) for p in fields.get("parameters") or []}
        for parameter in operation.get("parameters") or []:
            if isinstance(parameter, dict) and "$ref" not in parameter:
                if parameter_key(parameter) not in declared_parameters:
                    items.append(
                        f"{label} · parâmetro {parameter.get('name')} ({parameter.get('in')})"
                    )
    # The same parameter may sit both in the path item and in the operation.
    return list(dict.fromkeys(items))


# --- comparison --------------------------------------------------------------


def _resolve_parameter(parameter: Any, reusable: Dict[str, Any]) -> Any:
    ref = parameter.get("$ref") if isinstance(parameter, dict) else None
    if isinstance(ref, str) and ref.startswith("#/components/parameters/"):
        target = reusable.get(ref.rsplit("/", 1)[-1])
        if isinstance(target, dict):
            return copy.deepcopy(target)
    return parameter


def _without_defaults(obj: Any, default_style: str) -> Any:
    """Drops from a parameter or header the fields equal to the OpenAPI default."""
    if not isinstance(obj, dict) or "$ref" in obj:
        return obj
    if obj.get("style") == default_style:
        obj.pop("style")
    style = obj.get("style", default_style)
    if obj.get("explode") == (style == "form"):
        obj.pop("explode")
    if obj.get("required") is False:
        obj.pop("required")
    return obj


def _default_style(parameter: Any) -> str:
    location = parameter.get("in") if isinstance(parameter, dict) else None
    return "form" if location in ("query", "cookie") else "simple"


def _sort_required(node: Any) -> None:
    if isinstance(node, dict):
        if isinstance(node.get("required"), list):
            node["required"] = sorted(node["required"], key=str)
        for value in node.values():
            _sort_required(value)
    elif isinstance(node, list):
        for value in node:
            _sort_required(value)


def normalize_for_comparison(document: Dict[str, Any]) -> Dict[str, Any]:
    """Document without OpenAPI defaults, with sorted `required` and resolved parameter `$ref`."""
    copied = copy.deepcopy(document)
    components = copied.get("components") if isinstance(copied.get("components"), dict) else {}
    reusable = components.get("parameters") or {}

    def parameters(values: Any) -> Any:
        if not isinstance(values, list):
            return values
        resolved = [_resolve_parameter(p, reusable) for p in values]
        return [_without_defaults(p, _default_style(p)) for p in resolved]

    def headers(mapping: Any) -> None:
        for name, header in (mapping or {}).items():
            mapping[name] = _without_defaults(header, "simple")

    for item in (copied.get("paths") or {}).values():
        if isinstance(item, dict) and "parameters" in item:
            item["parameters"] = parameters(item["parameters"])
    for _, operation in document_operations(copied):
        if "parameters" in operation:
            operation["parameters"] = parameters(operation["parameters"])
        for response in (operation.get("responses") or {}).values():
            if isinstance(response, dict):
                headers(response.get("headers"))
    for name, parameter in reusable.items():
        reusable[name] = _without_defaults(parameter, _default_style(parameter))
    headers(components.get("headers"))
    for response in (components.get("responses") or {}).values():
        if isinstance(response, dict):
            headers(response.get("headers"))

    _sort_required(copied)
    return copied


def same_document(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Both documents are the same once normalized."""
    return normalize_for_comparison(a) == normalize_for_comparison(b)


def _without_flow(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _without_flow(v) for k, v in node.items() if k not in FLOW_EXTENSIONS}
    if isinstance(node, list):
        return [_without_flow(v) for v in node]
    return node


def same_documentation(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Both documents describe the API the same way; the flow extensions do not count."""
    return same_document(_without_flow(a), _without_flow(b))


def _extensions(node: Any, path: str = "") -> Dict[str, Any]:
    """Each `x-*` of the document by its path; `x-interceptors` without the local keys."""
    found: Dict[str, Any] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            where = f"{path}.{key}" if path else str(key)
            if isinstance(key, str) and key.startswith("x-"):
                found[where] = _without_local_keys(value) if key == "x-interceptors" else value
            else:
                found.update(_extensions(value, where))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found.update(_extensions(value, f"{path}[{i}]"))
    return found


def _without_local_keys(interceptors: Any) -> Any:
    if not isinstance(interceptors, dict):
        return interceptors
    items = []
    for item in interceptors.values():
        if isinstance(item, dict):
            item = {k: v for k, v in item.items() if k != "x-interceptor-parent-id"}
        items.append(json.dumps(item, sort_keys=True, default=str))
    return sorted(items)


def _short(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return text if len(text) <= 200 else text[:197] + "..."


def verify_contract(sent: Dict[str, Any], written: Dict[str, Any]) -> List[str]:
    """Differences between the sent and the written swagger: contract and extensions."""
    s = normalize_for_comparison(sent)
    w = normalize_for_comparison(written)
    differences: List[str] = []

    def compare(label: str, a: Any, b: Any) -> None:
        if a != b:
            differences.append(f"{label}: enviado {_short(a)}, gravado {_short(b)}")

    compare("info.contact", (s.get("info") or {}).get("contact"), (w.get("info") or {}).get("contact"))
    for key in ("tags", "security"):
        compare(key, s.get(key), w.get(key))
    for section in GOVERNED_SECTIONS:
        compare(
            f"components.{section}",
            (s.get("components") or {}).get(section),
            (w.get("components") or {}).get(section),
        )

    written_operations = dict(document_operations(w))
    for route, operation in document_operations(s):
        label = route_label(route)
        written_operation = written_operations.get(route)
        if written_operation is None:
            differences.append(f"{label}: a rota enviada não está no swagger gravado")
            continue
        for name in OPERATION_FIELDS:
            compare(f"{label} · {name}", operation.get(name), written_operation.get(name))

    sent_extensions, written_extensions = _extensions(s), _extensions(w)
    for key in sorted(set(sent_extensions) | set(written_extensions)):
        if sent_extensions.get(key) != written_extensions.get(key):
            differences.append(f"a extensão `{key}` mudou ao gravar")
    return differences
