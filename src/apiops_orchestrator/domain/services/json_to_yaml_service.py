import json
import logging
import os

import yaml
from pydantic import ValidationError
from typing import List, Dict, Any, Callable, Tuple

from apiops_orchestrator.domain.ports.manager_api_port import PublisherPort
from apiops_orchestrator.domain.services.yaml_to_json_exceptions import (
    InterceptorsNotFoundException,
    ResourcesListNotFoundException,
    ApiBasicInfoNotFoundException,
)
from apiops_orchestrator.domain.services.yaml_to_json_enum import YamlKind
from apiops_orchestrator.domain.models.api_partial_model import (
    ApiBasicInfo,
    ApiPartialInfo,
)
from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.domain.models.api_operations_model import Operation
from apiops_orchestrator.domain.models.interceptors_model import (
    Interceptor,
    InterceptorsFile,
)
from apiops_orchestrator.domain.models.resources_model import (
    Resource,
    ResourcesSpecList,
    ResourceSpec,
)
from apiops_orchestrator.config.settings import Settings

class JsonToYamlService:
    """
    Service to build a complete API YAML structure from a list of JSON data parts.
    """
    def __init__(self, json_full_object: ApiFull, logger: logging):
        self.json_full_object = json_full_object
        self.logger = logger

        # Keys for Dictionary Lookup via .get()
        self.KIND_KEY = "kind"
        self.KIND_API = "api"
        self.KIND_METADATA = "metadata"
        self.KIND_FILE_NAME = "fileName"
        self.KIND_SPEC = "spec"
        self.KIND_OPERATION = "operation"

    def build_yaml_parts(self) -> List[Dict[str, Any]]:
        """Orchestrates the parsing, validation, and building of the ApiFull object."""
        yaml_parts = [self._create_basic_info_part()]
        if self.json_full_object.interceptors:
            yaml_parts.append(self._create_interceptors_part())
        if self.json_full_object.resources:
            resources_part, operations_parts = self._create_resources_and_ops_parts()
            yaml_parts.append(resources_part)
            yaml_parts.extend(operations_parts)

        return yaml_parts

    def _create_basic_info_part(self) -> Dict[str, Any]:
        api_data = self._to_dict(self.json_full_object.api)
        return {self.KIND_KEY: "ApiBasicInfo", self.KIND_SPEC: {self.KIND_API: api_data}}

    def _create_interceptors_part(self) -> Dict[str, Any]:
        """Creates corresponding dictionaries as YamlKind.INTERCEPTORS"""
        interceptors_list = [self._prepare_interceptor(i) for i in self.json_full_object.interceptors]

        return {
            self.KIND_KEY: "Interceptors",
            self.KIND_SPEC: {
                "interceptors": interceptors_list
            }
        }

    def _create_resources_and_ops_parts(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Generates Resources and all files for ApiOperations files.
        """
        resource_items = []
        operation_files = []

        for resource in self.json_full_object.resources:
            ops_refs = []

            for op in resource.operations:
                # 1. Generates file name
                clean_path = str(op.path).strip('/').replace('/', '-').replace('{', '').replace('}', '')
                filename = f"{op.method.lower()}-{clean_path}.yaml"

                # 2. Resource is created
                ops_refs.append({
                    "method": op.method,
                    "path": op.path,
                    "file": filename
                })

                # 3. ApiOperations is created
                op_data = self._to_dict(op)
                if 'interceptors' in op_data:
                    op_data['interceptors'] = [
                        self._prepare_interceptor(i) for i in op.interceptors
                    ]

                operation_part = {
                    self.KIND_KEY: "ApiOperations",
                    self.KIND_METADATA: {
                        self.KIND_FILE_NAME: filename,
                        "resourceName": resource.name
                    },
                    self.KIND_SPEC: {
                        self.KIND_OPERATION: [op_data]
                    }
                }
                operation_files.append(operation_part)

            #Processed resource is added to list
            resource_items.append({
                "name": resource.name,
                "description": resource.description,
                "operations": ops_refs
            })

        resources_part = {
            self.KIND_KEY: "Resources",
            "items": resource_items
        }

        return resources_part, operation_files

    # --- Helpers ---

    def _prepare_interceptor(self, interceptor_obj: Any) -> Dict[str, Any]:
        """
        If interceptor contet is a JSON string, tries to convert it back to Dict
        """
        i_dict = self._to_dict(interceptor_obj)

        # Tries to load JSON content
        if isinstance(i_dict.get('content'), str):
            try:
                i_dict['content'] = json.loads(i_dict['content'])
            except (json.JSONDecodeError, TypeError):
                pass  #Keeps as string, it´s not valid

        return i_dict

    def _to_dict(self, obj: Any) -> Dict[str, Any]:
        """Pydantic or Common Object changed to Dict recursively."""
        if hasattr(obj, 'model_dump'):  # Pydantic v2
            return obj.model_dump()
        if hasattr(obj, 'dict'):  # Pydantic v1
            return obj.dict()
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return obj

    def save_yamls_to_disk(self, yaml_parts: List[Dict[str, Any]], output_folder: str = "output_api"):
        """
        Receives a list of dictionaries and write each on their respective .yaml file
        """

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            self.logger.info(f"Pasta '{output_folder}' criada.")

        for part in yaml_parts:
            kind = part.get('kind')
            file_name = "unknown.yaml"

            if kind == 'ApiBasicInfo':
                file_name = "api-info.yaml"
            elif kind == 'Interceptors':
                file_name = "interceptors.yaml"
            elif kind == 'Resources':
                file_name = "resources.yaml"
            elif kind == 'ApiOperations':
                file_name = part.get('metadata', {}).get('fileName', 'unknown-op.yaml')

            full_path = os.path.join(output_folder, file_name)

            try:
                with open(full_path, 'w', encoding='utf-8') as f:
                    yaml.dump(part, f, sort_keys=False, allow_unicode=True, indent=2, default_flow_style=False)

                self.logger.debug(f"Salvo: {file_name}")

            except Exception as e:
                self.logger.error(f"Erro ao salvar {file_name}", exc_info=e)
