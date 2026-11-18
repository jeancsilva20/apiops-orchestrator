"""Filesystem implementation of `RepoWriterPort`: staging folder, then move."""

import logging
import os
import shutil
from pathlib import Path
from typing import Sequence

from apiops_orchestrator.domain.ports.repo_writer_port import RepoWriteError, RepoWriterPort
from apiops_orchestrator.domain.services import repo_layout as layout
from apiops_orchestrator.domain.services.repo_materializer import MaterializedFile

logger = logging.getLogger(__name__)

STAGING_FOLDER = ".sen-sync.tmp"
MANAGED = (layout.BASIC_INFO_FILE, layout.ROOT_FILE, layout.RESOURCES_FOLDER)
# Windows refuses absolute paths of 260 characters or more without long-path support.
WINDOWS_MAX_PATH = 260


class RepoWriterAdapter(RepoWriterPort):
    def __init__(self, max_path: int | None = None) -> None:
        self._max_path = max_path if max_path is not None else (
            WINDOWS_MAX_PATH if os.name == "nt" else None
        )

    def write_managed_area(self, root: Path, files: Sequence[MaterializedFile]) -> None:
        root = Path(root).resolve()
        self._ensure_paths_fit(root, files)
        staging = root / STAGING_FOLDER
        try:
            if staging.exists():
                shutil.rmtree(staging)
            for file in files:
                target = staging / file.file_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(file.text, encoding="utf-8", newline="\n")
            for name in MANAGED:
                self._remove(root / name)
            for entry in staging.iterdir():
                shutil.move(str(entry), str(root / entry.name))
        except OSError as exc:
            logger.info("repo_writer.failed type=%s", type(exc).__name__)
            raise RepoWriteError(self._reason(exc), self._relative(exc, root)) from exc
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _ensure_paths_fit(self, root: Path, files: Sequence[MaterializedFile]) -> None:
        if self._max_path is None:
            return
        longest = max(files, key=lambda f: len(str(root / f.file_path)), default=None)
        if longest is None:
            return
        length = len(str(root / longest.file_path))
        if length >= self._max_path:
            raise RepoWriteError(
                f"o caminho absoluto teria {length} caracteres, acima do limite de "
                f"{self._max_path} do sistema de arquivos",
                longest.file_path,
            )

    @staticmethod
    def _remove(path: Path) -> None:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    @staticmethod
    def _reason(exc: OSError) -> str:
        if isinstance(exc, PermissionError):
            return "sem permissão de escrita"
        return exc.strerror or type(exc).__name__

    @staticmethod
    def _relative(exc: OSError, root: Path) -> str | None:
        filename = getattr(exc, "filename", None)
        if not filename:
            return None
        try:
            return str(Path(filename).resolve().relative_to(root)).replace("\\", "/")
        except ValueError:
            return str(filename)
