from adapters.inbound.files_importer.local_file_importer_adapter import (
    LocalFileLoaderAdapter,
)
from application.services.file_import_service import FileImportService
from application.services.repo_validator import RepoValidator
from application.services.schema_validator import SchemaValidator
from config.settings import Settings
from pathlib import Path
from domain.services.yaml_to_json_service import YamlToJsonService
import json


def main() -> None:
    settings = Settings()

    # ###################### #
    # Validar Pasta Artifact #
    # ###################### #
    repo_validator = RepoValidator(settings.ARTIFACTS_FILE_FOLDER_VALIDATION_RULES)

    repo_cep = Path(
        r"C:\Users\Sensedia\Downloads\Projetos\Nexus\apiops-orchestrator\api-repo-cep"
    )
    artifact_folder = repo_cep / settings.API_REPO_ARTIFACTS_PATH

    try:
        # print(f"Folder Location: {artifact_folder}")
        repo_validator.validate_artifact_struct(artifact_folder)
    except Exception as error:
        pass
        # print(error)

    # ###################### #
    # Importador de Arquivos #
    # ###################### #
    local_file_adapter = LocalFileLoaderAdapter()
    file_importer_service = FileImportService(local_file_adapter)
    try:
        files = file_importer_service.load_file_path(artifact_folder)
        # print(files)
    except Exception as error:
        pass
    # print(error)

    # ############### #
    # Validar Schemas #
    # ############### #
    schema_folder = settings.PROJECT_ROOT / settings.ORCHEST_SCHEMA_FOLDER
    validator = SchemaValidator(file_importer_service, schema_folder)

    schema_mapping = {
        "artifacts/templates/api-basic-info.yaml": "api-basic-info.schema.json",
        "artifacts/templates/default-interceptors.yaml": "mag-default-interceptors.schema.json",
        "artifacts/resources/": "api-operations.schema.json",
    }
    # Implementado assim para testes e validação, a ideia é passar isso para um orquestrador posteriormente.
    for path, schema_name in schema_mapping.items():
        target_path = repo_cep / path
        try:
            content = file_importer_service.load_file_path(target_path)
            files_to_validate = content if isinstance(content, list) else [content]

            for file_content in files_to_validate:
                try:
                    validator.validate(file_content, schema_name)
                    # print(
                    #    f"Validation successful for a file in '{path}' with schema '{schema_name}'"
                # )
                except ValueError as e:
                    pass
                # print(f"{e}")

        except Exception as e:
            print(f"Error loading path {target_path}: {e}")

    # ############ #
    # YAML TO JSON #
    # ############ #

    files = file_importer_service.load_file_path(artifact_folder)

    service = YamlToJsonService(files)
    # print(files)

    result = service.build_api_json()

    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
