from pathlib import Path
from unittest.mock import Mock, patch, ANY

import pytest

from apiops_orchestrator.application.services.versioner_service import VersionerService


class FakeSettings:
    def __init__(self, root: Path):
        self.PROJECT_ROOT = root
        self.API_REPO_FOLDER = "repo"
        self.revisions_folder = (
            self.PROJECT_ROOT / self.API_REPO_FOLDER / "src" / "apis" / "revisions"
        )


@pytest.fixture
def settings(tmp_path):
    return FakeSettings(tmp_path)


@pytest.fixture
def repo_adapter():
    return Mock()


@pytest.fixture
def manager_adapter():
    adapter = Mock()
    adapter.get_api_by_id.return_value = {"lastRevision": {"revisionNumber": "1"}}
    return adapter


@pytest.fixture
def service(manager_adapter, repo_adapter, settings) -> VersionerService:
    # Make sure the base directories exist for the service to initialize
    (
        settings.PROJECT_ROOT / settings.API_REPO_FOLDER / "src" / "apis" / "revisions"
    ).mkdir(parents=True, exist_ok=True)
    return VersionerService(manager_adapter, repo_adapter, settings)


def test_version_success_orchestration(service, manager_adapter):
    """
    Tests the success path of the version method, mocking internal helpers
    to focus on the orchestration logic.
    """
    # Arrange
    service._create_tmp_dir = Mock(return_value=".tmp_123")
    service._finish_process_success = Mock()
    service._cleanup_on_error = Mock()
    service.file_generator = Mock()  # Directly mock the instance
    mock_file_generator_instance = service.file_generator

    api_content = [{"key": "value"}]
    tmp_dir_path = service.revisions_folder / ".tmp_123"

    # Act
    service.version(api_content)

    # Assert
    manager_adapter.get_api_by_id.assert_called_once()
    service._create_tmp_dir.assert_called_once_with("1")
    mock_file_generator_instance.create_revision_files.assert_called_once_with(
        api_content, tmp_dir_path
    )
    service._finish_process_success.assert_called_once_with(".tmp_123", "1")
    service._cleanup_on_error.assert_not_called()


def test_version_failure_triggers_cleanup(service, manager_adapter):
    """
    Tests that a failure during file generation triggers the cleanup process.
    """
    # Arrange
    service._create_tmp_dir = Mock(return_value=".tmp_123")
    service._finish_process_success = Mock()
    service._cleanup_on_error = Mock()
    service.file_generator = Mock()  # Directly mock the instance
    mock_file_generator_instance = service.file_generator
    mock_file_generator_instance.create_revision_files.side_effect = Exception(
        "Generation failed"
    )
    api_content = [{"key": "value"}]

    # Act & Assert
    with pytest.raises(Exception, match="Generation failed"):
        service.version(api_content)

    manager_adapter.get_api_by_id.assert_called_once()
    service._create_tmp_dir.assert_called_once_with("1")
    service._finish_process_success.assert_not_called()
    service._cleanup_on_error.assert_called_once_with(".tmp_123")


def test_version_does_not_cleanup_if_tmp_dir_not_created(service, manager_adapter):
    """
    Tests that cleanup is not called if the process fails before the
    temporary directory is created.
    """
    # Arrange
    manager_adapter.get_api_by_id.side_effect = Exception("API fetch failed")
    service._cleanup_on_error = Mock()

    # Act & Assert
    with pytest.raises(Exception, match="API fetch failed"):
        service.version([{"key": "value"}])

    service._cleanup_on_error.assert_not_called()


def test_create_tmp_dir_success(service, repo_adapter):
    """
    Tests the successful creation of a temporary directory and lock file.
    """
    # Arrange
    new_revision_number = "2"
    # Mock create_dir to prevent actual filesystem creation and
    # to avoid issues with Path operations on Mocks
    repo_adapter.create_dir.return_value = None

    # Act
    tmp_dir_name = service._create_tmp_dir(new_revision_number)

    # Assert
    assert tmp_dir_name.startswith(f".tmp_{new_revision_number}_")
    repo_adapter.create_file.assert_called_once_with(service.repo_path, ".lock", ANY)
    assert repo_adapter.create_dir.call_count == 4
    repo_adapter.create_dir.assert_any_call(service.revisions_folder, tmp_dir_name)
    repo_adapter.create_dir.assert_any_call(
        service.revisions_folder / tmp_dir_name, "env-variables"
    )


def test_create_tmp_dir_fails_if_lock_exists(service, repo_adapter):
    """
    Tests that directory creation fails if a .lock file already exists.
    """
    # Arrange
    # Simulate file existence using a real file
    (service.repo_path / ".lock").touch()

    # Act & Assert
    with pytest.raises(FileExistsError, match=".lock file already exists"):
        service._create_tmp_dir("2")

    repo_adapter.create_file.assert_not_called()
    repo_adapter.create_dir.assert_not_called()


def test_create_tmp_dir_fails_if_revision_exists(service, repo_adapter):
    """
    Tests that directory creation fails if a revision directory already exists.
    """
    # Arrange
    # Simulate directory existence
    (service.revisions_folder / "2").mkdir()

    # Act & Assert
    with pytest.raises(
        FileExistsError, match="A file with the same revision number already exists"
    ):
        service._create_tmp_dir("2")

    repo_adapter.create_file.assert_not_called()


def test_finish_process_sucess(service, repo_adapter):
    """
    Tests that the success handler renames the directory and deletes the lock file.
    """
    # Arrange
    tmp_dir_name = ".tmp_123"
    new_revision_number = "2"

    # Act
    service._finish_process_success(tmp_dir_name, new_revision_number)

    # Assert
    repo_adapter.rename_dir.assert_called_once_with(
        service.revisions_folder, tmp_dir_name, new_revision_number
    )
    repo_adapter.delete_file.assert_called_once_with(service.repo_path, ".lock")


@patch("apiops_orchestrator.application.services.versioner_service.shutil")
def test_cleanup_on_error(mock_shutil, service, repo_adapter):
    """
    Tests that the error handler removes the temp directory and the lock file.
    """
    # Arrange
    tmp_dir_name = ".tmp_123"
    tmp_dir_path = service.revisions_folder / tmp_dir_name
    lock_file_path = service.repo_path / ".lock"

    # Simulate existence for the cleanup logic's checks
    tmp_dir_path.mkdir()
    lock_file_path.touch()

    # Act
    service._cleanup_on_error(tmp_dir_name)

    # Assert
    mock_shutil.rmtree.assert_called_once_with(tmp_dir_path)
    repo_adapter.delete_file.assert_called_once_with(service.repo_path, ".lock")
