from pydantic import ValidationError

from apiops_orchestrator.domain.models.api_basic_info_model import ApiBasicInfo, ApiInfo
from apiops_orchestrator.domain.models.resources_model import (
    ResourcesList,
    Resource,
    ResourceSpec,
    ResourceOperationRef,
)
from apiops_orchestrator.domain.models.interceptors_model import (
    InterceptorsFile,
    Interceptor,
)
from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.domain.models.api_operations_model import (
    Operation,
    ApiOperationsFile,
)


class YamlToJsonService:
    def __init__(self, yamls):
        self.yaml_files = yamls

    def build_api_json(self) -> ApiFull:
        # api_info = ApiInfo()
        interceptors: list[Interceptor] = []
        operations_by_file: dict[str, Operation] = {}
        resource_specs: list[ResourceSpec] = []

        for data in self.yaml_files:
            kind = data.get("kind")

            if kind == "ApiBasicInfo":
                parsed = ApiBasicInfo(**data)
                api_info = ApiInfo(**parsed.spec.get("api", {}))

            elif kind == "Interceptors":
                parsed = InterceptorsFile(**data)
                interceptors.extend(parsed.spec.interceptors)

            elif kind == "ApiOperations":
                file_name = data.get("metadata", {}).get("file_name", None)
                if not file_name:
                    raise Exception("ApiOperationsInfo must have metadata: file_name")

                for operation_data in data.get("spec", {}).get("operation", []):
                    print(operation_data)
                    operation = Operation(**operation_data)
                    # Use the file_name as the key
                    operations_by_file[file_name] = operation

            elif kind == "ResourcesList":
                parsed = ResourcesList(**data)
                resource_specs.extend(parsed.items)

        final_resources: list[Resource] = []

        for spec in resource_specs:
            enriched_operations: list[Operation] = []

            for operation_specs in spec.operations:
                # Use the 'file' field from the reference as the key
                if operation_specs.file and operation_specs.file in operations_by_file:
                    rich_operation = operations_by_file[operation_specs.file]

                    # Compares the method and path between the resources.yaml and operation.yaml, to guarrante error on mismatch.
                    if (
                        rich_operation.method == operation_specs.method
                        and rich_operation.path == operation_specs.path
                    ):
                        enriched_operations.append(rich_operation)
                    else:
                        print(
                            f"Warning: Mismatch for file {operation_specs.file}. Operation Reference={operation_specs.method} {operation_specs.path}, Operation File={rich_operation.method} {rich_operation.path}"
                        )
                else:
                    print(
                        f"Warning: No ApiOperation file found for {operation_specs.file}"
                    )

            final_resource = Resource(
                id=spec.id,
                name=spec.name,
                description=spec.description,
                operations=enriched_operations,
            )
            final_resources.append(final_resource)

        return ApiFull(
            api=api_info,
            interceptors=interceptors,
            resources=final_resources,
        )
