import json
import yaml
from pathlib import Path
from typing import Any, Callable
from apiops_orchestrator.adapters.inbound.files_importer.file_loader_enum import (
    FileTypeEnum,
)


def _load_yaml(file_path: Path) -> Any:
    """Loads a YAML file."""
    with open(file_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_json(file_path: Path) -> Any:
    """Loads a JSON file."""
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def _load_text(file_path: Path) -> str:
    """Loads a text file."""
    with open(file_path, encoding="utf-8") as f:
        return f.read()


FILE_LOADER_STRATEGIES: dict[str, Callable[[Path], Any]] = {
    FileTypeEnum.YAML.value: _load_yaml,
    FileTypeEnum.YML.value: _load_yaml,
    FileTypeEnum.JSON.value: _load_json,
    FileTypeEnum.TXT.value: _load_text,
}


class FileLoadingMessages:
    INVALID_FILE_FORMAT = "File format not supported for {file_path}. Supported formats are: {supported_formats}"
