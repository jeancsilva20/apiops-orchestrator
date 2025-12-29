import pytest
from unittest.mock import Mock
from pathlib import Path

from apiops_orchestrator.application.services.file_importer_service import (
    FileImporterService,
)
from apiops_orchestrator.domain.ports.file_importer_port import PathLoaderPort


@pytest.fixture
def mock_importer():
    """Fixture for mocking the PathLoaderPort."""
    return Mock(spec=PathLoaderPort)


@pytest.fixture
def service(mock_importer):
    """Fixture for the FileImporterService."""
    return FileImporterService(importer=mock_importer)


def test_load_file_path_delegates_to_importer(service, mock_importer):
    """
    Given a file path,
    When the load_file_path method is called,
    Then it should delegate the call to the importer.
    """
    # Arrange
    test_path = Path("/fake/path/file.yaml")
    expected_result = {"key": "value"}
    mock_importer.load_path.return_value = expected_result

    # Act
    result = service.load_file_path(test_path)

    # Assert
    mock_importer.load_path.assert_called_once_with(test_path)
    assert result == expected_result


def test_load_file_path_handles_importer_errors(service, mock_importer):
    """
    Given a file path that causes an error in the importer,
    When the load_file_path method is called,
    Then it should propagate the exception.
    """
    # Arrange
    test_path = Path("/fake/path/non_existent_file.yaml")
    mock_importer.load_path.side_effect = FileNotFoundError("File not found")

    # Act & Assert
    with pytest.raises(FileNotFoundError):
        service.load_file_path(test_path)
    mock_importer.load_path.assert_called_once_with(test_path)


def test_load_directory_path(service, mock_importer):
    """
    Given a directory path,
    When the load_file_path method is called,
    Then it should return a list of loaded file contents.
    """
    # Arrange
    test_path = Path("/fake/directory")
    expected_result = [{"key": "value"}, {"other_key": "other_value"}]
    mock_importer.load_path.return_value = expected_result

    # Act
    result = service.load_file_path(test_path)

    # Assert
    mock_importer.load_path.assert_called_once_with(test_path)
    assert result == expected_result
