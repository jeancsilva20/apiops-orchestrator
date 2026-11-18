"""Outbound port that writes the managed area of an API repository."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

from apiops_orchestrator.domain.services.repo_materializer import MaterializedFile


class RepoWriteError(Exception):
    """The tree could not be written: nothing was left in the destination.

    `reason` is the cause in the user's terms (path too long, permission);
    `path` is the relative path that failed, when known.
    """

    def __init__(self, reason: str, path: str | None = None) -> None:
        self.reason = reason
        self.path = path
        super().__init__(f"{path}: {reason}" if path else reason)


class RepoWriterPort(ABC):
    @abstractmethod
    def write_managed_area(self, root: Path, files: Sequence[MaterializedFile]) -> None:
        """Replaces `api-basic-info.yaml`, `all.yaml` and `resources/` under `root` with `files`.

        All-or-nothing: the files are staged first and moved at the end; any
        failure raises `RepoWriteError` and leaves the destination untouched.
        Files outside the managed area are never touched.
        """
