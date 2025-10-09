from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List


class PathLoaderPort(ABC):
    @abstractmethod
    def load_path(self, path: Path) -> Any | List[Any]:
        """Importa um arquivo ou diretório suportado."""
        pass
