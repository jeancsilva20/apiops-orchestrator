from datetime import datetime

from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.ports.api_repo_port import ApiRepoPort
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort


class VersionerService:
    def __init__(self, manager_adapter: ManagerApiPort, repo_adapter: ApiRepoPort, settings: Settings):
        self.repo = repo_adapter
        self.manager = manager_adapter
        self.repo_path = (settings.PROJECT_ROOT / settings.API_REPO_FOLDER)
        self.revisions_folder = self.repo_path / "src" / "apis" / "revisions"

    def version(self):
        api_info = self.manager.get_api_by_id()
        new_revision_number = str(api_info["lastRevision"]["revisionNumber"] + 1)
        tmp_dir_name = self._create_tmp_dir(new_revision_number)
        # Create files
        self._finish_process(tmp_dir_name, new_revision_number)
        # Add logs

    def _finish_process(self, tmp_dir_name: str, new_revision_number: str):
        self.repo.rename_dir(self.revisions_folder, tmp_dir_name, new_revision_number)
        self.repo.delete_file(self.repo_path, ".lock")

    def _create_tmp_dir(self, new_revision_number: str) -> str:
        now = datetime.now()
        formatted_date = now.strftime("%Y.%m.%d-%H.%M.%S")
        lock_file = self.repo_path / ".lock"

        if lock_file.exists():
            raise FileExistsError(".lock file already exists")

        if (self.revisions_folder/new_revision_number).exists() and (self.revisions_folder/new_revision_number).is_dir():
            raise FileExistsError(f"A file with the same revision number already exists, number: {new_revision_number}")

        self.repo.create_file(self.repo_path, ".lock", f"timestamp = {str(formatted_date)}")
        tmp_dir_name = f".tmp_{new_revision_number}_{str(formatted_date)}"

        self.repo.create_dir(self.revisions_folder, tmp_dir_name)
        self.repo.create_dir(self.revisions_folder / tmp_dir_name, "env-variables")
        self.repo.create_dir(self.revisions_folder / tmp_dir_name, "resources")
        self.repo.create_dir(self.revisions_folder / tmp_dir_name, "templates")
        return tmp_dir_name

