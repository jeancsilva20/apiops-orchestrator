import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List
from apiops_orchestrator.domain.ports.local_file_importer_port import LocalFileImporterPort


class LocalFileImporterAdapter(LocalFileImporterPort):
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def read(self, path: str) -> Dict[str, Any]:
        """
        Reads a local file and returns its content as a dictionary.
        Supports YAML and JSON (via YAML parser).
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            self.logger.error(f"File not found: {path}")
            raise FileNotFoundError(f"The file at '{path}' was not found.")
        except PermissionError:
            self.logger.error(f"Permission denied: {path}")
            raise PermissionError(f"Permission denied when trying to read file at '{path}'.")
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing YAML/JSON file {path}: {e}")
            raise ValueError(f"Error parsing file at '{path}': {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error reading {path}: {e}")
            raise RuntimeError(f"An unexpected error occurred while reading '{path}': {e}")

    def exists(self, path: str) -> bool:
        """Checks if a local path exists."""
        try:
            return Path(path).exists()
        except Exception as e:
            self.logger.error(f"Error checking existence of {path}: {e}")
            return False

    def list_directories(self, path: str) -> List[str]:
        """Lists directories within a given path."""
        try:
            p = Path(path)
            if not p.exists():
                return []
            return [str(d) for d in p.iterdir() if d.is_dir()]
        except PermissionError:
            self.logger.error(f"Permission denied listing directory: {path}")
            raise PermissionError(f"Permission denied when listing directory '{path}'.")
        except Exception as e:
            self.logger.error(f"Error listing directory {path}: {e}")
            raise RuntimeError(f"Error listing directory '{path}': {e}")

    def glob_files(self, path: str, pattern: str) -> List[str]:
        """Finds files matching a glob pattern."""
        try:
            p = Path(path)
            if not p.exists():
                return []
            return [str(f) for f in p.glob(pattern)]
        except PermissionError:
            self.logger.error(f"Permission denied globbing files in: {path}")
            raise PermissionError(f"Permission denied when searching for files in '{path}'.")
        except Exception as e:
            self.logger.error(f"Error globbing files in {path} with pattern {pattern}: {e}")
            raise RuntimeError(f"Error globbing files in '{path}': {e}")
