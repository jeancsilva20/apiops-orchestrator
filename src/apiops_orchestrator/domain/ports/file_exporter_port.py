from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List

class PathExporterPort(ABC):
    @abstractmethod
    def export_path(self, content: Any, output_folder: Path) -> Any | List[Any]:
        """Export a supported file"""
        pass

    @abstractmethod
    def generate_filename(self, method: str, path: str) -> str:
        """Transforms path and method into file name"""
        pass