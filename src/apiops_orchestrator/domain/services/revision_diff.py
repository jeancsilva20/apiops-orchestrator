"""Semantic diff between two materialized trees (the `diff_engine` of `sen sync --check`).

Pure logic. Both sides are the output of `repo_materializer.materialize`, so the
comparison is made on the YAML read back from each file, never on its text:
comments, key order, quoting and line breaks do not count as a difference.

Each difference names the file, the field path inside it and the value on each
side. A file present on one side only is reported with `field=None`.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import yaml

from apiops_orchestrator.domain.services import repo_layout as layout
from apiops_orchestrator.domain.services.repo_materializer import MaterializedFile

ABSENT = "<ausente>"
# Fields that are sets on the wire: compared by membership, never by position.
UNORDERED = {(layout.BASIC_INFO_FILE, "spec.apiTags")}


@dataclass(frozen=True)
class Difference:
    file: str
    field: Optional[str]
    repository: Any
    manager: Any


def _normalize(value: Any) -> Any:
    """Canonical form for comparison: a numeric string equals its number.

    The kind travels with the value so that `True` and `1` stay different,
    which Python's own equality would not guarantee.
    """
    if value is None:
        return ("none",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        return ("number", float(value))
    if isinstance(value, str):
        try:
            return ("number", float(value.strip()))
        except ValueError:
            return ("text", value)
    return ("other", value)


def _parse(file: MaterializedFile) -> Any:
    return yaml.safe_load(file.text) or {}


def _api_tags_by_attribute(items: Any) -> Any:
    """`apiTags` keyed by attribute, each with its tags sorted and joined, for the set comparison."""
    if not isinstance(items, list):
        return items
    by_name: Dict[str, List[str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("attributeName"))
        tags = item.get("tags") or []
        by_name.setdefault(name, []).extend(str(t) for t in (tags if isinstance(tags, list) else [tags]))
    return {name: ", ".join(sorted(set(tags))) for name, tags in by_name.items()}


def _walk(path: str, left: Any, right: Any, out: List[Difference], file: str) -> None:
    if (file, path) in UNORDERED:
        left, right = _api_tags_by_attribute(left), _api_tags_by_attribute(right)
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right), key=str):
            child = f"{path}.{key}" if path else str(key)
            if key not in left:
                out.append(Difference(file, child, ABSENT, right[key]))
            elif key not in right:
                out.append(Difference(file, child, left[key], ABSENT))
            else:
                _walk(child, left[key], right[key], out, file)
        return
    if isinstance(left, list) and isinstance(right, list):
        for index in range(max(len(left), len(right))):
            child = f"{path}[{index}]"
            if index >= len(left):
                out.append(Difference(file, child, ABSENT, right[index]))
            elif index >= len(right):
                out.append(Difference(file, child, left[index], ABSENT))
            else:
                _walk(child, left[index], right[index], out, file)
        return
    if _normalize(left) != _normalize(right):
        out.append(Difference(file, path or None, left, right))


def compare(
    repository: Sequence[MaterializedFile], manager: Sequence[MaterializedFile]
) -> List[Difference]:
    """Differences between the repository side and the Manager side, by file and field."""
    local: Dict[str, MaterializedFile] = {f.file_path: f for f in repository}
    remote: Dict[str, MaterializedFile] = {f.file_path: f for f in manager}
    differences: List[Difference] = []
    for path in sorted(set(local) | set(remote)):
        if path not in local:
            differences.append(Difference(path, None, ABSENT, "arquivo presente"))
        elif path not in remote:
            differences.append(Difference(path, None, "arquivo presente", ABSENT))
        else:
            _walk("", _parse(local[path]), _parse(remote[path]), differences, path)
    return differences
