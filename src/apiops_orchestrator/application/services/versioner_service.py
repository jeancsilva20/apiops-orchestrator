import logging
import shutil
from datetime import datetime

from apiops_orchestrator.application.services.revision_file_generator import (
    RevisionFileGenerator,
)
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.ports.api_repo_port import ApiRepoPort
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort
from apiops_orchestrator.infrastructure.observability.logging import set_status

logger = logging.getLogger(__name__)


class VersionerService:
    """
    Orchestrates the versioning process for an API revision. It handles the
    high-level process: creating temporary directories, handling transactions
    and cleanup, and delegating the file generation logic.
    """

    def __init__(
        self,
        manager_adapter: ManagerApiPort,
        repo_adapter: ApiRepoPort,
        settings: Settings,
    ):
        self.repo = repo_adapter
        self.manager = manager_adapter
        self.settings = settings
        self.repo_path = settings.PROJECT_ROOT / settings.API_REPO_FOLDER
        self.revisions_folder = self.repo_path / "src" / "apis" / "revisions"
        self.file_generator = RevisionFileGenerator(repo_adapter)

    def version(self, api_content: list):
        """
        Runs the full versioning process for an API revision.
        If any error occurs, it triggers a cleanup process.
        """
        tmp_dir_name = None
        try:
            api_info = self.manager.get_api_by_id()
            new_revision_number = str(api_info["lastRevision"]["revisionNumber"])

            tmp_dir_name = self._create_tmp_dir(new_revision_number)
            logger.info(f"Created temporary directory for revision: {tmp_dir_name}")
            tmp_dir_path = self.revisions_folder / tmp_dir_name

            self.file_generator.create_revision_files(api_content, tmp_dir_path)
            logger.info("Successfully created all revision files.")

            self._finish_process_sucess(tmp_dir_name, new_revision_number)
            logger.info(f"Successfully finalized revision {new_revision_number}.")

            # Set tmp_dir_name to None to prevent cleanup of a successful revision
            tmp_dir_name = None
        except Exception as e:
            set_status("FAILURE")
            logger.error(f"Error during versioning process: {e}", exc_info=True)
            # Re-raise the exception to stop the main process
            raise
        finally:
            if tmp_dir_name:
                self._cleanup_on_error(tmp_dir_name)

    def _cleanup_on_error(self, tmp_dir_name: str):
        """Deletes the temporary directory and the lock file in case of an error."""
        logger.info(f"Cleaning up due to error. Removing tmp dir: {tmp_dir_name}")
        tmp_dir_path = self.revisions_folder / tmp_dir_name

        try:
            if tmp_dir_path.exists() and tmp_dir_path.is_dir():
                shutil.rmtree(tmp_dir_path)

            lock_file_path = self.repo_path / ".lock"
            if lock_file_path.exists():
                self.repo.delete_file(self.repo_path, ".lock")

            logger.info("Cleanup successful.")
        except Exception as e:
            logger.error(f"Critical error during cleanup process: {e}", exc_info=True)

    def _finish_process_sucess(self, tmp_dir_name: str, new_revision_number: str):
        self.repo.rename_dir(self.revisions_folder, tmp_dir_name, new_revision_number)
        self.repo.delete_file(self.repo_path, ".lock")

    def _create_tmp_dir(self, new_revision_number: str) -> str:
        now = datetime.now()
        formatted_date = now.strftime("%Y.%m.%d-%H.%M.%S")
        lock_file = self.repo_path / ".lock"

        if lock_file.exists():
            raise FileExistsError(".lock file already exists")

        if (self.revisions_folder / new_revision_number).exists() and (
            self.revisions_folder / new_revision_number
        ).is_dir():
            raise FileExistsError(
                f"A file with the same revision number already exists, number: {new_revision_number}"
            )

        self.repo.create_file(
            self.repo_path, ".lock", f"timestamp = {str(formatted_date)}"
        )
        tmp_dir_name = f".tmp_{new_revision_number}_{str(formatted_date)}"

        self.repo.create_dir(self.revisions_folder, tmp_dir_name)
        self.repo.create_dir(self.revisions_folder / tmp_dir_name, "env-variables")
        self.repo.create_dir(self.revisions_folder / tmp_dir_name, "resources")
        self.repo.create_dir(self.revisions_folder / tmp_dir_name, "templates")
        return tmp_dir_name
