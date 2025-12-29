from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any

class ApiRepoPort(ABC):
    @abstractmethod
    def create_dir(self, path: Path, dir_name: str) -> Dict[str, Any]:
        """Create a new directory in the repository"""
        pass

    @abstractmethod
    def delete_dir(self, path: Path, dir_name: str) -> None:
        """Delete a directory in the repository"""
        pass

    @abstractmethod
    def rename_dir(self, path: Path, dir_name: str, new_dir_name: str) -> None:
        """Rename a directory in the repository"""
        pass

    @abstractmethod
    def create_file(self, path: Path, file_name: str, content: str) -> Dict[str, Any]:
        """Create a new file in the repository"""
    pass

    @abstractmethod
    def delete_file(self, path: Path, file_name: str) -> None:
        """Delete a file in the repository"""
        pass