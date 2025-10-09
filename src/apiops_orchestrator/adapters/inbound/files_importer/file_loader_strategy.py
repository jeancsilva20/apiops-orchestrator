import json
import yaml
from pathlib import Path
from typing import Any, Callable, Dict

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

FILE_LOADER_STRATEGIES: Dict[str, Callable[[Path], Any]] = {
    ".yaml": _load_yaml,
    ".yml": _load_yaml,
    ".json": _load_json,
    ".js": _load_text,
    ".txt": _load_text,
}

class FileLoadingMessages:
    INVALID_FILE_FORMAT = "File format not supported for {file_path}. Supported formats are: {supported_formats}"
