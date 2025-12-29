import logging
from pathlib import Path
from jsonschema import validate, exceptions
from apiops_orchestrator.application.services.file_importer_service import (
    FileImporterService,
)
from apiops_orchestrator.infrastructure.observability.logging import log_duration, set_span_id, clear_operation_context, set_status



class SchemaValidator:
    def __init__(self, file_importer_service: FileImporterService, schema_folder: Path):
        self.file_importer_service = file_importer_service
        self.schema_folder = schema_folder
        self.logger = logging.getLogger(__name__)

    def validate(self, yaml_data: dict, schema_name: str, target_path: Path):
        schema_path = self.schema_folder / schema_name
        set_span_id()
        with log_duration(__name__):
            try:
                schema = self.file_importer_service.load_file_path(schema_path)
            except FileNotFoundError as e:
                set_status("FAILURE")
                raise FileNotFoundError(f"Schema file not found at {schema_path}: {e}")
            except Exception as e:
                set_status("FAILURE")
                raise ValueError(f"Error reading schema file {schema_path}: {e}")

            try:
                validate(instance=yaml_data, schema=schema)
            except exceptions.ValidationError as e:
                if e.validator == "type" and e.instance is None:
                    message = "Cannot be null"
                else:
                    message = e.message
                field_path = ".".join(str(p) for p in e.path)
                set_status("FAILURE")
                raise exceptions.ValidationError(
                    f"Schema validation failed for file {str(target_path)} {f"for field '{field_path}'" if field_path else ""}: {message}"
                )
            return True
