"""Layout of the API repository and the JSON Schema of each file type, read from a schema folder."""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

from apiops_orchestrator.application.exceptions.schema_exceptions import SchemasUnavailableError

SCHEMA_SEN_SCHEMA_V1 = "apiops.sen-schema/v1"
CATALOG_FILE = "catalog.json"


class RepoFileType(str, Enum):
    """File types of the API repository layout; each value is a `name` in `catalog.json`."""

    BASIC_INFO = "basic-info"
    ALL = "all"
    COMPONENTS = "components"
    RESOURCE = "resource"
    OPERATION = "operation"


@dataclass(frozen=True)
class LayoutEntry:
    type: str
    file: str
    occurs: str
    schema_file: str


def layout_document(entries: List[LayoutEntry]) -> Dict[str, Any]:
    """Document `apiops.sen-schema/v1` of the layout listing."""
    return {
        "schema": SCHEMA_SEN_SCHEMA_V1,
        "layout": [{"type": e.type, "file": e.file, "occurs": e.occurs} for e in entries],
    }


class SchemaCatalog:
    """Reads `catalog.json` and the schemas of one folder."""

    def __init__(self, root: Path):
        self._root = root

    def layout(self) -> List[LayoutEntry]:
        catalog = self._read(CATALOG_FILE)
        fields = ("name", "file", "occurs", "schema")
        return [
            LayoutEntry(*(rule[f] for f in fields))
            for rule in catalog.get("layout") or []
            if all(rule.get(f) for f in fields)
        ]

    def schema_for(self, file_type: RepoFileType) -> Dict[str, Any]:
        """JSON Schema of the file type."""
        for entry in self.layout():
            if entry.type == file_type.value:
                return self._read(entry.schema_file)
        raise SchemasUnavailableError()

    def _read(self, name: str) -> Dict[str, Any]:
        try:
            return json.loads((self._root / name).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SchemasUnavailableError() from exc
