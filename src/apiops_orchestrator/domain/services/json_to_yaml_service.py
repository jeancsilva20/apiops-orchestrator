import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import List, Dict, Any
from uuid import UUID

import yaml

from apiops_orchestrator.adapters.outbound.files_exporter.local_file_exporter_adapter import LocalFileExporterAdapter
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.domain.services.json_to_yaml_enum import JsonKind


class _YamlDocumentFactory:
    """Factory for creating standard YAML document structures."""

    @staticmethod
    def create_document(
        kind: str,
        spec: Dict[str, Any],
        version: str
    ) -> Dict[str, Any]:
        """Create a standard YAML document with apiVersion, kind, and spec."""
        return {
            "apiVersion": version,
            "kind": kind,
            "spec": spec
        }

class JsonToYamlService:
    """
    Service to build a complete API YAML structure from a list of JSON data parts.
    """
    def __init__(self, json_full_object: ApiFull, settings: Settings, local_file_exporter: LocalFileExporterAdapter) -> None:
        self.json_full_object = json_full_object
        self.logger = logging.getLogger(__name__)
        self.settings = settings
        self.local_file_exporter = local_file_exporter

        # Keys for Dictionary Lookup via .get()
        self.KIND_KEY = "kind"
        self.KIND_API = "api"
        self.KIND_METADATA = "metadata"
        self.KIND_FILE_NAME = "fileName"
        self.KIND_SPEC = "spec"
        self.KIND_OPERATION = "operation"

    def build_yaml_parts(self) -> List[Dict[str, Any]]:
        # 1. Basic info
        yaml_parts = [self._create_basic_info_part()]

        # 2. All/all interceptors
        if self.json_full_object.interceptors:
            yaml_parts.append(self._create_interceptors_part())

        # 3. Resources and Operations
        if self.json_full_object.resources:
            resources_list, operations_files = self._create_resources_and_ops_parts()

            # Adds resources.yaml (because it is an object list, not a unique dict with spec)
            yaml_parts.append({
                "kind": JsonKind.RESOURCES.value,
                "content": resources_list
            })

            # Adds operations files
            yaml_parts.extend(operations_files)

        return yaml_parts

    def _create_basic_info_part(self) -> Dict[str, Any]:
        api_data = self._to_dict(self.json_full_object.api)
        # Cleans unimportant properties
        for field in ['revisions', 'deployments', 'creationDate', 'id', 'apiType', 'apiSwaggerConfiguration', 'lastRevision']:
            api_data.pop(field, None)

        spec = {
            "api": api_data,
            "revision": {
                "workflowId": self.settings.WORKFLOW_ID,
                "workflowStageId": self.settings.WORKFLOW_STAGE_ID
            }
        }

        return _YamlDocumentFactory.create_document(
            kind=JsonKind.API_BASIC_INFO.value,
            spec=spec,
            version=self.settings.VERSION
        )

    def _create_interceptors_part(self) -> Dict[str, Any]:
        interceptors_list = [self._prepare_interceptor(i) for i in self.json_full_object.interceptors]
        spec = {"interceptors": interceptors_list}
        return _YamlDocumentFactory.create_document(
            kind=JsonKind.INTERCEPTORS.value,
            spec=spec,
            version=self.settings.VERSION
        )

    def _create_resources_and_ops_parts(self):
        resources_output_list = []
        operation_files = []

        for resource in self.json_full_object.resources:
            ops_refs = []

            # Makes sure operation will be searched
            ops_list = getattr(resource, 'operations', [])

            for op in ops_list:
                # Generates file name
                file_name = self.local_file_exporter.generate_filename(op.method, op.path)

                # Creates reference for resources.yaml
                ops_refs.append({
                    "method": op.method,
                    "path": op.path,
                    "file": file_name
                })

                # Prepares operation content
                op_data = self._to_dict(op)

                # Special treatment for interceptors inside operation
                if 'interceptors' in op_data:
                    op_data['interceptors'] = [
                        self._prepare_interceptor(i) for i in op.interceptors
                    ]

                # Removes fields not present in individual file
                op_data.pop('id', None)

                # Creates structure of operation file
                op_spec = {"operation": [op_data]}
                operation_files.append({
                    "kind": JsonKind.API_OPERATIONS.value,
                    "method": op.method,
                    "path": op.path,
                    "content": _YamlDocumentFactory.create_document(
                        kind=JsonKind.API_OPERATIONS.value,
                        spec=op_spec,
                        version=self.settings.VERSION
                    )
                })

            # Adds entry for resources.yaml
            resources_output_list.append({
                "apiVersion": self.settings.VERSION,
                "kind": JsonKind.RESOURCES.value,
                "name": resource.name,
                "description": getattr(resource, 'description', None),
                "operations": ops_refs
            })

        return resources_output_list, operation_files

    # --- Helpers ---

    def _prepare_interceptor(self, interceptor_obj: Any) -> Dict[str, Any]:
        i_dict = self._to_dict(interceptor_obj)
        content = i_dict.get('content')

        # Tries to convert string JSON to Dict
        if isinstance(content, str):
            try:
                i_dict['content'] = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                # If it fails, keeps the string
                pass

        # If content is a numeric string like ("158"), converts it into int
        if isinstance(i_dict.get('content'), str) and i_dict['content'].isdigit():
            i_dict['content'] = int(i_dict['content'])

        # Removes internal fields
        i_dict.pop('parent', None)
        i_dict.pop('revision', None)

        return i_dict

    def _to_dict(self, obj: Any, _max_depth: int = 100, _current_depth: int = 0) -> Any:
        """
        Convert objects to dictionaries recursively.

        Handles:
        - Dataclasses (using asdict)
        - Lists and dicts (recursive conversion)
        - Primitives (returned as-is)
        """
        if _current_depth > _max_depth:
            self.logger.warning(f"Maximum recursion depth {_max_depth} exceeded during object conversion")
            raise RecursionError(f"Maximum recursion depth {_max_depth} exceeded")

        # Handle dataclasses (fastest path for structured data)
        if is_dataclass(obj) and not isinstance(obj, type):
            try:
                return asdict(obj)
            except Exception as e:
                self.logger.debug(f"Failed to convert dataclass using asdict: {str(e)}, falling back to __dict__")

        # Handle lists
        if isinstance(obj, list):
            return [self._to_dict(item, _max_depth, _current_depth + 1) for item in obj]

        # Handle dictionaries
        if isinstance(obj, dict):
            return {
                key: self._to_dict(value, _max_depth, _current_depth + 1)
                for key, value in obj.items()
            }

        # Return primitives as-is (str, int, float, bool, None, etc.)
        return obj

