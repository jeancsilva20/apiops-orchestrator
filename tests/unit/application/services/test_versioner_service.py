from pathlib import Path
from unittest.mock import Mock

import pytest

from apiops_orchestrator.application.services.versioner_service import VersionerService

class FakeSettings:
    def __init__(self, root: Path):
        self.PROJECT_ROOT = root
        self.API_REPO_FOLDER = "repo"

@pytest.fixture
def settings(tmp_path):
    return FakeSettings(tmp_path)

@pytest.fixture
def repo_adapter():
    return Mock()

@pytest.fixture
def manager_adapter():
    adapter = Mock()
    adapter.get_api_by_id.return_value = {
        "lastRevision": {"revisionNumber": 1}
    }
    return adapter

def test_version_success(tmp_path, settings, repo_adapter, manager_adapter):
    repo_root = tmp_path / "repo"
    revisions = repo_root / "src" / "apis" / "revisions"
    revisions.mkdir(parents=True)

    service = VersionerService(manager_adapter,repo_adapter,settings)

    service.version()

    manager_adapter.get_api_by_id.assert_called_once()

    repo_adapter.create_file.assert_called_once()
    repo_adapter.rename_dir.assert_called_once()
    repo_adapter.delete_file.assert_called_once_with(repo_root, ".lock")

def test_create_tmp_dir_fails_if_lock_exists(tmp_path, settings, repo_adapter, manager_adapter):
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)
    (repo_root / ".lock").touch()

    service = VersionerService(manager_adapter, repo_adapter, settings)

    with pytest.raises(FileExistsError, match=".lock file already exists"):
        service._create_tmp_dir("2")

    repo_adapter.create_file.assert_not_called()
    repo_adapter.create_dir.assert_not_called()

def test_create_tmp_dir_fails_if_revision_exists(tmp_path, settings, repo_adapter, manager_adapter):
    revisions = tmp_path / "repo" / "src" / "apis" / "revisions" / "2"
    revisions.mkdir(parents=True)

    service = VersionerService(manager_adapter, repo_adapter, settings)

    with pytest.raises(FileExistsError, match="A file with the same revision number already exists"):
        service._create_tmp_dir("2")

    repo_adapter.create_file.assert_not_called()