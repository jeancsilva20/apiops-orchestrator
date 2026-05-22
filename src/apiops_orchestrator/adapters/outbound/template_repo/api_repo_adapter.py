import logging
import shutil
from pathlib import Path
from apiops_orchestrator.domain.ports.api_repo_port import ApiRepoPort


class ApiRepoAdapter(ApiRepoPort):
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def create_dir(self, path: Path, dir_name: str) -> None:
        path.joinpath(dir_name).mkdir()

    def delete_dir(self, path: Path, dir_name: str) -> None:
        shutil.rmtree(path.joinpath(dir_name))

    def rename_dir(self, path: Path, dir_name: str, new_dir_name: str) -> None:
        path.joinpath(dir_name).rename(path.joinpath(new_dir_name))

    def create_file(self, path: Path, file_name: str, content: str) -> None:
        file_path = path.joinpath(file_name)
        file_path.write_text(content, encoding="utf-8")

    def delete_file(self, path: Path, file_name: str) -> None:
        file_path = path.joinpath(file_name)
        file_path.unlink()
