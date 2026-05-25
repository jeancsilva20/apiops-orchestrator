from abc import ABC, abstractmethod
from typing import Dict, Any, List

class LocalFileImporterPort(ABC):
    @abstractmethod
    def read(self, path: str) -> Dict[str, Any]:
        """Reads a local file and returns its content as a dictionary."""
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Checks if a local path exists."""
        pass

    @abstractmethod
    def list_directories(self, path: str) -> List[str]:
        """Lists directories within a given path."""
        pass

    @abstractmethod
    def glob_files(self, path: str, pattern: str) -> List[str]:
        """Finds files matching a glob pattern."""
        pass
