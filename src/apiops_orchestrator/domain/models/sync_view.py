"""Resposta do `sen sync` (service → CLI), contrato `apiops.sen-sync/v1`."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from apiops_orchestrator.domain.models.validate_view import ValidateApi, ValidateRevision
from apiops_orchestrator.domain.services.revision_diff import Difference

SCHEMA_SEN_SYNC_V1 = "apiops.sen-sync/v1"

MODE_LOAD = "load"
MODE_CHECK = "check"


@dataclass(frozen=True)
class SyncView:
    """Árvore completa da resposta do `sen sync`, nos dois modos."""

    schema: str
    generated_at: str
    mode: str
    api: ValidateApi
    revision: ValidateRevision
    # Absolute folder that received the load; `None` on `--check`.
    repository: Optional[str] = None
    files: List[str] = field(default_factory=list)
    resources: int = 0
    operations: int = 0
    warnings: List[str] = field(default_factory=list)
    differences: List[Difference] = field(default_factory=list)

    @property
    def in_sync(self) -> bool:
        return not self.differences

    def to_document(self) -> Dict[str, Any]:
        """Árvore do contrato v1, na ordem declarada; cada modo traz só o seu bloco."""
        document: Dict[str, Any] = {
            "schema": self.schema,
            "generatedAt": self.generated_at,
            "mode": self.mode,
            "api": {
                "managerId": self.api.manager_id,
                "name": self.api.name,
                "version": self.api.version,
                "basePath": self.api.base_path,
            },
            "revision": {
                "managerId": self.revision.manager_id,
                "revisionNumber": self.revision.revision_number,
            },
        }
        if self.mode == MODE_CHECK:
            document["inSync"] = self.in_sync
            document["differences"] = [
                {
                    "file": d.file,
                    "field": d.field,
                    "repository": d.repository,
                    "manager": d.manager,
                }
                for d in self.differences
            ]
        else:
            document["repository"] = self.repository
            document["files"] = list(self.files)
            document["counts"] = {
                "files": len(self.files),
                "resources": self.resources,
                "operations": self.operations,
            }
        document["warnings"] = list(self.warnings)
        return document
