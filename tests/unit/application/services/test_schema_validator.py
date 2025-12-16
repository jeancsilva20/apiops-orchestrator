import pytest
from pathlib import Path
from unittest.mock import MagicMock

from apiops_orchestrator.application.services.file_import_service import (
    FileImportService,
)
from apiops_orchestrator.application.services.schema_validator import SchemaValidator
from jsonschema import exceptions

@pytest.fixture
def schema_folder(tmp_path: Path) -> Path:
    schema_dir = tmp_path / "apiops_orchestrator/domain/schemas"
    schema_dir.mkdir(parents=True)
    return schema_dir


@pytest.fixture
def file_importer_service_mock():
    return MagicMock(spec=FileImportService)


@pytest.fixture
def schema_validator(file_importer_service_mock, schema_folder):
    return SchemaValidator(
        file_importer_service=file_importer_service_mock, schema_folder=schema_folder
    )


def test_validate_success(schema_validator, file_importer_service_mock):
    schema_name = "my_schema.json"
    schema_content = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "version": {"type": "number"}},
        "required": ["name", "version"],
    }
    file_importer_service_mock.load_file_path.return_value = schema_content

    yaml_data = {"name": "my-api", "version": 1}

    assert schema_validator.validate(yaml_data, schema_name) is True


def test_validate_missing_required_property(
    schema_validator, file_importer_service_mock
):
    schema_name = "my_schema.json"
    schema_content = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "version": {"type": "number"}},
        "required": ["name", "version"],
    }
    file_importer_service_mock.load_file_path.return_value = schema_content

    yaml_data = {"name": "my-api"}  # Missing 'version'

    with pytest.raises(
        exceptions.ValidationError,
        match="Schema validation failed for file.*for field.*version.*is a required property",
    ):
        schema_validator.validate(yaml_data, schema_name)


def test_validate_invalid_type(schema_validator, file_importer_service_mock):
    schema_name = "my_schema.json"
    schema_content = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "version": {"type": "number"}},
        "required": ["name", "version"],
    }
    file_importer_service_mock.load_file_path.return_value = schema_content

    yaml_data = {"name": "my-api", "version": "1.0"}  # 'version' should be a number

    with pytest.raises(
        exceptions.ValidationError,
        match="Schema validation failed for file.*for field.*version.*is not of type.*number",
    ):
        schema_validator.validate(yaml_data, schema_name)


def test_validate_non_existent_schema(schema_validator, file_importer_service_mock):
    file_importer_service_mock.load_file_path.side_effect = Exception("File not found")
    with pytest.raises(ValueError, match="Error reading schema file"):
        schema_validator.validate({}, "non_existent_schema.json")
