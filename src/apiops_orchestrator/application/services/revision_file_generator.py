import re
import yaml
from pathlib import Path

from apiops_orchestrator.application.enums.json_to_yaml_enum import (
    JsonKind,
    JsonKindFileName,
)
from apiops_orchestrator.domain.ports.api_repo_port import ApiRepoPort


class RevisionFileGenerator:
    """
    Responsible for the logic of processing API content and
    generating the revision's file structure.
    """

    def __init__(self, repo_adapter: ApiRepoPort):
        self.repo = repo_adapter

    def create_revision_files(self, api_content: list, tmp_dir_path: Path):
        """
        Processes the list of file objects and creates the corresponding YAML files
        in the correct directory structure.
        """
        resources_list_obj = next(
            (
                api_part
                for api_part in api_content
                if api_part.get("kind") == JsonKind.RESOURCES_LIST.value
            ),
            None,
        )

        for api_part in api_content:
            self._process_and_create_file(api_part, resources_list_obj, tmp_dir_path)

    def _process_and_create_file(
        self, api_part: dict, resources_list_obj: dict, tmp_dir_path: Path
    ):
        """
        Determines the file type and dispatches to the correct creation logic.
        """
        kind = api_part.get("kind")
        file_name = self._get_filename_from_object(api_part)
        file_content_str = yaml.dump(api_part, sort_keys=False)

        if kind in [JsonKind.API_BASIC_INFO.value, JsonKind.INTERCEPTORS.value]:
            destination = tmp_dir_path / "templates"
            self.repo.create_file(destination, file_name, file_content_str)

        elif kind == JsonKind.RESOURCES_LIST.value:
            destination = tmp_dir_path / "resources"
            self.repo.create_file(destination, file_name, file_content_str)

        elif kind == JsonKind.API_OPERATIONS.value:
            self._create_operation_file(
                api_part, file_name, file_content_str, resources_list_obj, tmp_dir_path
            )

    def _create_operation_file(
        self,
        api_part: dict,
        file_name: str,
        file_content_str: str,
        resources_list_obj: dict,
        tmp_dir_path: Path,
    ):
        """
        Handles the specific logic for creating an ApiOperations file, which includes
        placing it inside a folder named after its parent resource.
        """
        operation_list = api_part.get("spec", {}).get("operation", [])
        if not (
            operation_list
            and isinstance(operation_list, list)
            and len(operation_list) > 0
        ):
            raise ValueError(
                f"ApiOperations file '{file_name}' is invalid: 'spec.operation' is missing or empty."
            )

        op_path = operation_list[0].get("path")
        if not op_path:
            raise ValueError(
                f"ApiOperations file '{file_name}' is invalid: 'path' is missing in 'spec.operation'."
            )

        if not resources_list_obj:
            raise FileNotFoundError(
                "Could not process ApiOperations files because ResourcesList was not found."
            )

        resource_name = self._find_resource_name_for_operation(
            op_path, resources_list_obj
        )
        if not resource_name:
            raise ValueError(
                f"Could not find a matching resource for operation with path '{op_path}' in file '{file_name}'."
            )

        temp_name = resource_name.lower()

        # Replace spaces with hyphens. Using re.sub to handle multiple spaces.
        temp_name = re.sub(r"\s+", "-", temp_name)

        # Remove any character that is not alphanumeric or a hyphen.
        sanitized_resource_name = "".join(
            c for c in temp_name if c.isalnum() or c == "-"
        )
        sanitized_resource_name = sanitized_resource_name.strip("-")

        resource_dir_path = tmp_dir_path / "resources" / sanitized_resource_name

        try:
            if not resource_dir_path.exists():
                self.repo.create_dir(
                    tmp_dir_path / "resources", sanitized_resource_name
                )
        except FileExistsError:
            pass

        self.repo.create_file(resource_dir_path, file_name, file_content_str)

    @staticmethod
    def _find_resource_name_for_operation(
        op_path: str, resources_list_obj: dict
    ) -> str | None:
        """
        Finds the name of the resource that an operation belongs to by matching the path.
        """
        for resource in resources_list_obj.get("items", []):
            for operation in resource.get("operations", []):
                if op_path == operation.get("path"):
                    return resource.get("name")
        return None

    @staticmethod
    def _get_filename_from_object(file_obj: dict) -> str:
        """
        Determines the filename for a given file object based on its kind and metadata.
        """
        kind = file_obj.get("kind")
        if kind == JsonKind.API_BASIC_INFO.value:
            return JsonKindFileName.API_BASIC_INFO.value
        if kind == JsonKind.INTERCEPTORS.value:
            return JsonKindFileName.INTERCEPTORS.value
        if kind == JsonKind.RESOURCES_LIST.value:
            return JsonKindFileName.RESOURCES.value
        if kind == JsonKind.API_OPERATIONS.value:
            filename = file_obj.get("metadata", {}).get("fileName")
            if filename:
                return filename

        raise ValueError(f"Could not determine filename for object with kind '{kind}'.")
