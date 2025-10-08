import json, yaml
from pathlib import Path
from typing import Any, List
from apiops_orchestrator.domain.ports.file_importer_port import FileLoaderPort


class InvalidFileFormatError(Exception):
    pass


class LocalFileLoaderAdapter(FileLoaderPort):

    SUPPORTED = {".yaml", ".yml", ".json", ".js", ".txt"}

    def load_file_path(self, path: Path) -> Any | List[Any]:
        if not path.exists():
            raise FileNotFoundError(path)
        if path.is_file():
            return self._load_single_file(path)
        return [
            self._load_single_file(p)
            for p in path.rglob("*")
            if p.suffix in self.SUPPORTED
        ]

    @staticmethod
    def _load_single_file(file_path: Path) -> Any:
        suffix = file_path.suffix.lower()
        with open(file_path, encoding="utf-8") as f:
            if suffix in {".yaml", ".yml"}:
                return yaml.safe_load(f)
            elif suffix == ".json":
                return json.load(f)
            elif suffix in {".js", ".txt"}:
                return f.read()
            else:
                raise InvalidFileFormatError(
                    f"{file_path} must be one of: {LocalFileLoaderAdapter.SUPPORTED}"
                )
