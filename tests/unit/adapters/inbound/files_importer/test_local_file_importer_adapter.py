import pytest
from pathlib import Path
import yaml
import json
from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
    LocalFileImporterAdapter,
)

@pytest.fixture
def adapter():
    return LocalFileImporterAdapter()

def test_read_yaml(adapter, tmp_path: Path):
    content = {"key": "value"}
    file_path = tmp_path / "test.yaml"
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(content, f)
    
    result = adapter.read(str(file_path))
    assert result == content

def test_read_json(adapter, tmp_path: Path):
    content = {"key": "value"}
    file_path = tmp_path / "test.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(content, f)
    
    result = adapter.read(str(file_path))
    assert result == content

def test_read_not_found(adapter):
    with pytest.raises(FileNotFoundError):
        adapter.read("non_existent.yaml")

def test_exists(adapter, tmp_path: Path):
    file_path = tmp_path / "test.txt"
    file_path.touch()
    
    assert adapter.exists(str(file_path)) is True
    assert adapter.exists(str(tmp_path / "missing.txt")) is False

def test_list_directories(adapter, tmp_path: Path):
    (tmp_path / "dir1").mkdir()
    (tmp_path / "dir2").mkdir()
    (tmp_path / "file.txt").touch()
    
    dirs = adapter.list_directories(str(tmp_path))
    assert len(dirs) == 2
    assert any("dir1" in d for d in dirs)
    assert any("dir2" in d for d in dirs)

def test_glob_files(adapter, tmp_path: Path):
    (tmp_path / "test1.yaml").touch()
    (tmp_path / "test2.yaml").touch()
    (tmp_path / "other.txt").touch()
    
    files = adapter.glob_files(str(tmp_path), "*.yaml")
    assert len(files) == 2
    assert any("test1.yaml" in f for f in files)
    assert any("test2.yaml" in f for f in files)
