import json
import logging
import os
import re
from typing import List, Dict, Any, Tuple

import yaml

from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.domain.services.json_to_yaml_enum import JsonKind



class JsonToYamlService:
    """
    Service to build a complete API YAML structure from a list of JSON data parts.
    """
    def __init__(self, json_full_object: ApiFull, settings: Settings):
        self.json_full_object = json_full_object
        self.logger = logging.getLogger(__name__)
        self.settings = settings

        # Keys for Dictionary Lookup via .get()
        self.KIND_KEY = "kind"
        self.KIND_API = "api"
        self.KIND_METADATA = "metadata"
        self.KIND_FILE_NAME = "fileName"
        self.KIND_SPEC = "spec"
        self.KIND_OPERATION = "operation"

    def _generate_filename(self, method: str, path: str) -> str:
        """
        Transforms path and method into file name
        """
        base_name = f"{str(method).lower()}{str(path).lower()}"
        clean_name = base_name.replace('/', '_')
        clean_name = re.sub(r'[<>:"\\|?*]', '', clean_name)
        # Removes duplicated underscores in beginning or end after concatenation
        clean_name = clean_name.strip('_')

        return f"{clean_name}.yaml"

    def _build_yaml_parts(self) -> List[Dict[str, Any]]:
        # 1. Basic info
        yaml_parts = [self._create_basic_info_part()]

        # 2. All/all interceptors
        if self.json_full_object.interceptors:
            yaml_parts.append(self._create_interceptors_part())

        # 3. Resources and Operations
        if self.json_full_object.resources:
            resources_list, operations_files = self._create_resources_and_ops_parts()

            # Adds resources.yaml (because it is a object list, not a unique dict with spec)
            yaml_parts.append({
                "kind": JsonKind.RESOURCES.value(),
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

        return {
            "apiVersion": "api-management.sensedia.com/v1",
            "kind": "ApiBasicInfo",
            "spec": {
                "api": api_data,
                "revision": {
                    "workflowId": self.settings.WORKFLOW_ID,
                    "workflowStageId": self.settings.WORKFLOW_STAGE_ID
                }
            }
        }

    def _create_interceptors_part(self) -> Dict[str, Any]:
        interceptors_list = [self._prepare_interceptor(i) for i in self.json_full_object.interceptors]
        return {
            "apiVersion": "api-management.sensedia.com/v1",
            "kind": "Interceptors",
            "spec": {"interceptors": interceptors_list}
        }

    def _create_resources_and_ops_parts(self):
        resources_output_list = []
        operation_files = []

        for resource in self.json_full_object.resources:
            ops_refs = []

            # Makes sure operation will be searched
            ops_list = getattr(resource, 'operations', [])

            for op in ops_list:
                # Generates file name
                file_name = self._generate_filename(op.method, op.path)

                # Creates reference for resources.yaml
                ops_refs.append({
                    "id": getattr(op, 'id', None),
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
                operation_files.append({
                    "kind": "ApiOperations",
                    "method": op.method,
                    "path": op.path,
                    "content": {
                        "apiVersion": "api-management.sensedia.com/v1",
                        "kind": "ApiOperations",
                        "spec": {
                            "operation": [op_data]
                        }
                    }
                })

            # Adds entry for resources.yaml
            resources_output_list.append({
                "apiVersion": "api-management.sensedia.com/v1",
                "kind": "Resources",
                "id": getattr(resource, 'id', None),
                "name": resource.name,
                "description": getattr(resource, 'description', None),
                "operations": ops_refs
            })

        return resources_output_list, operation_files

    # --- Helpers ---

    def _prepare_interceptor(self, interceptor_obj: Any) -> Dict[str, Any]:
        i_dict = self._to_dict(interceptor_obj)
        content = i_dict.get('content')

        # Tenta converter string JSON para Dict (para ficar bonito no YAML)
        if isinstance(content, str):
            try:
                i_dict['content'] = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                # Se falhar, mantém como string (pode ser o ID '158' como string)
                pass

        # Se content for string numérica ("158"), converte para int
        if isinstance(i_dict.get('content'), str) and i_dict['content'].isdigit():
            i_dict['content'] = int(i_dict['content'])

        # Removes internal fields
        i_dict.pop('parent', None)
        i_dict.pop('revision', None)

        return i_dict

    def _to_dict(self, obj: Any) -> Any:
        if isinstance(obj, list): return [self._to_dict(i) for i in obj]
        if isinstance(obj, dict): return {k: self._to_dict(v) for k, v in obj.items()}
        if hasattr(obj, '__dict__'): return self._to_dict(obj.__dict__)
        return obj

    def save_to_disk(self, output_folder="output_yaml"):
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        parts = self._build_yaml_parts()
        print(f"Escrevendo em: {output_folder}/")

        for part in parts:
            kind = part.get('kind')
            content = part.get('content')
            file_name = None

            # Determine filename based on kind
            if kind == 'ApiBasicInfo':
                file_name = "api-basic-info.yaml"
                content = part  # For ApiBasicInfo, the part itself is the content
            elif kind == 'Interceptors':
                file_name = "default-interceptors.yaml"
                content = part  # For Interceptors, the part itself is the content
            elif kind == 'Resources':
                file_name = "resources.yaml"
                # content is already set from part.get('content')
            elif kind == 'ApiOperations':
                method = part.get('method')
                path = part.get('path')
                file_name = self._generate_filename(method, path)
                # content is already set from part.get('content')
            elif kind == 'Deployment':
                file_name = "deployment.yaml"
                content = part  # For Deployment, the part itself is the content
            else:
                self.logger.warning(f"Unknown kind: {kind}. Skipping this part.")
                continue

            if not file_name:
                self.logger.warning(f"Could not determine filename for kind: {kind}. Skipping.")
                continue

            full_path = os.path.join(output_folder, file_name)

            with open(full_path, 'w', encoding='utf-8') as f:
                yaml.dump(content, f, sort_keys=False, allow_unicode=True, indent=2, default_flow_style=False)
