from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List


class FileLoaderPort(ABC):
    @abstractmethod
    def load_file_path(self, path: Path) -> Any | List[Any]:
        """Importa um arquivo ou diretório suportado."""
        pass
