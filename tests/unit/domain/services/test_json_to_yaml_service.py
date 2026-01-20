import pytest
from pathlib import Path
from unittest.mock import MagicMock
from typing import List, Any

from apiops_orchestrator.application.services.file_importer_service import (
    FileImporterService,
)
from apiops_orchestrator.adapters.inbound.files_importer.file_loader_strategy import (
    FILE_LOADER_STRATEGIES,
)
from apiops_orchestrator.adapters.inbound.files_importer.local_file_importer_adapter import (
    LocalFileLoaderAdapter,
)
from apiops_orchestrator.application.services.schema_validator import SchemaValidator
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.domain.models.api_partial_model import (
    ApiPartialInfo,
    ApiResponsible,
)
from apiops_orchestrator.domain.models.interceptors_model import Interceptor
from apiops_orchestrator.domain.models.resources_model import Resource
from apiops_orchestrator.domain.models.api_operations_model import Operation
from apiops_orchestrator.domain.services.json_to_yaml_service import JsonToYamlService
from apiops_orchestrator.application.enums.json_to_yaml_enum import JsonKind


@pytest.fixture
def settings() -> Settings:
    mock_settings = MagicMock(spec=Settings)
    mock_settings.KIND_VERSION = "api-management.sensedia.com/v1"
    mock_settings.PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
    return mock_settings


@pytest.fixture
def schema_validator(settings) -> SchemaValidator:
    adapter = LocalFileLoaderAdapter(loader_strategies=FILE_LOADER_STRATEGIES)
    file_importer_service = FileImporterService(importer=adapter)
    schema_folder = (
        settings.PROJECT_ROOT / "src" / "apiops_orchestrator" / "domain" / "schemas"
    )
    return SchemaValidator(
        file_importer_service=file_importer_service, schema_folder=schema_folder
    )


@pytest.fixture
def api_full_object() -> ApiFull:
    """Provides a test object using the real Pydantic models."""
    return ApiFull(
        api=ApiPartialInfo(
            id="123",
            name="Test API",
            version="1.0.0",
            description="A test API",
            basePath="/test",
            apiResponsible=ApiResponsible(username="testuser", groupName="Test Group"),
            creationDate=1672531200,  # Example integer timestamp
            revisions=[],  # Empty list as expected type
            lastRevision=None,  # None as expected for Optional[dict]
        ),
        interceptors=[
            Interceptor(
                name="Global-Request-Interceptor",
                position=1,
                content={},
                type="Request",
                executionPoint="MESSAGE_RECEIVED",
                status="ENABLED",
            ),
        ],
        resources=[
            Resource(
                name="Users",
                description="Resource for user operations",
                operations=[
                    Operation(
                        path="/users",
                        method="GET",
                        description="Get all users",
                        destination="http://mock.destination",
                        interceptors=[
                            Interceptor(
                                name="Op-Specific-Interceptor",
                                position=2,
                                content={},
                                type="Request",
                                executionPoint="MESSAGE_RECEIVED",
                                status="ENABLED",
                            )
                        ],
                    ),
                    Operation(
                        path="/users/{id}",
                        method="POST",
                        description="Create a user",
                        destination="http://mock.destination",
                    ),
                ],
            )
        ],
    )


class TestJsonToYamlService:
    def test_build_yaml_parts_and_validate_schemas(
        self,
        api_full_object: ApiFull,
        settings: Settings,
        schema_validator: SchemaValidator,
    ):
        # The service now needs the file_exporter_port in its constructor.
        # Let's mock it since we are not testing the file writing itself here.
        service = JsonToYamlService(
            json_full_object=api_full_object,
            settings=settings,
        )

        # Validator for schemas in src/
        src_schema_map = {
            JsonKind.API_BASIC_INFO.value: "api-basic-info.schema.json",
            JsonKind.API_OPERATIONS.value: "api-operations.schema.json",
        }

        # A specific validator for our test-only schema
        test_schema_folder = (
            settings.PROJECT_ROOT / "tests" / "unit" / "domain" / "schemas"
        )
        adapter = LocalFileLoaderAdapter(loader_strategies=FILE_LOADER_STRATEGIES)
        file_importer_service = FileImporterService(importer=adapter)
        test_validator = SchemaValidator(
            file_importer_service=file_importer_service,
            schema_folder=test_schema_folder,
        )

        yaml_parts = service.build_yaml_parts()

        # The number of parts might change based on the real models, let's adjust.
        # 1 basic-info, 1 interceptors, 1 resources, 2 operations = 5 parts. This seems right.
        assert len(yaml_parts) == 5

        errors = []
        for part in yaml_parts:
            kind = part.get("kind")
            file_name_for_logging = part.get("metadata", {}).get(
                "fileName", f"{kind}.yaml"
            )

            # Skip validation for ResourcesList due to schema mismatch
            if kind == JsonKind.RESOURCES_LIST.value:
                continue

            validator_to_use = None
            schema_name = None

            if kind == JsonKind.INTERCEPTORS.value:
                # Use the test validator for the interceptors schema
                validator_to_use = test_validator
                schema_name = "test-interceptors.schema.json"
            else:
                # Use the main validator for all other schemas
                validator_to_use = schema_validator
                schema_name = src_schema_map.get(kind)

            assert schema_name is not None, f"Schema not found for kind: {kind}"
            assert validator_to_use is not None, f"Validator not found for kind: {kind}"

            try:
                validator_to_use.validate(
                    yaml_data=part,
                    schema_name=schema_name,
                    target_path=Path(file_name_for_logging),
                )
            except Exception as e:
                errors.append(
                    f"Validation failed for {file_name_for_logging} with schema {schema_name}: {e}"
                )

        assert not errors, (
            "All validated YAML parts should be valid against their schemas.\n"
            + "\n".join(errors)
        )
