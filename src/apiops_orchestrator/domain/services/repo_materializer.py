"""Materializa o layout canônico a partir do estado do Manager.

Lógica pura: recebe os modelos `Api` e `Revision` já lidos por GET e devolve
`(file_path, text)`. Não toca disco nem rede — quem escreve é a camada de aplicação.

Com o swagger da revisão, o contrato OpenAPI entra na mesma árvore: `components.yaml`
(sempre), `contact`/`tags`/`security` no `api-basic-info.yaml` e os campos de
contrato no arquivo de cada operação. A extração dos campos é de `openapi_contract`.

Os comentários dos arquivos são fixos: dizem ao dev o que cada campo faz e nunca
citam estado que varie entre branches (id de revisão, itens removidos), para que
editar um campo não exija editar o comentário e o merge de `feat/*` não conflite.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from apiops_orchestrator.domain.models.api_model import Api, Interceptor, Resource, Revision
from apiops_orchestrator.domain.services import openapi_contract as contract
from apiops_orchestrator.domain.services import repo_layout as layout
from apiops_orchestrator.domain.services.revision_payload import repository_mock_content
from apiops_orchestrator.domain.services.yaml_serialization import scalar

DESCRIPTION_WIDTH = 92
STATUS_REMOVED = "REMOVED"

# Fixed comments of the generated files, in one place. Each value is one line or
# a tuple of lines, without indentation: the writer indents where it applies.
COMMENTS = {
    "root_header": (
        "# escopo raiz da API: destination e interceptors herdados por todos os "
        "recursos e operações"
    ),
    "inherit": (
        "# inherit: true  executa o fluxo herdado do escopo acima e, depois, os "
        "interceptors declarados abaixo",
        "# inherit: false ignora o fluxo herdado e executa só os interceptors "
        "declarados abaixo",
    ),
    "id": "# id da API no Manager; gravado pelo sen sync, não edite",
    "base_path": "# basePath não muda depois que a API é criada; divergência aborta a publicação",
    "template": "# id da API-template que define o padrão de interceptors conferido pelo sen validate",
    "api_tags": "# apiTags: lista completa; ausente preserva o que está no Manager, [] remove todas",
    "root_contract": "# contrato OpenAPI da raiz: info.contact, tags (grupos de rotas, não apiTags) e security",
    "components_header": (
        "# componentes OpenAPI reutilizáveis, apontados por $ref: '#/components/<seção>/<nome>'",
        f"# seções aceitas: {', '.join(contract.GOVERNED_SECTIONS)}",
    ),
    "operation_contract": "# contrato OpenAPI da rota",
}


@dataclass(frozen=True)
class MaterializedFile:
    file_path: str
    text: str


@dataclass(frozen=True)
class MaterializationResult:
    files: List[MaterializedFile]
    warnings: List[str]

    @property
    def paths(self) -> List[str]:
        return [a.file_path for a in self.files]


# --------------------------------------------------------------------------- YAML


def _block(data: Any, indent: int) -> List[str]:
    """Serializa dict/list em YAML de bloco, com os reparos de escalar."""
    lines: List[str] = []
    pad = " " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)) and value:
                lines.append(f"{pad}{key}:")
                lines.extend(_block(value, indent + 2))
            elif isinstance(value, dict):
                lines.append(f"{pad}{key}: {{}}")
            elif isinstance(value, list):
                lines.append(f"{pad}{key}: []")
            else:
                lines.append(f"{pad}{key}: {scalar(value)}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item:
                sub = _block(item, indent + 2)
                lines.append(f"{pad}- {sub[0].strip()}")
                lines.extend(sub[1:])
            else:
                lines.append(f"{pad}- {scalar(item)}")
    return lines


class _ContractDumper(yaml.SafeDumper):
    """No anchors or aliases; multi-line text comes out as a `|` block."""

    def ignore_aliases(self, data: Any) -> bool:
        return True


def _contract_text(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = "|" if "\n" in value and not value.endswith("\n") else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_ContractDumper.add_representer(str, _contract_text)


def _contract_lines(data: Any, indent: int = 0) -> List[str]:
    """Contract YAML lines, with the types preserved on read-back; an empty mapping is `{}`."""
    raw = yaml.dump(
        data,
        Dumper=_ContractDumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=float("inf"),
    )
    pad = " " * indent
    return [f"{pad}{line}" if line else line for line in raw.rstrip("\n").split("\n")]


def _description(value: Optional[str], indent: int = 0) -> List[str]:
    """Descrição curta em uma linha; longa vira bloco dobrado `>-`."""
    raw = re.sub(r"\s+", " ", str(value or "").strip())
    pad = " " * indent
    if not raw:
        return []
    if len(raw) <= 90:
        return [f"{pad}description: {scalar(raw)}"]
    lines = [f"{pad}description: >-"]
    current = ""
    for word in raw.split(" "):
        if len(current) + len(word) + 1 > DESCRIPTION_WIDTH:
            lines.append(f"{pad}  {current}")
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(f"{pad}  {current}")
    return lines


def _destination_block(url: Any, timeout: Any) -> List[str]:
    lines = ["destination:"]
    if url:
        lines.append(f"  url: {scalar(url)}")
    else:
        lines.append("  url: ''            # vazio = herda do escopo acima")
    if timeout not in (None, ""):
        lines.append(f"  timeout: {scalar(str(timeout))}")
    return lines


def _interceptors_block(items: Sequence[Interceptor], title: str) -> List[str]:
    if not items:
        return []
    lines = ["", f"{title}:"]
    for item in items:
        if item.type == "Custom" and item.custom_interceptor_id:
            lines.append("  - type: Custom")
            lines.append(f"    id: {item.custom_interceptor_id}")
            continue
        lines.append(f"  - type: {scalar(item.type)}")
        data = item.content
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (TypeError, ValueError):
                data = item.content
        if item.type == "Mock":
            # The Manager keeps `body` and `status` as text or as object/number,
            # depending on who wrote them; the repository always gets object/number.
            data = repository_mock_content(data)
        if isinstance(data, (dict, list)) and data:
            lines.append("    content:")
            lines.extend(_block(data, 6))
        elif isinstance(data, dict):
            # The Manager keeps `'{}'` for the types without settings; the
            # repository declares the empty object so the PUT sends it back.
            lines.append("    content: {}")
        elif data not in (None, "", []):
            lines.append(f"    content: {scalar(data)}")
    return lines


def _by_point(items: Iterable[Interceptor], point: str) -> List[Interceptor]:
    return [i for i in items if (i.execution_point or "").upper() == point]


def _flow(items: Sequence[Interceptor]) -> List[str]:
    return _interceptors_block(_by_point(items, "FIRST"), "interceptors_request") + (
        _interceptors_block(_by_point(items, "SECOND"), "interceptors_response")
    )


# --------------------------------------------------------------------------- escopos


def _key(item: Interceptor) -> Tuple[Any, Any, Any, Any]:
    """Identidade de conteúdo, para apontar um próprio que repete um herdado."""
    content = item.content
    if isinstance(content, (dict, list)):
        content = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return (item.execution_point, item.type, item.custom_interceptor_id, content)


def _split(
    items: Sequence[Interceptor], scope: str, warnings: List[str]
) -> Tuple[List[Interceptor], List[Interceptor]]:
    """Itens próprios e marcações de supressão de um escopo.

    A marcação (`status: REMOVED` com `parent`) NÃO é item do fluxo: é a marca de
    um item herdado que foi suprimido. Tratá-la como presente publicaria de volta
    o que se queria remover. Um item com `parent` e outro status não tem regra
    conhecida: é tratado como próprio, com aviso. O que está fora de FIRST/SECOND
    não entra no YAML.
    """
    own: List[Interceptor] = []
    tombstones: List[Interceptor] = []
    for item in items:
        if not layout.is_governed(item.execution_point):
            continue
        if item.status == STATUS_REMOVED:
            tombstones.append(item)
        elif item.parent_id is not None:
            warnings.append(
                f"{scope}: {item.label} com parent {item.parent_id} e status "
                f"{item.status!r} não reconhecido — tratado como próprio"
            )
            own.append(item)
        else:
            own.append(item)
    return own, tombstones


def _suppress(inherited: Sequence[Interceptor], tombstones: Sequence[Interceptor]):
    """Fluxo herdado menos os itens apontados por `parent.id`."""
    targets = {t.parent_id for t in tombstones if t.parent_id is not None}
    return [i for i in inherited if i.id not in targets], targets


def _scope_flow(
    items: Sequence[Interceptor],
    inherited: Sequence[Interceptor],
    scope: str,
    warnings: List[str],
) -> Tuple[List[str], List[Interceptor]]:
    """Bloco de herança do escopo e o fluxo efetivo que ele passa aos filhos.

    A supressão é a lista completa explícita: o fluxo herdado menos os itens
    apontados por `parent.id`, mais o que o escopo tem de próprio. Sem marcações,
    os itens próprios executam depois do herdado.
    """
    own, tombstones = _split(items, scope, warnings)
    remaining, targets = _suppress(inherited, tombstones)
    orphans = sorted(str(t) for t in targets if not any(i.id == t for i in inherited))
    if orphans:
        warnings.append(
            f"{scope}: REMOVED aponta para interceptor fora do fluxo herdado: "
            f"{', '.join(orphans)}"
        )
    inherited_keys = {_key(i) for i in remaining}
    for item in own:
        if _key(item) in inherited_keys:
            warnings.append(
                f"{scope}: {item.label} próprio repete um herdado idêntico — "
                "com a herança preservada os dois entram no fluxo"
            )

    effective = list(remaining) + list(own)
    lines = ["", *COMMENTS["inherit"]]
    if tombstones:
        return lines + ["inherit: false"] + _flow(effective), effective
    return lines + ["inherit: true"] + _flow(own), effective


def _basic_info(api: Api, template: Any, root_contract: Dict[str, Any]) -> List[str]:
    """
    Campos de fundo (visibility, apiType, creationDate, revisions, lastRevision,
    flags e contadores) NÃO entram no YAML — são hidratados por GET no publish.
    `template` não vem do wire: a plataforma não tem esta chave.
    """
    lines = [
        "apiVersion: api-management.sensedia.com/v1",
        "kind: ApiBasicInfo",
        "spec:",
        f"  {COMMENTS['id']}",
        f"  id: {scalar(api.id)}",
        f"  name: {scalar(api.name)}",
        f"  version: {scalar(api.version)}",
        f"  {COMMENTS['base_path']}",
        f"  basePath: {scalar(api.base_path)}",
    ]
    lines.extend(_description(api.description, indent=2))
    lines.append(f"  {COMMENTS['template']}")
    lines.append(
        f"  template: {scalar(template) if template not in (None, '') else repr('')}"
    )
    responsible = api.api_responsible
    lines.append("  apiResponsible:")
    lines.append(f"    username: {scalar((responsible.username if responsible else None) or '')}")
    lines.append(f"    groupName: {scalar((responsible.group_name if responsible else None) or '')}")
    if api.api_tags is not None:
        lines.append(f"  {COMMENTS['api_tags']}")
        lines.append("  apiTags: []" if not api.api_tags else "  apiTags:")
        for tag in api.api_tags:
            lines.append(f"    - attributeName: {scalar(tag.attribute_name)}")
            if tag.tags:
                lines.append("      tags:")
                lines.extend(_block(list(tag.tags), 8))
            else:
                lines.append("      tags: []")
    if root_contract:
        lines.append(f"  {COMMENTS['root_contract']}")
        lines.extend(_contract_lines(root_contract, 2))
    return lines


def _operation_contract(
    contracts: Optional[Dict[Any, Dict[str, Any]]],
    route: Tuple[str, Any],
    scope: str,
    warnings: List[str],
) -> List[str]:
    """Contract block of one operation; `None` contracts means no swagger was given."""
    if contracts is None:
        return []
    fields = contracts.get(route)
    if fields is None:
        warnings.append(
            f"{scope}: rota fora do swagger da revision — escrita sem contrato; "
            "o sen validate barra até o dev declarar responses"
        )
        return []
    if "responses" not in fields:
        warnings.append(
            f"{scope}: swagger sem responses na rota — não escrito; "
            "o sen validate barra até o dev declarar"
        )
    if not fields:
        return []
    return ["", COMMENTS["operation_contract"]] + _contract_lines(fields)


def _naming_view(resource: Resource) -> Dict[str, Any]:
    """What `repo_layout` needs to name a folder: the name and the routes."""
    return {
        "name": resource.name,
        "operations": [{"method": o.method, "path": o.path} for o in resource.operations],
    }


def materialize(
    api: Api,
    revision: Revision,
    *,
    template: Any = "",
    swagger: Optional[Dict[str, Any]] = None,
) -> MaterializationResult:
    """Produz a árvore canônica inteira a partir do estado remoto.

    `template` é o valor de `spec.template` a gravar: vem do arquivo que já
    existe no repositório, nunca do Manager. Com `swagger`, o contrato OpenAPI
    entra na árvore; sem ele, a árvore sai só com o fluxo.
    """
    warnings: List[str] = []
    files: List[MaterializedFile] = []

    root_contract = contract.swagger_root_contract(swagger) if swagger is not None else {}
    contracts = (
        contract.swagger_operations_contract(swagger, warnings) if swagger is not None else None
    )

    files.append(_file(layout.BASIC_INFO_FILE, _basic_info(api, template, root_contract)))
    if swagger is not None:
        files.append(
            _file(
                layout.COMPONENTS_FILE,
                [*COMMENTS["components_header"], *_contract_lines(contract.swagger_components(swagger))],
            )
        )

    # --- all.yaml (escopo raiz) ---------------------------------------------
    root_own, root_tombstones = _split(revision.interceptors, "raiz", warnings)
    if root_tombstones:
        warnings.append(
            "a raiz da revision tem item com status REMOVED, o que não deveria "
            "acontecer: a raiz não herda de nenhum escopo acima"
        )
    lines = [COMMENTS["root_header"]]
    lines += _destination_block(revision.destination, revision.timeout)
    lines += _flow(root_own)
    files.append(_file(layout.ROOT_FILE, lines))

    # --- recursos e operações ------------------------------------------------
    naming = [_naming_view(r) for r in revision.resources]
    for resource, view in zip(revision.resources, naming):
        folder = layout.folder_name(view, naming, warnings)
        base = f"{layout.RESOURCES_FOLDER}/{folder}"

        lines = [f"name: {scalar(resource.name)}"]
        lines.extend(_description(resource.description))
        lines += _destination_block(resource.destination, resource.timeout)
        block, resource_flow = _scope_flow(
            resource.interceptors, root_own, f"recurso {resource.name}", warnings
        )
        files.append(_file(f"{base}/{layout.RESOURCE_FILE}", lines + block))

        for op in resource.operations:
            scope = f"{op.route[0]} {op.path}"
            lines = [f"path: {scalar(op.path)}"]
            lines += _destination_block(op.destination, op.timeout)
            lines.extend(_description(op.description))
            block, _ = _scope_flow(op.interceptors, resource_flow, scope, warnings)
            block += _operation_contract(contracts, op.route, scope, warnings)
            name = layout.file_name({"method": op.method, "path": op.path}, warnings)
            files.append(_file(f"{base}/{name}", lines + block))

    return MaterializationResult(files=files, warnings=warnings)


def _file(file_path: str, lines: Sequence[Optional[str]]) -> MaterializedFile:
    text = "\n".join(l for l in lines if l is not None).rstrip() + "\n"
    return MaterializedFile(file_path=file_path, text=text)
