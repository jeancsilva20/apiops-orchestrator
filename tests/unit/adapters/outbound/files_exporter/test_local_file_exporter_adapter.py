import pytest
import os
from unittest.mock import MagicMock, patch, call
from pathlib import Path

from apiops_orchestrator.adapters.outbound.files_exporter.local_file_exporter_adapter import (
    LocalFileExporterAdapter,
)
from apiops_orchestrator.adapters.outbound.files_exporter.files_exporter_exceptions import (
    FileExporterException,
    UnmappedKindException,
)


class TestLocalFileExporterAdapter:

    @pytest.fixture
    def mock_yaml_strategy(self):
        """Creates a mock strategy for YAML files."""
        return MagicMock()

    @pytest.fixture
    def adapter(self, mock_yaml_strategy):
        """
        Initializes the adapter with a mocked strategy map to avoid
        dependencies on the real FILE_EXPORTER_STRATEGIES.
        """
        strategies = {".yaml": mock_yaml_strategy}
        return LocalFileExporterAdapter(exporter_strategies=strategies)

    @patch(
        "apiops_orchestrator.adapters.outbound.files_exporter.local_file_exporter_adapter.os"
    )
    def test_export_path_creates_directory(self, mock_os, adapter):
        """
        Should verify if os.makedirs is called when the output folder does not exist.
        """
        # Arrange
        output_folder = "new_folder"
        mock_os.path.exists.return_value = False
        content = []

        # Act
        adapter.export_path(content, output_folder=output_folder)

        # Assert
        mock_os.makedirs.assert_called_once_with(output_folder)

    @patch(
        "apiops_orchestrator.adapters.outbound.files_exporter.local_file_exporter_adapter.os"
    )
    def test_export_path_directory_exists(self, mock_os, adapter):
        """
        Should NOT call os.makedirs if the directory already exists.
        """
        # Arrange
        output_folder = "existing_folder"
        mock_os.path.exists.return_value = True
        content = []

        # Act
        adapter.export_path(content, output_folder=output_folder)

        # Assert
        mock_os.makedirs.assert_not_called()

    @patch(
        "apiops_orchestrator.adapters.outbound.files_exporter.local_file_exporter_adapter.os"
    )
    def test_export_yaml_api_operations(self, mock_os, adapter, mock_yaml_strategy):
        """
        Should dynamically generate filenames for ApiOperations kind based on method and path.
        """
        # Arrange
        mock_os.path.exists.return_value = True
        output_folder = Path("output")

        content = [
            {
                "kind": "ApiOperations",
                "method": "GET",
                "path": "/users",
                "content": "op_data",
            }
        ]

        # Act
        adapter.export_path(content, output_folder=str(output_folder))

        # Assert
        # generate_filename("GET", "/users") -> "get_users.yaml"
        expected_path = output_folder / "get_users.yaml"
        mock_yaml_strategy.assert_called_once_with(expected_path, content[0])

    @patch(
        "apiops_orchestrator.adapters.outbound.files_exporter.local_file_exporter_adapter.os"
    )
    def test_export_yaml_unmapped_kind(self, mock_os, adapter):
        """
        Should raise UnmappedKindException if the 'kind' is not recognized.
        """
        # Arrange
        mock_os.path.exists.return_value = True
        content = [{"kind": "UnknownKind", "content": {}}]

        # Act & Assert
        with pytest.raises(UnmappedKindException) as exc_info:
            adapter.export_path(content)

        assert "UnknownKind" in str(exc_info.value)

    @patch(
        "apiops_orchestrator.adapters.outbound.files_exporter.local_file_exporter_adapter.os"
    )
    def test_export_yaml_strategy_exception(self, mock_os, adapter, mock_yaml_strategy):
        """
        Should capture generic exceptions during file writing and raise FileExporterException.
        """
        # Arrange
        mock_os.path.exists.return_value = True
        mock_yaml_strategy.side_effect = Exception("Disk full")
        content = [{"kind": "ApiBasicInfo", "content": {}}]

        # Act & Assert
        with pytest.raises(FileExporterException):
            adapter.export_path(content)

    # --- Tests for generate_filename helper method ---

    def test_generate_filename_simple(self, adapter):
        """Should generate a clean filename for simple paths."""
        result = adapter.generate_filename("GET", "/test")
        assert result == "get_test.yaml"

    def test_generate_filename_nested_path(self, adapter):
        """Should replace slashes with underscores."""
        result = adapter.generate_filename("POST", "/api/v1/users")
        assert result == "post_api_v1_users.yaml"

    def test_generate_filename_removes_invalid_chars(self, adapter):
        """Should remove characters invalid for Windows filenames."""
        # Chars removed by code: < > : " \ | ? *
        result = adapter.generate_filename("GET", "/test/id:123")
        # 'id:123' becomes 'id123'
        assert result == "get_test_id123.yaml"

    def test_generate_filename_strips_underscores(self, adapter):
        """Should remove leading/trailing underscores resulted from concatenation."""
        # Logic: base_name = method + path -> "get" + "/" -> "get/" -> replaced "get_"
        # Then stripped.
        result = adapter.generate_filename("GET", "/")
        assert result == "get.yaml"
