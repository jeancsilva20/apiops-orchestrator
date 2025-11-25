from adapters.inbound.files_importer.local_file_importer_adapter import (
    LocalFileLoaderAdapter,
)
from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.domain.ports.manager_api_port import PublisherPort
from application.services.file_import_service import FileImportService
from application.services.repo_validator import RepoValidator
from application.services.schema_validator import SchemaValidator
from application.services.publisher_service import PublisherService
from adapters.outbound.http.manager_api.manager_api_adapter import ManagerApiAdapter
from config.settings import Settings
from pathlib import Path
from domain.services.yaml_to_json_service import YamlToJsonService
import json
from typing import List, Dict
import traceback


def _print_step(step_name: str):
    """Prints a formatted step name."""
    print("\n" + "=" * 20)
    print(f" {step_name}")
    print("=" * 20 + "\n")


def validate_repository_structure(
    repo_validator: RepoValidator, repo_path: Path, settings: Settings
):
    """Validates the artifact folder structure."""
    _print_step("Step 1: Validating Repository Structure")
    artifact_folder = repo_path / settings.API_REPO_ARTIFACTS_PATH
    try:
        print(f"Validating folder: {artifact_folder}")
        repo_validator.validate_artifact_struct(artifact_folder)
        print("Repository structure validation successful.")
    except Exception as error:
        print(f"Repository structure validation failed: {error}")
        raise


def import_repository_files(
    file_importer_service: FileImportService, repo_path: Path, settings: Settings
) -> List[Path]:
    """Imports all files from the artifact folder."""
    _print_step("Step 2: Importing Repository Files")
    artifact_folder = repo_path / settings.API_REPO_ARTIFACTS_PATH
    try:
        files = file_importer_service.load_file_path(artifact_folder)
        print(files)
        print(f"Found {len(files)} files in {artifact_folder}")
        return files
    except Exception as error:
        print(f"File import failed: {error}")
        raise


def validate_repository_schemas(
    validator: SchemaValidator,
    file_importer_service: FileImportService,
    repo_path: Path,
    schema_mapping: Dict[str, str],
):
    """Validates repository files against their schemas."""
    _print_step("Step 3: Validating Schemas")
    for path, schema_name in schema_mapping.items():
        target_path = repo_path / path
        try:
            content = file_importer_service.load_file_path(target_path)
            files_to_validate = content if isinstance(content, list) else [content]

            for file_content in files_to_validate:
                try:
                    validator.validate(file_content, schema_name)
                    print(
                        f"OK: Validation successful for a file in '{path}' with schema '{schema_name}'"
                    )
                except ValueError as e:
                    print(f"ERROR: {e}")

        except Exception as e:
            print(f"ERROR: Error loading path {target_path}: {e}")
            print(traceback.format_exc())


def generate_api_json(
    file_importer_service: FileImportService,
    api_manager: PublisherPort,
    repo_path: Path,
    settings: Settings,
) -> ApiFull:
    """Generates the final API JSON from YAML files."""
    _print_step("Step 4: Generating API JSON from YAML files")
    artifact_folder = repo_path / settings.API_REPO_ARTIFACTS_PATH
    files = file_importer_service.load_file_path(artifact_folder)
    service = YamlToJsonService(files, settings, api_manager)
    result = service.build_api_json()
    print("API JSON generated successfully.")
    return result


def main() -> None:
    """Main orchestration function."""
    settings = Settings()
    repo_path = (
        settings.PROJECT_ROOT / settings.API_REPO_FOLDER
    )  # This Path is the default for the pipeline. If you're running locally, change this Path to your local API Repository.

    repo_validator = RepoValidator(settings.ARTIFACTS_FILE_FOLDER_VALIDATION_RULES)
    local_file_adapter = LocalFileLoaderAdapter()
    file_importer_service = FileImportService(local_file_adapter)
    schema_folder = settings.PROJECT_SRC_DIR / settings.ORCHEST_SCHEMA_FOLDER
    schema_validator = SchemaValidator(file_importer_service, schema_folder)
    manager_adapter = ManagerApiAdapter(
        token=settings.AUTHORIZATION,
        base_path="/api-manager/api/v3/",
        max_retries=3,
        api_id=settings.API_ID,
        settings=settings
    )
    publisher_service = PublisherService(manager_adapter)

    schema_mapping = {
        "artifacts/templates/api-basic-info.yaml": "api-basic-info.schema.json",
        "artifacts/templates/default-interceptors.yaml": "mag-default-interceptors.schema.json",
        "artifacts/resources/": "api-operations.schema.json",
    }

    try:
        validate_repository_structure(repo_validator, repo_path, settings)

        import_repository_files(file_importer_service, repo_path, settings)

        validate_repository_schemas(
            schema_validator, file_importer_service, repo_path, schema_mapping
        )

        final_json = generate_api_json(file_importer_service, manager_adapter, repo_path, settings)

        _print_step("Final Result: API JSON")
        print(json.dumps(final_json.model_dump(), indent=2, ensure_ascii=False))

        _print_step("Step 5: GET /apis/{id} call started")
        remote_api_data = publisher_service.fetch_remote_api_data()

        print("GET call successfully completed.")
        print(json.dumps(remote_api_data, indent=2, ensure_ascii=False))

    except Exception as e:
        print("\n" + "!" * 20)
        print(" An error occurred during the process:")
        print(f" {e}")
        print("!" * 20)


if __name__ == "__main__":
    main()