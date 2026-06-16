import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock
from apiops_orchestrator.application.services.schema_validator import SchemaValidator
from apiops_orchestrator.domain.ports.local_file_importer_port import LocalFileImporterPort
from jsonschema import exceptions

@pytest.fixture
def schema_folder(tmp_path: Path) -> Path:
    return tmp_path / "schemas"

@pytest.fixture
def mock_importer():
    return MagicMock(spec=LocalFileImporterPort)

@pytest.fixture
def schema_validator(mock_importer, schema_folder):
    return SchemaValidator(
        file_importer=mock_importer, schema_folder=schema_folder
    )

def test_validate_success(schema_validator, mock_importer, schema_folder):
    schema_name = "my_schema.json"
    schema_path = schema_folder / schema_name
    schema_content = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "version": {"type": "number"}},
        "required": ["name", "version"],
    }
    mock_importer.exists.return_value = True
    mock_importer.read.return_value = schema_content

    yaml_data = {"name": "my-api", "version": 1}
    target_path = Path("success_file.yaml")

    assert schema_validator.validate(yaml_data, schema_name, target_path) is True
    mock_importer.exists.assert_called_once_with(str(schema_path))
    mock_importer.read.assert_called_once_with(str(schema_path))

def test_validate_missing_required_property(schema_validator, mock_importer):
    schema_name = "my_schema.json"
    schema_content = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    mock_importer.exists.return_value = True
    mock_importer.read.return_value = schema_content

    yaml_data = {}  # Missing 'name'
    target_path = Path("invalid_file.yaml")

    with pytest.raises(
            exceptions.ValidationError,
            match="Schema validation failed for file invalid_file.yaml: 'name' is a required property",
    ):
        schema_validator.validate(yaml_data, schema_name, target_path)

def test_validate_non_existent_schema(schema_validator, mock_importer):
    mock_importer.exists.return_value = False
    target_path = Path("dummy_path.yaml")

    with pytest.raises(FileNotFoundError, match="Schema file not found"):
        schema_validator.validate({}, "non_existent_schema.json", target_path)
