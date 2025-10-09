import pytest
from pathlib import Path
import yaml
import json

from apiops_orchestrator.adapters.inbound.files_importer.local_file_importer_adapter import (
    LocalFileLoaderAdapter,
    InvalidFileFormatError,
)


# Fixture for the adapter instance
@pytest.fixture
def adapter():
    return LocalFileLoaderAdapter()


def test_load_single_yaml_file(adapter, tmp_path: Path):
    """Tests loading a single, valid YAML file."""
    content = {"name": "test-api", "version": "1.0"}
    file_path = tmp_path / "config.yaml"
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(content, f)

    result = adapter.load_file_path(file_path)
    assert result == content


def test_load_single_json_file(adapter, tmp_path: Path):
    """Tests loading a single, valid JSON file."""
    content = {"name": "test-api", "version": "1.0"}
    file_path = tmp_path / "config.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(content, f)

    result = adapter.load_file_path(file_path)
    assert result == content


def test_load_single_js_file(adapter, tmp_path: Path):
    """Tests loading a single, valid JS file."""
    content = "var teste = 'okay';"
    file_path = tmp_path / "script.js"
    file_path.write_text(content, encoding="utf-8")

    result = adapter.load_file_path(file_path)
    assert result == content


def test_load_single_txt_file(adapter, tmp_path: Path):
    """Tests loading a single, valid TXT file."""
    content = "This is a simple text file."
    file_path = tmp_path / "readme.txt"
    file_path.write_text(content, encoding="utf-8")

    result = adapter.load_file_path(file_path)
    assert result == content


def test_load_path_not_found(adapter):
    """Tests that FileNotFoundError is raised for a non-existent path."""
    non_existent_path = Path("/non/existent/path/file.yaml")
    with pytest.raises(FileNotFoundError):
        adapter.load_file_path(non_existent_path)


def test_load_unsupported_file_directly(adapter, tmp_path: Path):
    """Tests that an error is raised when loading an unsupported file type directly."""
    file_path = tmp_path / "document.docx"
    file_path.touch()
    with pytest.raises(InvalidFileFormatError):
        adapter.load_file_path(file_path)


def test_load_directory_with_multiple_file_types(adapter, tmp_path: Path):
    """Tests loading a directory with a mix of supported and unsupported files."""
    # Create a nested directory structure
    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()

    # Supported files
    (tmp_path / "config.yml").write_text("key: value")
    (tmp_path / "data.json").write_text('{"id": 123}')
    (sub_dir / "info.txt").write_text("some info")

    # Unsupported file (should be ignored)
    (tmp_path / "archive.zip").touch()
    (sub_dir / "image.png").touch()

    results = adapter.load_file_path(tmp_path)

    # The results can be in any order, so we check for presence and length
    assert len(results) == 3
    assert {"key": "value"} in results
    assert {"id": 123} in results
    assert "some info" in results


def test_load_empty_directory(adapter, tmp_path: Path):
    """Tests loading an empty directory, which should return an empty list."""
    results = adapter.load_file_path(tmp_path)
    assert results == []
