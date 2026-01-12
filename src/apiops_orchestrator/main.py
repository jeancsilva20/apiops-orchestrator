import logging
import sys

from adapters.inbound.files_importer.local_file_importer_adapter import (
    LocalFileLoaderAdapter,
)
from apiops_orchestrator.adapters.outbound.files_exporter.local_file_exporter_adapter import (
    LocalFileExporterAdapter,
)
from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.domain.services.json_to_yaml_service import JsonToYamlService
from apiops_orchestrator.infrastructure.observability.logging import (
    setup_logging,
    set_default_data,
    log_duration,
    set_api_info,
    set_status,
    clear_operation_context,
)
from apiops_orchestrator.infrastructure.utils.critical_exception_handler import (
    critical_exception_handler,
)
from application.services.publisher_service import PublisherService
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort
from application.services.file_importer_service import FileImporterService
from application.services.repo_validator import RepoValidator
from application.services.schema_validator import SchemaValidator
from adapters.outbound.http.manager_api.manager_api_adapter import ManagerApiAdapter
from config.settings import Settings
from pathlib import Path
from apiops_orchestrator.application.services.conversor_service import ConversorService
from apiops_orchestrator.adapters.outbound.template_repo.api_repo_adapter import (
    ApiRepoAdapter,
)
from apiops_orchestrator.application.services.versioner_service import VersionerService
from typing import List, Dict


def validate_repository_structure(
    repo_validator: RepoValidator,
    repo_path: Path,
    settings: Settings,
    logger: logging.Logger,
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
    file_importer_service: FileImporterService,
    repo_path: Path,
    settings: Settings,
    logger: logging.Logger,
) -> List[Path]:
    """Imports all files from the artifact folder."""
    artifact_folder = repo_path / settings.API_REPO_ARTIFACTS_PATH
    try:
        files = file_importer_service.load_file_path(artifact_folder)
        # print(files)
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
    file_importer_service: FileImporterService,
    repo_path: Path,
    schema_mapping: Dict[str, str],
    logger: logging.Logger,
):
    """Validates repository files against their schemas."""
    for path, schema_name in schema_mapping.items():
        target_path = repo_path / path
        try:
            content = file_importer_service.load_file_path(target_path)
            files_to_validate = content if isinstance(content, list) else [content]

            for file_content in files_to_validate:
                validator.validate(file_content, schema_name, target_path)
                set_status("SUCCESS")
                logger.info(
                    f"OK: Validation successful for a file in '{path}' with schema '{schema_name}'"
                )
                clear_operation_context()

        except FileNotFoundError as e:
            set_status("FAILURE")
            clear_operation_context()
            raise Exception(f"File not found. Path: {target_path}", e)


def generate_api_json(
    file_importer_service: FileImporterService,
    api_manager: ManagerApiPort,
    repo_path: Path,
    settings: Settings,
    logger: logging.Logger,
) -> ApiFull:
    """Generates the final API JSON from YAML files."""
    artifact_folder = repo_path / settings.API_REPO_ARTIFACTS_PATH
    files = file_importer_service.load_file_path(artifact_folder)
    service = ConversorService(files, settings, api_manager)
    result = service.build_api_json()
    set_status("SUCCESS")
    logger.info("API JSON generated successfully.")
    clear_operation_context()
    return result


def generate_yaml_files(
    final_json: ApiFull, settings: Settings, versioner_service: VersionerService
):
    local_file_adapter = LocalFileExporterAdapter()
    service = JsonToYamlService(final_json, settings, local_file_adapter)
    result = service.build_yaml_parts()
    versioner_service.version(result)


def main() -> None:
    """Main orchestration function."""
    sys.excepthook = critical_exception_handler
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
        local_file_loader_adapter = LocalFileLoaderAdapter()
        file_importer_service = FileImporterService(local_file_loader_adapter)
        api_bindings_file = file_importer_service.load_file_path(
            repo_path / "bindings.json"
        )
        metadata = api_bindings_file.get("metadata", {})
        set_api_info(
            api_bindings_file["api_id"], metadata.get("customer", "Desconhecido")
        )
        schema_folder = settings.PROJECT_SRC_DIR / settings.ORCHEST_SCHEMA_FOLDER
        schema_validator = SchemaValidator(file_importer_service, schema_folder)
        manager_adapter = ManagerApiAdapter(
            token=settings.AUTHORIZATION,
            base_path="/api-manager/api/v3/",
            max_retries=3,
            api_id=settings.API_ID,
            settings=settings,
        )
        publisher_service = PublisherService(manager_adapter)
        repo_adapter = ApiRepoAdapter()
        local_file_exporter_adapter = LocalFileExporterAdapter()
        versioner_service = VersionerService(
            manager_adapter, repo_adapter, settings
        )

        schema_mapping = {
            "artifacts/templates/api-basic-info.yaml": "api-basic-info.schema.json",
            "artifacts/templates/default-interceptors.yaml": "mag-default-interceptors.schema.json",
            # "artifacts/Resources/resources.yaml": "api-resources.schema.json",
        }

        logger.info("Step 1: Validating Repository Structure")
        validate_repository_structure(repo_validator, repo_path, settings, logger)

        logger.info("Step 2: Importing Repository Files")
        import_repository_files(file_importer_service, repo_path, settings, logger)

        logger.info("Step 3: Validating Schemas")
        validate_repository_schemas(
            schema_validator, file_importer_service, repo_path, schema_mapping, logger
        )

        logger.info("Step 4: Generating API JSON from YAML files")
        final_json = generate_api_json(
            file_importer_service, manager_adapter, repo_path, settings, logger
        )

        logger.info("Step 5: POST /revisions call started")
        publisher_service.publish_changes(final_json)

        logger.info("Step 6: Convert JSON file to YAML file")
        generate_yaml_files(final_json, settings, versioner_service)

        logger.debug("POST call successfully completed")
        # print(json.dumps(publish_response, indent=2, ensure_ascii=False))

        #  logger.info(f"Revision {publish_response["id"]} created successfully")
        logger.info("Finished application")


if __name__ == "__main__":
    main()
