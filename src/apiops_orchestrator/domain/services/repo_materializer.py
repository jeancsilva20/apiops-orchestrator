"""Materializa o layout canônico a partir do estado do Manager.

Lógica pura: recebe os dicts já lidos por GET e devolve `(file_path, text)`. Não
toca disco nem rede — quem escreve é a camada de aplicação.

Opera sobre o **wire cru**, sem modelos intermediários.

Decisões que o código implementa:

* **V-18** — o escopo raiz é `all.yaml`;
* **V-25** — a supressão de item herdado é a **lista completa explícita**; o item
  removido é identificado por `parent.id`, confirmado por leitura da revisão 9175;
* **V-22** — o que está fora de `FIRST`/`SECOND` não entra no YAML;
* **V-26** — a herança é sempre declarada (`inherit`);
* **V-28** — itens próprios sem marcações são append (`inherit: true`);
* **fila 23/24** — os dois reparos de serialização.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from apiops_orchestrator.domain.services import repo_layout as layout
from apiops_orchestrator.domain.services.interceptor_flow import partition
from apiops_orchestrator.domain.services.yaml_serialization import scalar

DESCRIPTION_WIDTH = 92
STATUS_REMOVED = "REMOVED"


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


def _description(value: Optional[str], indent: int = 0) -> List[str]:
    """Descrição curta em uma linha; longa vira bloco dobrado `>-`."""
    import re

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


def _interceptors_block(items: Sequence[Dict[str, Any]], title: str) -> List[str]:
    if not items:
        return []
    lines = ["", f"{title}:"]
    for item in items:
        if item.get("type") == "Custom" and item.get("customInterceptorId"):
            lines.append("  - type: Custom")
            lines.append(f"    id: {item['customInterceptorId']}")
            continue
        lines.append(f"  - type: {scalar(item.get('type'))}")
        raw = item.get("content")
        data = raw
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except (TypeError, ValueError):
                data = raw
        if isinstance(data, (dict, list)) and data:
            lines.append("    content:")
            lines.extend(_block(data, 6))
        elif data not in (None, "", {}, []):
            lines.append(f"    content: {scalar(data)}")
    return lines


def _by_point(items: Iterable[Dict[str, Any]], point: str) -> List[Dict[str, Any]]:
    return [i for i in items if (i.get("executionPoint") or "").upper() == point]


def _flow(items: Sequence[Dict[str, Any]]) -> List[str]:
    return _interceptors_block(_by_point(items, "FIRST"), "interceptors_request") + (
        _interceptors_block(_by_point(items, "SECOND"), "interceptors_response")
    )


# --------------------------------------------------------------------------- escopos


def _split(items: Optional[Sequence[Dict[str, Any]]]) -> Tuple[list, list, list]:
    """Governados presentes, tombstones e preservados.

    O tombstone (`status: REMOVED`) NÃO é item do fluxo: é a marca de um item
    herdado que foi suprimido. Tratá-lo como presente publicaria de volta o que
    se queria remover.
    """
    governed, preserved = partition(items)
    present = [i for i in governed if i.get("status") != STATUS_REMOVED]
    tombstones = [i for i in governed if i.get("status") == STATUS_REMOVED]
    return present, tombstones, preserved


def _suppress(inherited: Sequence[Dict[str, Any]], tombstones: Sequence[Dict[str, Any]]):
    """Fluxo herdado menos os itens apontados por `parent.id` (V-25 §2.1)."""
    targets = {
        (t.get("parent") or {}).get("id")
        for t in tombstones
        if (t.get("parent") or {}).get("id") is not None
    }
    return [i for i in inherited if i.get("id") not in targets], targets


def materialize(api: Dict[str, Any], revision: Dict[str, Any]) -> MaterializationResult:
    """Produz a árvore canônica inteira a partir do estado remoto."""
    warnings: List[str] = []
    files: List[MaterializedFile] = []

    # --- api-basic-info.yaml -------------------------------------------------
    spec = {
        "id": api.get("id"),
        "name": api.get("name"),
        "version": api.get("version"),
        "basePath": api.get("basePath"),
    }
    lines = [
        "apiVersion: api-management.sensedia.com/v1",
        "kind: ApiBasicInfo",
        "spec:",
        f"  id: {scalar(spec['id'])}",
        f"  name: {scalar(spec['name'])}",
        f"  version: {scalar(spec['version'])}",
        f"  basePath: {scalar(spec['basePath'])}",
    ]
    lines.extend(_description(api.get("description"), indent=2))
    # `template` não vem do wire: a plataforma não tem esta chave (D-12).
    lines.append("  template: ''")
    responsible = api.get("apiResponsible") or {}
    lines.append("  apiResponsible:")
    lines.append(f"    username: {scalar(responsible.get('username') or '')}")
    lines.append(f"    groupName: {scalar(responsible.get('groupName') or '')}")
    tags = api.get("apiTags")
    if tags is not None:
        lines.append("  apiTags:")
        for t in tags:
            lines.append(f"    - attributeName: {scalar(t.get('attributeName'))}")
            values = t.get("tags") or []
            if values:
                lines.append("      tags:")
                lines.extend(_block(values, 8))
            else:
                lines.append("      tags: []")
    files.append(_file(layout.BASIC_INFO_FILE, lines))

    # --- all.yaml (escopo raiz) ---------------------------------------------
    root_present, root_tombstones, root_preserved = _split(
        revision.get("interceptors")
    )
    if root_tombstones:
        warnings.append(
            "a raiz da revision tem item com status REMOVED, o que não deveria "
            "acontecer: a raiz não herda de nenhum escopo acima"
        )
    lines = [
        f"# escopo `all` — raiz da revision {revision.get('id')} "
        f"(revisionNumber {revision.get('revisionNumber')})",
        f"# API {api.get('id')} · {api.get('name')} · {api.get('basePath')}",
    ]
    lines += _destination_block(revision.get("destination"), revision.get("timeout"))
    lines += _flow(root_present)
    if root_preserved:
        lines += [
            "",
            f"# {len(root_preserved)} interceptor(es) fora de FIRST/SECOND — "
            "estado não governado, preservado por GET no publish",
        ]
    files.append(_file(layout.ROOT_FILE, lines))

    # --- recursos e operações ------------------------------------------------
    resources = revision.get("resources") or []
    for resource in resources:
        folder = layout.folder_name(resource, resources, warnings)
        base = f"{layout.RESOURCES_FOLDER}/{folder}"

        rec_present, rec_tombstones, _ = _split(resource.get("interceptors"))
        resource_inherited, _ = _suppress(root_present, rec_tombstones)
        resource_effective = resource_inherited + rec_present

        lines = [f"name: {scalar(resource.get('name'))}"]
        lines.extend(_description(resource.get("description")))
        lines += _destination_block(resource.get("destination"), resource.get("timeout"))
        lines += _declare_inheritance(
            present=rec_present,
            tombstones=rec_tombstones,
            inherited=root_present,
        )
        files.append(_file(f"{base}/{layout.RESOURCE_FILE}", lines))

        for op in resource.get("operations") or []:
            op_present, op_tombstones, _ = _split(op.get("interceptors"))
            lines = [f"path: {scalar(op.get('path'))}"]
            lines += _destination_block(op.get("destination"), op.get("timeout"))
            lines.extend(_description(op.get("description")))
            lines += _declare_inheritance(
                present=op_present,
                tombstones=op_tombstones,
                inherited=resource_effective,
            )
            name = layout.file_name(op, warnings)
            files.append(_file(f"{base}/{name}", lines))

    return MaterializationResult(files=files, warnings=warnings)


def _declare_inheritance(
    *,
    present: Sequence[Dict[str, Any]],
    tombstones: Sequence[Dict[str, Any]],
    inherited: Sequence[Dict[str, Any]],
) -> List[str]:
    """Decide entre herança pura, append e supressão — e escreve o bloco.

    A supressão (V-25) é a **lista completa explícita**: o fluxo herdado menos os
    itens apontados por `parent.id`, mais o que o escopo tem de próprio. Sem
    marcações, os itens próprios executam depois do herdado: é append (V-28).
    """
    if tombstones:
        remaining, targets = _suppress(inherited, tombstones)
        names = ", ".join(sorted({str(t.get("type")) for t in tombstones}))
        unresolved = len(tombstones) - len(
            [a for a in targets if any(i.get("id") == a for i in inherited)]
        )
        lines = ["", "inherit: false", f"# este ponto deixa de executar, do herdado: {names}"]
        flow = list(remaining) + list(present)
        if flow:
            lines.append("# a lista abaixo é o fluxo completo que vale aqui")
        else:
            lines.append("# não executa nenhum interceptor")
        if unresolved:
            lines.append(
                f"# atenção: {unresolved} remoção(ões) apontam para um "
                "interceptor que não está no fluxo herdado deste ponto"
            )
        return lines + _flow(flow)

    if not present:
        # Sem artigo: `scope` ora é "recurso", ora "operação", e qualquer
        # artigo fixo erra a concordância num dos dois.
        return [
            "",
            "inherit: true",
            "# apenas herda o fluxo do nível acima: nenhum interceptor próprio",
        ]

    return [
        "",
        "inherit: true",
        "# os interceptors abaixo executam depois do fluxo herdado",
    ] + _flow(present)


def _file(file_path: str, lines: Sequence[Optional[str]]) -> MaterializedFile:
    text = "\n".join(l for l in lines if l is not None).rstrip() + "\n"
    return MaterializedFile(file_path=file_path, text=text)
