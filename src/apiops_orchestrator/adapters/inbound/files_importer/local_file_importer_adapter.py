from pathlib import Path
from typing import Any, List, Dict, Callable

from apiops_orchestrator.domain.ports.file_importer_port import PathLoaderPort
from apiops_orchestrator.adapters.inbound.files_importer.file_loader_strategy import (
    FILE_LOADER_STRATEGIES,
    FileLoadingMessages,
)


class InvalidFileFormatError(Exception):
    pass


class LocalFileLoaderAdapter(PathLoaderPort):

    def __init__(self, loader_strategies: Dict[str, Callable[[Path], Any]] = None):
        self._loader_strategies = loader_strategies or FILE_LOADER_STRATEGIES

    @property
    def supported_extensions(self) -> set[str]:
        return set(self._loader_strategies.keys())

    def load_path(self, path: Path) -> Any | List[Any]:
        if not path.exists():
            raise FileNotFoundError(path)
        if path.is_file():
            return self._load_single_file(path)
        return [
            self._load_single_file(p)
            for p in path.rglob("*")
            if p.suffix.lower() in self.supported_extensions
        ]

    def _load_single_file(self, file_path: Path) -> Any:
        suffix = file_path.suffix.lower()
        loader = self._loader_strategies.get(suffix)

        if not loader:
            raise InvalidFileFormatError(
                FileLoadingMessages.INVALID_FILE_FORMAT.format(
                    file_path=file_path,
                    supported_formats=list(self.supported_extensions),
                )
            )
        return loader(file_path)
