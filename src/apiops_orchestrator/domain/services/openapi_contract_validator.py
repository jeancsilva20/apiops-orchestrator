"""Local validation of the OpenAPI contract declared in the repository (Swagger validate).

Pure logic, no network. Returns the errors, which block the write, and the
warnings, which do not.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Sequence

from apiops_orchestrator.domain.services.openapi_contract import (
    GOVERNED_SECTIONS,
    OPERATION_FIELDS,
    ROOT_FIELDS,
    normalize_yaml,
)
from apiops_orchestrator.domain.services.repo_layout import (
    BASIC_INFO_FILE,
    COMPONENTS_FILE,
)

COMPONENTS_YML_FILE = "components.yml"
PARAMETER_LOCATIONS = ("path", "query", "header", "cookie")
METHODS_WITH_BODY = frozenset({"POST", "PUT", "PATCH"})
SECTIONS_WITH_CYCLES = ("responses", "requestBodies", "headers", "examples")

_STATUS = re.compile(r"[1-5]\d\d|[1-5]XX|default")
_TEMPLATE = re.compile(r"\{([^{}/]+)\}")
_REF = re.compile(r"#/components/([^/]+)/([^/]+)")
_FORMATS = {
    "date": re.compile(r"\d{4}-\d{2}-\d{2}"),
    "date-time": re.compile(
        r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?([Zz]|[+-]\d{2}:?\d{2})?"
    ),
    "uuid": re.compile(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    ),
}
_BOUNDS = {"int32": (-(2**31), 2**31 - 1), "int64": (-(2**63), 2**63 - 1)}

# Minimum description lengths the Manager completeness asks for.
MIN_SUMMARY = 5
MIN_RESPONSE = 5
MIN_PARAMETER = 5
MIN_PROPERTY = 9
MIN_SCHEMA = 10

# Maps whose keys are names, not fields: an `x-` key there is not an extension.
_NAME_MAPS = frozenset({
    "properties", "patternProperties", "headers", "content", "responses", "examples",
    "schemas", "requestBodies", "securitySchemes", "encoding", "mapping", "scopes",
})
_FREE_VALUES = frozenset({"example", "default", "enum", "value", "const"})

_EXTENSION_PROBLEM = "extensões `x-*` são do Manager e não entram no repositório"


@dataclass(frozen=True)
class ValidationResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class _Validation:
    def __init__(self, components: Dict[str, Any]):
        self.components = components
        self.errors: List[str] = []
        self.short_descriptions: List[str] = []

    def error(self, file: str, position: Optional[str], problem: str) -> None:
        where = f"`{file}`" + (f", em `{position}`" if position else "")
        self.errors.append(f"{where}: {problem}")


def validate(
    *,
    basic_info: Dict[str, Any],
    components: Any,
    resources: Sequence[Any],
    ignored: Sequence[str] = (),
) -> ValidationResult:
    """Validates the contract of the whole repository."""
    basic_info = normalize_yaml(basic_info or {})
    declared = normalize_yaml(components or {})
    v = _Validation(declared if isinstance(declared, dict) else {})

    if not isinstance(declared, dict):
        v.error(COMPONENTS_FILE, None, "o arquivo precisa ser um mapa de seções")
    _out_of_model(v, basic_info, ignored)
    _components(v)

    spec = basic_info.get("spec") or {}
    _security(v, BASIC_INFO_FILE, "spec.security", spec.get("security"))

    operation_ids: Dict[str, List[str]] = {}
    for resource in resources:
        resource_data = normalize_yaml(resource.data or {})
        _file_extensions(v, resource.file_path, resource_data, ("parameters",))
        resource_parameters = resource_data.get("parameters") or []
        _parameter_list(v, resource.file_path, resource_parameters)
        operations = [(op, normalize_yaml(op.data or {})) for op in resource.operations]
        _resource_parameters(
            v, resource.file_path, resource_parameters, [d.get("path") or "" for _, d in operations]
        )
        for operation, data in operations:
            _operation(v, operation, data, resource_parameters, operation_ids)

    for operation_id, files in operation_ids.items():
        if len(files) > 1:
            v.error(
                files[0],
                "operationId",
                f"o `operationId` `{operation_id}` se repete em "
                + ", ".join(f"`{f}`" for f in files[1:])
                + "; ele precisa ser único na API",
            )

    warnings = [_descriptions_warning(v.short_descriptions)] if v.short_descriptions else []
    return ValidationResult(errors=v.errors, warnings=warnings)


# --- outside the model --------------------------------------------------------


def _extensions(node: Any, path: str = "", name_map: bool = False) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            where = f"{path}.{key}" if path else str(key)
            if not name_map and isinstance(key, str) and key.startswith("x-"):
                yield where
                continue
            if not name_map and key in _FREE_VALUES:
                continue
            yield from _extensions(value, where, name_map=not name_map and key in _NAME_MAPS)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _extensions(value, f"{path}[{i}]")


def _file_extensions(v: _Validation, file: str, data: Dict[str, Any], fields: Sequence[str]) -> None:
    for key in data:
        if isinstance(key, str) and key.startswith("x-"):
            v.error(file, key, _EXTENSION_PROBLEM)
    for name in fields:
        for where in _extensions(data.get(name), name):
            v.error(file, where, _EXTENSION_PROBLEM)


def _out_of_model(v: _Validation, basic_info: Dict[str, Any], ignored: Sequence[str]) -> None:
    if COMPONENTS_YML_FILE in ignored:
        v.error(
            COMPONENTS_YML_FILE,
            None,
            f"o arquivo de componentes se chama `{COMPONENTS_FILE}`; renomeie-o",
        )

    spec = basic_info.get("spec") or {}
    for name in ("servers", "info"):
        if name in spec:
            v.error(
                BASIC_INFO_FILE,
                f"spec.{name}",
                f"`{name}` não é declarado no repositório: vem do Manager",
            )
    _file_extensions(v, BASIC_INFO_FILE, basic_info, ())
    _file_extensions(v, BASIC_INFO_FILE, spec, ROOT_FIELDS)

    for section in v.components:
        if section == "parameters":
            v.error(
                COMPONENTS_FILE,
                section,
                "parâmetros não são reutilizados por referência: escreva cada um por "
                "extenso no arquivo da rota ou no `resource.yaml`",
            )
        elif section not in GOVERNED_SECTIONS:
            v.error(
                COMPONENTS_FILE,
                section,
                "seção fora do modelo; as aceitas são "
                + ", ".join(f"`{s}`" for s in GOVERNED_SECTIONS),
            )
    for where in _extensions(v.components):
        v.error(COMPONENTS_FILE, where, _EXTENSION_PROBLEM)


# --- references ---------------------------------------------------------------


def _ref(v: _Validation, file: str, position: str, ref: Any, expected_section: str) -> Optional[Any]:
    """Checks a `$ref` and returns the component it points to."""
    if not isinstance(ref, str):
        v.error(file, position, "`$ref` precisa ser um texto")
        return None
    if ref.startswith("#/definitions/"):
        v.error(
            file,
            position,
            f"`{ref}` está no formato do Swagger 2.0; use `#/components/{expected_section}/...`",
        )
        return None
    matched = _REF.fullmatch(ref)
    if matched is None:
        v.error(
            file,
            position,
            f"`{ref}` não é aceito: a referência aponta para "
            f"`#/components/{expected_section}/<nome>`, no `{COMPONENTS_FILE}`",
        )
        return None
    section, name = matched.groups()
    if section != expected_section:
        v.error(
            file,
            position,
            f"aqui só cabe referência a `#/components/{expected_section}/`, "
            f"e `{ref}` aponta para `{section}`",
        )
        return None
    target = (v.components.get(section) or {}).get(name)
    if target is None:
        v.error(file, position, f"`{ref}` não existe no `{COMPONENTS_FILE}`")
    return target


def _resolve_schema(v: _Validation, schema: Any) -> Optional[Dict[str, Any]]:
    seen = set()
    while isinstance(schema, dict) and isinstance(schema.get("$ref"), str):
        ref = schema["$ref"]
        matched = _REF.fullmatch(ref)
        if ref in seen or matched is None or matched.group(1) != "schemas":
            return None
        seen.add(ref)
        schema = (v.components.get("schemas") or {}).get(matched.group(2))
    return schema if isinstance(schema, dict) else None


def _cycles(v: _Validation) -> None:
    for section in SECTIONS_WITH_CYCLES:
        entries = v.components.get(section) or {}
        for name in entries:
            chain = [name]
            current = entries.get(name)
            while isinstance(current, dict) and isinstance(current.get("$ref"), str):
                matched = _REF.fullmatch(current["$ref"])
                if matched is None or matched.group(1) != section:
                    break
                following = matched.group(2)
                if following in chain:
                    v.error(
                        COMPONENTS_FILE,
                        f"{section}.{name}",
                        "as referências formam um ciclo: " + " → ".join(chain + [following]),
                    )
                    break
                chain.append(following)
                current = entries.get(following)


# --- types and examples -------------------------------------------------------


def _matches_type(value: Any, kind: Any) -> bool:
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "array":
        return isinstance(value, list)
    if kind == "object":
        return isinstance(value, dict)
    return True


def _value_problem(value: Any, schema: Dict[str, Any]) -> Optional[str]:
    if value is None and schema.get("nullable"):
        return None
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        return f"o valor {value!r} não está no `enum` {enum}"
    kind = schema.get("type")
    if kind and not _matches_type(value, kind):
        return f"o valor {value!r} não é do tipo `{kind}`"
    fmt = schema.get("format")
    if isinstance(value, str) and fmt in _FORMATS and not _FORMATS[fmt].fullmatch(value):
        return f"o valor {value!r} não está no formato `{fmt}`"
    if fmt in _BOUNDS and isinstance(value, int) and not isinstance(value, bool):
        low, high = _BOUNDS[fmt]
        if not low <= value <= high:
            return f"o valor {value!r} não cabe em `{fmt}`"
    return None


def _check_value(v: _Validation, file: str, position: str, value: Any, schema: Any) -> None:
    target = _resolve_schema(v, schema)
    if target is None:
        return
    problem = _value_problem(value, target)
    if problem:
        v.error(file, position, problem)


def _schema(v: _Validation, file: str, position: str, schema: Any) -> None:
    if not isinstance(schema, dict):
        return
    if "$ref" in schema:
        _ref(v, file, position, schema["$ref"], "schemas")
        return
    kind, enum = schema.get("type"), schema.get("enum")
    if kind and isinstance(enum, list):
        for value in enum:
            if not _matches_type(value, kind):
                v.error(file, f"{position}.enum", f"o valor {value!r} não é do tipo `{kind}`")
    for key in ("example", "default"):
        if key in schema:
            _check_value(v, file, f"{position}.{key}", schema[key], schema)
    for name, prop in (schema.get("properties") or {}).items():
        _schema(v, file, f"{position}.properties.{name}", prop)
    for key in ("items", "additionalProperties", "not"):
        if isinstance(schema.get(key), dict):
            _schema(v, file, f"{position}.{key}", schema[key])
    for key in ("allOf", "anyOf", "oneOf"):
        for i, part in enumerate(schema.get(key) or []):
            _schema(v, file, f"{position}.{key}[{i}]", part)


def _example(v: _Validation, file: str, position: str, example: Any, schema: Any) -> None:
    if not isinstance(example, dict):
        return
    if "$ref" in example:
        example = _ref(v, file, position, example["$ref"], "examples")
    if isinstance(example, dict) and "value" in example and schema is not None:
        _check_value(v, file, f"{position}.value", example["value"], schema)


def _media(v: _Validation, file: str, position: str, media: Any) -> None:
    if not isinstance(media, dict):
        return
    schema = media.get("schema")
    _schema(v, file, f"{position}.schema", schema)
    if "example" in media and schema is not None:
        _check_value(v, file, f"{position}.example", media["example"], schema)
    for name, example in (media.get("examples") or {}).items():
        _example(v, file, f"{position}.examples.{name}", example, schema)


def _header(v: _Validation, file: str, position: str, header: Any) -> None:
    if not isinstance(header, dict):
        return
    if "$ref" in header:
        _ref(v, file, position, header["$ref"], "headers")
        return
    _schema(v, file, f"{position}.schema", header.get("schema"))
    if "example" in header and header.get("schema") is not None:
        _check_value(v, file, f"{position}.example", header["example"], header["schema"])


def _response(v: _Validation, file: str, position: str, response: Any) -> None:
    if not isinstance(response, dict):
        v.error(file, position, "a resposta precisa ser um mapa com `description`")
        return
    if "$ref" in response:
        _ref(v, file, position, response["$ref"], "responses")
        return
    description = response.get("description")
    if not isinstance(description, str):
        v.error(file, position, "toda resposta precisa de `description`")
    elif len(description.strip()) < MIN_RESPONSE:
        v.short_descriptions.append(f"{file} · {position}")
    for name, header in (response.get("headers") or {}).items():
        _header(v, file, f"{position}.headers.{name}", header)
    for media_type, media in (response.get("content") or {}).items():
        _media(v, file, f"{position}.content.{media_type}", media)


def _request_body(v: _Validation, file: str, position: str, body: Any) -> None:
    if not isinstance(body, dict):
        return
    if "$ref" in body:
        _ref(v, file, position, body["$ref"], "requestBodies")
        return
    for media_type, media in (body.get("content") or {}).items():
        _media(v, file, f"{position}.content.{media_type}", media)


def _security(v: _Validation, file: str, position: str, requirements: Any) -> None:
    if requirements is None:
        return
    if not isinstance(requirements, list):
        v.error(file, position, "`security` precisa ser uma lista")
        return
    schemes = v.components.get("securitySchemes") or {}
    for requirement in requirements:
        for name in requirement if isinstance(requirement, dict) else ():
            if name not in schemes:
                v.error(
                    file,
                    position,
                    f"o esquema `{name}` não está em `securitySchemes`, no `{COMPONENTS_FILE}`",
                )


# --- components ---------------------------------------------------------------


def _components(v: _Validation) -> None:
    for name, schema in (v.components.get("schemas") or {}).items():
        _schema(v, COMPONENTS_FILE, f"schemas.{name}", schema)
        _schema_descriptions(v, name, schema)
    for name, response in (v.components.get("responses") or {}).items():
        _response(v, COMPONENTS_FILE, f"responses.{name}", response)
    for name, body in (v.components.get("requestBodies") or {}).items():
        _request_body(v, COMPONENTS_FILE, f"requestBodies.{name}", body)
    for name, header in (v.components.get("headers") or {}).items():
        _header(v, COMPONENTS_FILE, f"headers.{name}", header)
    for name, example in (v.components.get("examples") or {}).items():
        if isinstance(example, dict) and "$ref" in example:
            _ref(v, COMPONENTS_FILE, f"examples.{name}", example["$ref"], "examples")
    for name, scheme in (v.components.get("securitySchemes") or {}).items():
        if isinstance(scheme, dict) and "$ref" in scheme:
            _ref(v, COMPONENTS_FILE, f"securitySchemes.{name}", scheme["$ref"], "securitySchemes")
        elif not isinstance(scheme, dict) or not scheme.get("type"):
            v.error(COMPONENTS_FILE, f"securitySchemes.{name}", "o esquema precisa de `type`")
    _cycles(v)


def _schema_descriptions(v: _Validation, name: str, schema: Any) -> None:
    if not isinstance(schema, dict) or "$ref" in schema:
        return
    if len(str(schema.get("description") or "").strip()) < MIN_SCHEMA:
        v.short_descriptions.append(f"{COMPONENTS_FILE} · schemas.{name}")
    if "properties" not in schema:
        note = (
            " (o completeness acusa schema com `enum` declarado à parte; para não "
            "perder nota, declare o `enum` onde ele é usado)"
            if "enum" in schema
            else ""
        )
        v.short_descriptions.append(f"{COMPONENTS_FILE} · schemas.{name} sem propriedades{note}")
    for prop_name, prop in (schema.get("properties") or {}).items():
        if isinstance(prop, dict) and "$ref" not in prop:
            if len(str(prop.get("description") or "").strip()) < MIN_PROPERTY:
                v.short_descriptions.append(
                    f"{COMPONENTS_FILE} · schemas.{name}.properties.{prop_name}"
                )


# --- parameters and operations ------------------------------------------------


def _parameter_list(v: _Validation, file: str, parameters: Any) -> None:
    if not isinstance(parameters, list):
        v.error(file, "parameters", "`parameters` precisa ser uma lista")
        return
    seen = set()
    for i, parameter in enumerate(parameters):
        if not isinstance(parameter, dict):
            v.error(file, f"parameters[{i}]", "o parâmetro precisa ser um mapa")
            continue
        if "$ref" in parameter:
            v.error(file, f"parameters[{i}]", "parâmetro não usa `$ref`: escreva-o por extenso")
            continue
        name, location = parameter.get("name"), parameter.get("in")
        if not name or location not in PARAMETER_LOCATIONS:
            v.error(
                file,
                f"parameters[{i}]",
                "todo parâmetro precisa de `name` e de `in` (path, query, header ou cookie)",
            )
            continue
        position = f"parameters.{name} ({location})"
        if (name, location) in seen:
            v.error(file, position, "o parâmetro está repetido no arquivo")
        seen.add((name, location))
        if location == "path" and parameter.get("required") is not True:
            v.error(file, position, "parâmetro de path precisa de `required: true`")
        schema = parameter.get("schema")
        _schema(v, file, f"{position}.schema", schema)
        if "example" in parameter and schema is not None:
            _check_value(v, file, f"{position}.example", parameter["example"], schema)
        for example_name, example in (parameter.get("examples") or {}).items():
            _example(v, file, f"{position}.examples.{example_name}", example, schema)
        for media_type, media in (parameter.get("content") or {}).items():
            _media(v, file, f"{position}.content.{media_type}", media)
        if len(str(parameter.get("description") or "").strip()) < MIN_PARAMETER:
            v.short_descriptions.append(f"{file} · {position}")


def _resource_parameters(v: _Validation, file: str, parameters: Any, paths: Sequence[str]) -> None:
    for parameter in parameters if isinstance(parameters, list) else ():
        if not isinstance(parameter, dict) or parameter.get("in") != "path":
            continue
        name = parameter.get("name")
        without_it = [p for p in paths if name not in _TEMPLATE.findall(p)]
        if without_it:
            v.error(
                file,
                f"parameters.{name} (path)",
                f"o parâmetro de path `{name}` não existe em "
                + ", ".join(f"`{p}`" for p in without_it)
                + "; o `resource.yaml` só leva o que vale para todas as rotas do "
                "recurso — declare-o no arquivo de cada rota que o usa",
            )


def _operation(
    v: _Validation,
    operation: Any,
    data: Dict[str, Any],
    resource_parameters: Any,
    operation_ids: Dict[str, List[str]],
) -> None:
    file = operation.file_path
    method = str(operation.method or "").upper()
    path = data.get("path") or ""
    _file_extensions(v, file, data, OPERATION_FIELDS)

    own = data.get("parameters") or []
    _parameter_list(v, file, own)
    template = set(_TEMPLATE.findall(path))
    every = [
        p
        for p in list(resource_parameters if isinstance(resource_parameters, list) else [])
        + list(own if isinstance(own, list) else [])
        if isinstance(p, dict)
    ]
    path_names = {p.get("name") for p in every if p.get("in") == "path"}
    for name in sorted(template - path_names):
        v.error(
            file,
            "parameters",
            f"a rota `{path}` tem `{{{name}}}`, mas nenhum parâmetro `{name}` em `path` "
            "foi declarado, nem no `resource.yaml`",
        )
    for parameter in own if isinstance(own, list) else ():
        if isinstance(parameter, dict) and parameter.get("in") == "path":
            if parameter.get("name") not in template:
                v.error(
                    file,
                    f"parameters.{parameter.get('name')} (path)",
                    f"`{parameter.get('name')}` não existe na rota `{path}`",
                )

    if data.get("operationId"):
        operation_ids.setdefault(str(data["operationId"]), []).append(file)

    if "requestBody" in data:
        if method not in METHODS_WITH_BODY:
            v.error(
                file,
                "requestBody",
                f"`requestBody` só vale em POST, PUT e PATCH; esta rota é {method}",
            )
        else:
            _request_body(v, file, "requestBody", data["requestBody"])

    responses = data.get("responses")
    if not responses:
        v.error(
            file,
            None,
            "a rota não declara `responses`. Toda rota precisa de pelo menos uma "
            "resposta; rota sem documentação declara `responses: {'200': {description: OK}}`",
        )
    elif not isinstance(responses, dict):
        v.error(file, "responses", "`responses` precisa ser um mapa de status")
    else:
        for status, response in responses.items():
            if not _STATUS.fullmatch(str(status)):
                v.error(
                    file,
                    f"responses.{status}",
                    "status inválido: use três dígitos, `1XX` a `5XX` ou `default`",
                )
            _response(v, file, f"responses.{status}", response)

    _security(v, file, "security", data.get("security"))

    summary = data.get("summary") or data.get("description") or ""
    if len(str(summary).strip()) < MIN_SUMMARY:
        v.short_descriptions.append(f"{file} · summary")


def _descriptions_warning(short: Sequence[str]) -> str:
    return (
        "Estas descrições do contrato estão abaixo do mínimo que o completeness do "
        "Manager cobra, e baixam a nota da API:\n"
        + "\n".join(f"  - {s}" for s in short)
        + "\n\nO mínimo é: `summary`, descrição de resposta e de parâmetro com mais de 4 "
        "caracteres; descrição de propriedade com 9 ou mais; descrição de schema com "
        "mais de 9, e schema com propriedades."
    )
