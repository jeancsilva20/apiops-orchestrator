import json
import logging
from typing import List, Dict, Any
import re

from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.application.enums.json_to_yaml_enum import JsonKind


class _YamlDocumentFactory:
    """Factory for creating standard YAML document structures."""

    @staticmethod
    def create_document(
        kind: str, spec: Dict[str, Any], api_version: str
    ) -> Dict[str, Any]:
        """Create a standard YAML document with apiVersion, kind, and spec."""
        if api_version:
            return {"apiVersion": api_version, "kind": kind, "spec": spec}
        else:
            return {"kind": kind, "spec": spec}


class JsonToYamlService:
    """
    Service to build a complete API YAML structure from a list of JSON data parts.
    """

    def __init__(
        self,
        json_full_object: ApiFull,
        settings: Settings,
    ) -> None:
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

    def build_yaml_parts(self) -> List[Dict[str, Any]]:
        yaml_parts = []

        try:
            # 1. Basic info
            yaml_parts = [self._create_api_basic_info_part()]

            # 2. All/all interceptors
            if self.json_full_object.interceptors:
                yaml_parts.append(self._create_interceptors_part())
            else:
                self.logger.debug("No interceptors found")

            # 3. Resources and Operations
            if self.json_full_object.resources:
                resources_list, operations_files = (
                    self._create_resources_and_operations_parts()
                )

                # Adds resources.yaml (because it is an object list, not a unique dict with spec)
                yaml_parts.append(
                    {
                        "apiVersion": self.settings.KIND_VERSION,
                        "kind": JsonKind.RESOURCES_LIST.value,
                        "items": resources_list,
                    }
                )

                # Adds operations files
                yaml_parts.extend(operations_files)
            else:
                self.logger.debug("No resources found")

            return yaml_parts
        except Exception as e:
            self.logger.error(f"Error building YAMLs", exc_info=e)
            raise

    def _create_api_basic_info_part(self) -> Dict[str, Any]:
        self.logger.debug("Creating API basic information part")
        try:
            api_data = self.json_full_object.api.model_dump()
            self.logger.debug("API data converted to dictionary")

            # Cleans unimportant properties
            fields_to_remove = [
                "revisions",
                "deployments",
                "creationDate",
                "id",
                "apiType",
                "apiSwaggerConfiguration",
                "lastRevision",
                "apiTags",
                "visibility",
            ]
            for field in fields_to_remove:
                api_data.pop(field, None)
            self.logger.debug(f"Removed {len(fields_to_remove)} unnecessary properties")

            spec = {
                "api": api_data,
            }

            result = _YamlDocumentFactory.create_document(
                kind=JsonKind.API_BASIC_INFO.value,
                spec=spec,
                api_version=self.settings.KIND_VERSION,
            )
            self.logger.info("Basic information YAML document created successfully")
            return result
        except Exception as e:
            self.logger.error(f"Error creating API basic information", exc_info=e)
            raise

    def _create_interceptors_part(self) -> Dict[str, Any]:
        self.logger.debug(
            f"Creating interceptors part ({len(self.json_full_object.interceptors)} total)"
        )
        try:
            interceptors_list = [
                self._prepare_interceptor(i) for i in self.json_full_object.interceptors
            ]
            self.logger.debug(
                f"All {len(interceptors_list)} interceptor(s) prepared successfully"
            )

            spec = {"interceptors": interceptors_list}
            result = _YamlDocumentFactory.create_document(
                kind=JsonKind.INTERCEPTORS.value,
                spec=spec,
                api_version=self.settings.KIND_VERSION,
            )

            self.logger.info("Interceptors YAML document created successfully")
            return result
        except Exception as e:
            self.logger.error(
                f"Error creating interceptors part: {str(e)}", exc_info=True
            )
            raise

    def _create_resources_and_operations_parts(self):
        self.logger.debug(
            f"Creating resources and operations parts for {len(self.json_full_object.resources)} resource(s)"
        )
        resources_output_list = []
        operation_files = []

        try:
            for idx, resource in enumerate(self.json_full_object.resources, 1):
                self.logger.debug(
                    f"Processing resource {idx}/{len(self.json_full_object.resources)}: {resource.name}"
                )

                # Makes sure operation will be searched
                ops_list = getattr(resource, "operations", [])
                self.logger.debug(
                    f"Resource '{resource.name}' contains {len(ops_list)} operation(s)"
                )

                # Create operation files and references
                ops_refs, resource_ops_files = self._create_operation_files_and_refs(
                    ops_list
                )
                operation_files.extend(resource_ops_files)

                # Create resource entry
                resource_entry = self._create_resource_entry(resource, ops_refs)
                resources_output_list.append(resource_entry)

                self.logger.debug(f"Resource '{resource.name}' processed successfully")

            self.logger.info(
                f"Resource and operations creation completed: {len(operation_files)} operation(s)"
            )
            return resources_output_list, operation_files
        except Exception as e:
            self.logger.error(
                f"Error creating resources and operations: {str(e)}", exc_info=True
            )
            raise

    def _create_operation_files_and_refs(
        self, operations_list: List[Any]
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Create operation files and their references for resources.yaml.

        Returns:
            Tuple of (operation_references, operation_files)
        """
        self.logger.debug(
            f"Creating operation files and references ({len(operations_list)} operation(s))"
        )
        ops_refs = []
        operation_files = []

        try:
            for idx, op in enumerate(operations_list, 1):
                self.logger.debug(
                    f"Processing operation {idx}/{len(operations_list)}: {op.method} {op.path}"
                )

                # Prepares operation content
                op_data = op.model_dump()

                # Generates file name
                file_name = self._generate_filename(op.method, op.path)
                self.logger.debug(f"Generated file name: {file_name}")

                # Creates reference for resources.yaml
                ops_refs.append(
                    {"method": op.method, "path": op.path, "file": file_name}
                )

                # Special treatment for interceptors inside operation
                if "interceptors" in op_data:
                    num_interceptors = len(op.interceptors)
                    op_data["interceptors"] = [
                        self._prepare_interceptor(i) for i in op.interceptors
                    ]
                    self.logger.debug(
                        f"Processed {num_interceptors} interceptor(s) in operation {op.method} {op.path}"
                    )

                # Removes fields not present in individual file
                op_data.pop("id", None)

                # Creates structure of operation file
                op_spec = {"operation": [op_data]}
                operation_files.append(
                    {
                        "apiVersion": self.settings.KIND_VERSION,
                        "kind": JsonKind.API_OPERATIONS.value,
                        "metadata": {"fileName": file_name},
                        "spec": op_spec,
                    }
                )

                self.logger.debug(
                    f"Operation {op.method} {op.path} processed successfully"
                )

            self.logger.debug(
                f"Operation creation completed: {len(ops_refs)} reference(s), {len(operation_files)} file(s)"
            )
            return ops_refs, operation_files
        except Exception as e:
            self.logger.error(
                f"Error creating operation files and references", exc_info=e
            )
            raise

    def _create_resource_entry(
        self, resource: Any, ops_refs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create a resource entry for resources.yaml.

        Args:
            resource: The resource object
            ops_refs: List of operation references for this resource

        Returns:
            Resource entry dictionary
        """
        self.logger.debug(
            f"Creating resource entry: {resource.name} with {len(ops_refs)} reference(s)"
        )
        try:
            entry = {
                "name": resource.name,
                "description": getattr(resource, "description", None),
                "operations": ops_refs,
            }
            self.logger.debug(f"Resource entry '{resource.name}' created successfully")
            return entry
        except Exception as e:
            self.logger.error(
                f"Error creating resource entry '{resource.name}': {str(e)}",
                exc_info=True,
            )
            raise

    # --- Helpers ---

    def _prepare_interceptor(self, interceptor_obj: Any) -> Dict[str, Any]:
        self.logger.debug("Preparing interceptor")
        try:
            i_dict = interceptor_obj.model_dump()
            content = i_dict.get("content")
            # Tries to convert string JSON to Dict
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                    i_dict["content"] = content
                    self.logger.debug("Interceptor JSON content converted successfully")
                except (json.JSONDecodeError, TypeError) as e:
                    self.logger.debug(
                        f"Failed to convert interceptor JSON, keeping as string: {str(e)}"
                    )
                    pass

            # For "Custom" interceptors, content should be a reference to the script ID
            if i_dict.get("type") == "Custom" and isinstance(content, dict):
                if "id" in content:
                    i_dict["content"] = content["id"]
                    self.logger.debug(
                        f"Set 'Custom' interceptor content to reference ID: {i_dict['content']}"
                    )

            # If content is a numeric string like ("158"), converts it into int
            if isinstance(i_dict.get("content"), str) and i_dict["content"].isdigit():
                i_dict["content"] = int(i_dict["content"])
                self.logger.debug(
                    f"Numeric content converted to integer: {i_dict['content']}"
                )

            # print(f"i_dict after content processing: {i_dict}")

            # Removes internal fields
            i_dict.pop("parent", None)
            i_dict.pop("revision", None)
            i_dict.pop("id", None)
            i_dict.pop("idTemp", None)

            return i_dict
        except Exception as e:
            self.logger.error(f"Error preparing interceptor: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def _generate_filename(method: str, path: str) -> str:
        """
        Transforms path and method into file name
        """
        base_name = f"{str(method).lower()}{str(path).lower()}"
        clean_name = base_name.replace("/", "_")
        clean_name = re.sub(r'[<>:"\\|?*]', "", clean_name)
        # Removes duplicated underscores in beginning or end after concatenation
        clean_name = clean_name.strip("_")

        return f"{clean_name}.yaml"
