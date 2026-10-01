import logging
import json
from pathlib import Path
from jsonschema import validate, exceptions
from apiops_orchestrator.domain.ports.local_file_importer_port import LocalFileImporterPort
from apiops_orchestrator.infrastructure.observability.logging import (
    log_duration,
    set_span_id,
    set_status,
)


class SchemaValidator:
    def __init__(self, file_importer: LocalFileImporterPort, schema_folder: Path):
        self.file_importer = file_importer
        self.schema_folder = schema_folder
        self.logger = logging.getLogger(__name__)

    def validate(self, yaml_data: dict, schema_name: str, target_path: Path):
        schema_path = self.schema_folder / schema_name
        set_span_id()
        with log_duration(__name__):
            try:
                if not self.file_importer.exists(str(schema_path)):
                    set_status("FAILURE")
                    raise FileNotFoundError(f"Schema file not found at {schema_path}")

                schema = self.file_importer.read(str(schema_path))
            except FileNotFoundError as e:
                set_status("FAILURE")
                raise FileNotFoundError(f"Schema file not found at {schema_path}: {e}")
            except Exception as e:
                set_status("FAILURE")
                raise ValueError(f"Error reading schema file {schema_path}: {e}")

            try:
                # Ensure data is JSON-compatible (e.g., convert dates to strings)
                json_compatible_data = json.loads(
                    json.dumps(yaml_data, default=str)
                )
                validate(instance=json_compatible_data, schema=schema)
            except exceptions.ValidationError as e:
                if e.validator == "type" and e.instance is None:
                    message = "Cannot be null"
                else:
                    message = e.message
                field_path = ".".join(str(p) for p in e.path)
                field_msg = f" for field '{field_path}'" if field_path else ""
                set_status("FAILURE")
                raise exceptions.ValidationError(
                    f"Schema validation failed for file {str(target_path)}{field_msg}: {message}"
                )
            return True
