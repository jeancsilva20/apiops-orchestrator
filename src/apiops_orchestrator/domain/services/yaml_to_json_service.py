from pydantic import ValidationError

from apiops_orchestrator.domain.services.yaml_to_json_exceptions import (
    InterceptorsNotFoundException,
    ResourcesListNotFoundException,
    ApiInfoNotFoundException,
)

from apiops_orchestrator.domain.services.yaml_to_json_enum import YamlKind

from apiops_orchestrator.domain.models.api_basic_info_model import ApiBasicInfo, ApiInfo
from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.domain.models.api_operations_model import Operation
from apiops_orchestrator.domain.models.interceptors_model import (
    Interceptor,
    InterceptorsFile,
)
from apiops_orchestrator.domain.models.resources_model import (
    Resource,
    ResourcesList,
    ResourceSpec,
)


class YamlToJsonService:
    def __init__(self, yamls):
        self.yaml_files = yamls

    def build_api_json(self) -> ApiFull:
        api_info: ApiInfo | None = None
        interceptors: list[Interceptor] = []
        operations_by_file: dict[str, Operation] = {}
        resource_specs: list[ResourceSpec] = []

        try:
            for data in self.yaml_files:
                kind = data.get("kind")

                if kind == YamlKind.API_BASIC_INFO.value:
                    if api_info is not None:
                        raise ValueError(
                            "Multiple ApiBasicInfo found. Only one is allowed."
                        )
                    parsed = ApiBasicInfo(**data)
                    api_info = ApiInfo(**parsed.spec.get("api", {}))

                elif kind == YamlKind.INTERCEPTORS.value:
                    parsed = InterceptorsFile(**data)
                    interceptors.extend(parsed.spec.interceptors)

                elif kind == YamlKind.API_OPERATIONS.value:
                    file_name = data.get("metadata", {}).get("file_name")
                    if not file_name:
                        raise ValueError(
                            "ApiOperations must have metadata with a file_name."
                        )

                    if file_name in operations_by_file:
                        raise ValueError(
                            f"Duplicate ApiOperations file_name: {file_name}"
                        )

                    for operation_data in data.get("spec", {}).get("operation", []):
                        operation = Operation(**operation_data)
                        operations_by_file[file_name] = operation

                elif kind == YamlKind.RESOURCES_LIST.value:
                    parsed = ResourcesList(**data)
                    resource_specs.extend(parsed.items)

            if api_info is None:
                raise ApiInfoNotFoundException()
            if not resource_specs:
                raise ResourcesListNotFoundException()
            if not interceptors:
                raise InterceptorsNotFoundException()

            final_resources: list[Resource] = []

            for spec in resource_specs:
                enriched_operations: list[Operation] = []
                for op_spec in spec.operations:
                    op_file = op_spec.file
                    if not op_file or op_file not in operations_by_file:
                        raise ValueError(
                            f"ApiOperation file '{op_file}' not found for resource '{spec.name}'."
                        )

                    rich_operation = operations_by_file[op_file]

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
                        id=spec.id,
                        name=spec.name,
                        description=spec.description,
                        operations=enriched_operations,
                    )
                )

            return ApiFull(
                api=api_info,
                interceptors=interceptors,
                resources=final_resources,
            )

        except ValidationError as e:
            raise ValueError(f"YAML content validation failed: {e}") from e
        except (
            ValueError,
            ApiInfoNotFoundException,
            ResourcesListNotFoundException,
            InterceptorsNotFoundException,
        ) as e:
            raise e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred while building the API JSON: {e}"
            ) from e
