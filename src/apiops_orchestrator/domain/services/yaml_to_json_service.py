from apiops_orchestrator.domain.models.api_basic_info_model import ApiBasicInfo, ApiInfo
from apiops_orchestrator.domain.models.resources_model import (
    ResourcesList,
    Resource,
    ResourceOperationRef,
)
from apiops_orchestrator.domain.models.interceptors_model import (
    InterceptorsFile,
    Interceptor,
)
from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.domain.models.api_operations_model import Operation


class YamlToJsonService:
    def __init__(self, yamls):
        self.yaml_files = yamls

    def build_api_json(self) -> ApiFull:
        api_info = ApiInfo()
        interceptors = []
        resources = []
        operations_by_file = {}

        # --- 1️⃣ Primeiro, varremos todos os YAMLs ---
        for data in self.yaml_files:
            kind = data.get("kind")

            if kind == "ApiBasicInfo":
                parsed = ApiBasicInfo(**data)
                api_info = ApiInfo(**parsed.spec.get("api", {}))

            elif kind == "Interceptors":
                parsed = InterceptorsFile(**data)
                interceptors.extend(parsed.spec.interceptors)

            elif kind == "ApiOperations":
                # Cada operação vem de um arquivo separado (ex: get_cep_{cep}.yaml)
                ops = data.get("spec", {}).get("operation", [])
                for op_data in ops:
                    op = Operation(**op_data)

                    # 🧩 Aqui armazenamos pelo nome do arquivo (se existir)
                    # exemplo: get_cep_{cep}.yaml → serve para linkar com o resource
                    file_name = data.get("metadata", {}).get("name")
                    if not file_name:
                        # fallback se não existir metadata
                        file_name = op_data.get("file", None)
                    if file_name:
                        operations_by_file[file_name] = op

            elif kind == "ResourcesList":
                parsed = ResourcesList(**data)
                resources.extend(parsed.items)

        # --- 2️⃣ Agora, montamos os resources completos com as operations preenchidas ---
        complete_resources = []

        for resource in resources:
            full_ops = []

            for op_ref in resource.operations:
                # Buscar a operation completa pelo nome do arquivo
                if op_ref.file and op_ref.file in operations_by_file:
                    op_full = operations_by_file[op_ref.file]
                    full_ops.append(op_full)
                else:
                    # fallback se não encontrou a operation completa
                    full_ops.append(
                        Operation(
                            method=op_ref.method,
                            path=op_ref.path,
                            description=None,
                            destination=None,
                            timeout=None,
                            interceptors=[],
                        )
                    )

            complete_resources.append(
                Resource(
                    name=resource.name,
                    description=resource.description,
                    operations=full_ops,
                )
            )

        # --- 3️⃣ Montamos o objeto final ---
        return ApiFull(
            api=api_info, interceptors=interceptors, resources=complete_resources
        )
