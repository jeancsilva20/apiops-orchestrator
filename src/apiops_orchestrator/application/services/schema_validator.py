from pathlib import Path
from jsonschema import validate, exceptions

from apiops_orchestrator.application.services.file_import_service import (
    FileImportService,
)


class SchemaValidator:
    def __init__(self, file_importer_service: FileImportService, schema_folder: Path):
        self.file_importer_service = file_importer_service
        self.schema_folder = schema_folder

    def validate(self, yaml_data: dict, schema_name: str):
        schema_path = self.schema_folder / schema_name
        try:
            schema = self.file_importer_service.load_file_path(schema_path)
        except Exception as e:
            raise ValueError(f"Error reading schema file {schema_path}: {e}")

        try:
            validate(instance=yaml_data, schema=schema)
        except exceptions.ValidationError as e:
            field_path = ".".join(str(p) for p in e.path)
            raise ValueError(
                f"Schema validation failed for file {str(schema_path)} for field '{field_path}': {e.message}"
            )

        return True
