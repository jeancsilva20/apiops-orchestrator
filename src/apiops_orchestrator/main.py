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
import logging
from apiops_orchestrator.infrastructure.observability.logging import setup_logging, set_default_data, log_duration, set_api_info, set_status, clear_operation_context


def validate_repository_structure(
    repo_validator: RepoValidator, repo_path: Path, settings: Settings, logger: logging.Logger
):
    """Validates the artifact folder structure."""
    artifact_folder = repo_path / settings.API_REPO_ARTIFACTS_PATH
    try:
        repo_validator.validate_artifact_struct(artifact_folder)
        set_status("SUCCESS")
        clear_operation_context()
    except Exception as error:
        set_status("FAILURE")
        logger.error(f"Repository validation failed", exc_info=error)
        clear_operation_context()
        raise


def import_repository_files(
    file_importer_service: FileImportService, repo_path: Path, settings: Settings, logger: logging.Logger
) -> List[Path]:
    """Imports all files from the artifact folder."""
    artifact_folder = repo_path / settings.API_REPO_ARTIFACTS_PATH
    try:
        files = file_importer_service.load_file_path(artifact_folder)
        #print(files)
        set_status("SUCCESS")
        clear_operation_context()
        return files
    except Exception as error:
        set_status("FAILURE")
        logger.error(f"File import failed", exc_info=error)
        clear_operation_context()
        raise


def validate_repository_schemas(
    validator: SchemaValidator,
    file_importer_service: FileImportService,
    repo_path: Path,
    schema_mapping: Dict[str, str],
    logger: logging.Logger
):
    """Validates repository files against their schemas."""
    for path, schema_name in schema_mapping.items():
        target_path = repo_path / path
        try:
            content = file_importer_service.load_file_path(target_path)
            files_to_validate = content if isinstance(content, list) else [content]

            for file_content in files_to_validate:
                try:
                    validator.validate(file_content, schema_name)
                    set_status("SUCCESS")
                    logger.info(
                        f"OK: Validation successful for a file in '{path}' with schema '{schema_name}'"
                    )
                    clear_operation_context()
                except ValueError as e:
                    raise

        except Exception as e:
            set_status("FAILURE")
            logger.error(f"Error loading path {target_path}", exc_info=e, stack_info=traceback.format_exc())
            clear_operation_context()


def generate_api_json(
    file_importer_service: FileImportService,
    api_manager: PublisherPort,
    repo_path: Path,
    settings: Settings,
    logger: logging.Logger
) -> ApiFull:
    """Generates the final API JSON from YAML files."""
    artifact_folder = repo_path / settings.API_REPO_ARTIFACTS_PATH
    files = file_importer_service.load_file_path(artifact_folder)
    service = YamlToJsonService(files, settings, api_manager)
    result = service.build_api_json()
    set_status("SUCCESS")
    logger.info("API JSON generated successfully.")
    clear_operation_context()
    return result


def main() -> None:
    """Main orchestration function."""
    settings = Settings()
    setup_logging()
    set_default_data()
    logger = logging.getLogger(__name__)
    logger.info("Initialized application")

    with log_duration(__name__):
        repo_path = (
            settings.PROJECT_ROOT / settings.API_REPO_FOLDER
        )  # This Path is the default for the pipeline. If you're running locally, change this Path to your local API Repository.

        repo_validator = RepoValidator(settings.ARTIFACTS_FILE_FOLDER_VALIDATION_RULES)
        local_file_adapter = LocalFileLoaderAdapter()
        file_importer_service = FileImportService(local_file_adapter)
        api_bindings_file = file_importer_service.load_file_path(repo_path / "bindings.json")
        metadata = api_bindings_file.get("metadata", {})
        set_api_info(api_bindings_file["api_id"], metadata.get("customer", "Desconhecido"))
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
            logger.info("Step 1: Validating Repository Structure")
            validate_repository_structure(repo_validator, repo_path, settings, logger)

            logger.info("Step 2: Importing Repository Files")
            import_repository_files(file_importer_service, repo_path, settings, logger)

            logger.info("Step 3: Validating Schemas")
            validate_repository_schemas(
                schema_validator, file_importer_service, repo_path, schema_mapping, logger
            )

            logger.info("Step 4: Generating API JSON from YAML files")
            final_json = generate_api_json(file_importer_service, manager_adapter, repo_path, settings, logger)

            # logger.debug("Final Result: API JSON")
            # print(json.dumps(final_json.model_dump(), indent=2, ensure_ascii=False))

            logger.info("Step 5: GET /apis/{id} call started")
            remote_api_data = publisher_service.fetch_remote_api_data()

            logger.debug("GET call successfully completed")
            # print(json.dumps(remote_api_data, indent=2, ensure_ascii=False))

            logger.info("Step 6: POST /revisions call started")
            publish_response = publisher_service.publish_changes(final_json)

            logger.debug("POST call successfully completed.")
            print(json.dumps(publish_response, indent=2, ensure_ascii=False))

            logger.info("Finished application")

        except Exception as e:
            logger.warning("An error occurred during the process")


if __name__ == "__main__":
    main()