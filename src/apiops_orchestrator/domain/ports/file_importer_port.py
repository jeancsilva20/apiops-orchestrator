from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List


class PathLoaderPort(ABC):
    @abstractmethod
    def load_path(self, path: Path) -> Any | List[Any]:
        """Import a supported file or directory."""
        pass
