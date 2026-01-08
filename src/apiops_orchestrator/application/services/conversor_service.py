import json
from pydantic import ValidationError
from typing import List, Dict, Any, Callable

from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort
from apiops_orchestrator.application.exceptions.yaml_to_json_exceptions import (
    InterceptorsNotFoundException,
    ResourcesListNotFoundException,
    ApiBasicInfoNotFoundException,
)
from apiops_orchestrator.application.enums.yaml_to_json_enum import YamlKind
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


class ConversorService:
    """
    Service to build a complete API JSON structure from a list of YAML data parts.
    """

    def __init__(self, yamls: List[Dict[str, Any]], settings: Settings, manager_api: ManagerApiPort):
        self.yamls = yamls
        self.settings = settings
        self.manager_api = manager_api

        self._api_partial_info: ApiPartialInfo | None = None
        self._interceptors: list[Interceptor] = []
        self._operations_by_file: dict[str, Operation] = {}
        self._resource_specs: list[ResourceSpec] = []

        # Maps kinds to processing methods
        self._parsers: Dict[YamlKind, Callable[[Dict[str, Any]], None]] = {
            YamlKind.API_BASIC_INFO: self._process_api_basic_info,
            YamlKind.INTERCEPTORS: self._process_interceptors_file,
            YamlKind.API_OPERATIONS: self._process_api_operations,
            YamlKind.RESOURCES_LIST: self._process_resources_list,
        }

        # Keys for Dictionary Lookup via .get()
        self.KIND_KEY = "kind"
        self.KIND_API = "api"
        self.KIND_METADATA = "metadata"
        self.KIND_FILE_NAME = "fileName"
        self.KIND_SPEC = "spec"
        self.KIND_OPERATION = "operation"

    def build_api_json(self) -> ApiFull:
        """Orchestrates the parsing, validation, and building of the ApiFull object."""
        try:
            for data in self.yamls:
                kind_str = data.get(self.KIND_KEY)
                if not kind_str:
                    raise ValueError(f"Kind field is required: {data}")

                kind_value = YamlKind(kind_str)
                parser = self._parsers.get(kind_value)
                if parser:
                    parser(data)

            self._validate_presence_of_required_parts()

            final_resources = self._build_final_resources()

            api_full = ApiFull(
                api=self._api_partial_info,
                interceptors=self._interceptors,
                resources=final_resources,
                workflowId=self.settings.WORKFLOW_ID,
                workflowStageId=self.settings.WORKFLOW_STAGE_ID,
            )

            self._escape_interceptors_content(api_full, self.manager_api)
            return api_full

        except ValidationError as e:
            errors = []
            for error in e.errors():
                field = ".".join(str(x) for x in error["loc"])
                message = error["msg"]
                errors.append(f"- {field}: {message}")

            formatted_error = "\n".join(errors)
            raise ValueError(f"YAML content validation failed:\n{formatted_error}") from e
        except (
            ValueError,
            KeyError,
            ApiBasicInfoNotFoundException,
            ResourcesListNotFoundException,
            InterceptorsNotFoundException,
        ) as e:
            # Catch specific, expected errors and re-raise
            raise e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred while building the API JSON: {e}"
            ) from e

    # --- Private Processing Methods ---

    def _process_api_basic_info(self, data: Dict[str, Any]):
        if self._api_partial_info is not None:
            raise ValueError("Multiple ApiBasicInfo found. Only one is allowed.")
        parsed = ApiBasicInfo(**data)
        self._api_partial_info = ApiPartialInfo(
            **parsed.spec.get(self.KIND_API, {}),
            id=self.settings.API_ID,
            apiTags=self.settings.api_tags,
        )

    def _process_interceptors_file(self, data: Dict[str, Any]):
        parsed = InterceptorsFile(**data)
        self._interceptors.extend(parsed.spec.interceptors)

    def _process_api_operations(self, data: Dict[str, Any]):
        file_name = data.get(self.KIND_METADATA, {}).get(self.KIND_FILE_NAME)
        if not file_name:
            raise ValueError("ApiOperations must have metadata with a fileName.")
        if file_name in self._operations_by_file:
            raise ValueError(f"Duplicate ApiOperations fileName: {file_name}")

        for op_data in data.get(self.KIND_SPEC, {}).get(self.KIND_OPERATION, []):
            operation = Operation(**op_data)
            self._operations_by_file[file_name] = operation

    def _process_resources_list(self, data: Dict[str, Any]):
        parsed = ResourcesSpecList(**data)
        self._resource_specs.extend(parsed.items)

    def _validate_presence_of_required_parts(self):
        if self._api_partial_info is None:
            raise ApiBasicInfoNotFoundException()
        if not self._resource_specs:
            raise ResourcesListNotFoundException()
        if not self._interceptors:
            raise InterceptorsNotFoundException()

    def _build_final_resources(self) -> list[Resource]:
        final_resources = []
        for spec in self._resource_specs:
            enriched_operations = []
            for op_spec in spec.operations:
                op_file = op_spec.file
                if not op_file or op_file not in self._operations_by_file:
                    raise ValueError(
                        f"ApiOperation file '{op_file}' not found for resource '{spec.name}'."
                    )

                rich_operation = self._operations_by_file[op_file]

                # Validate consistency between resource and operation
                if (
                    rich_operation.method != op_spec.method
                    or rich_operation.path != op_spec.path
                ):
                    raise ValueError(
                        f"Operation mismatch in '{op_file}' for resource '{spec.name}'. "
                        f"Resource expects '{op_spec.method} {op_spec.path}', "
                        f"but file provides '{rich_operation.method} {rich_operation.path}'."
                    )
                enriched_operations.append(rich_operation)

            final_resources.append(
                Resource(
                    name=spec.name,
                    description=spec.description,
                    operations=enriched_operations,
                )
            )
        return final_resources

    @staticmethod
    def _escape_interceptors_content(api_full: ApiFull, manager_api: ManagerApiPort):
        """
        Instance method to escape the content of non-custom interceptors.
        This method mutates the ApiFull object.
        """
        all_interceptors = api_full.interceptors + [
            interceptor
            for r in api_full.resources
            for o in r.operations
            for interceptor in o.interceptors
        ]
        for interceptor in all_interceptors:
            if interceptor.type.lower() != "custom" and isinstance(
                interceptor.content, dict
            ):
                interceptor.content = json.dumps(interceptor.content)
            else:
                interceptor.content = json.dumps(manager_api.get_custom_interceptor_by_id(interceptor.content))
