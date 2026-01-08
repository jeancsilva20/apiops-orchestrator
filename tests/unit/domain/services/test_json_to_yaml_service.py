import pytest
from pathlib import Path
from unittest.mock import MagicMock
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

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
from apiops_orchestrator.domain.ports.file_exporter_port import PathExporterPort
from apiops_orchestrator.domain.services.json_to_yaml_service import JsonToYamlService
from apiops_orchestrator.domain.services.json_to_yaml_enum import JsonKind


# Mock Data Structures that mimic the real Pydantic models
@dataclass
class MockApiResponsible:
    username: str
    groupName: str


@dataclass
class MockInterceptor:
    name: str
    type: str = "Request"
    flow: str = "Pre"
    script: str = "console.log('test');"
    content: Dict[str, Any] = field(default_factory=dict)
    parent: Optional[Any] = None
    revision: Optional[Any] = None
    id: Optional[str] = None
    idTemp: Optional[str] = None
    position: int = 1
    executionPoint: str = "MESSAGE_RECEIVED"
    status: str = "ENABLED"


@dataclass
class MockOperation:
    path: str
    method: str
    description: str
    destination: str = "http://mock.destination"
    interceptors: List[MockInterceptor] = field(default_factory=list)
    id: Optional[str] = None


@dataclass
class MockResource:
    name: str
    description: str
    operations: List[MockOperation] = field(default_factory=list)


@dataclass
class MockApiPartialInfo:
    id: str
    name: str
    version: str
    description: str
    basePath: str
    apiResponsible: MockApiResponsible = field(
        default_factory=lambda: MockApiResponsible(
            username="testuser", groupName="Test Group"
        )
    )
    revisions: List[Any] = field(default_factory=list)
    deployments: List[Any] = field(default_factory=list)
    creationDate: int = 1672531200
    apiType: str = "STANDARD"
    apiSwaggerConfiguration: Optional[Any] = None
    lastRevision: Optional[Any] = None
    apiTags: List[str] = field(default_factory=list)
    visibility: Optional[Any] = None


@dataclass
class MockApiFull:
    api: MockApiPartialInfo
    interceptors: List[MockInterceptor] = field(default_factory=list)
    resources: List[MockResource] = field(default_factory=list)


@pytest.fixture
def settings() -> Settings:
    mock_settings = MagicMock(spec=Settings)
    mock_settings.KIND_VERSION = "api-management.sensedia.com/v1"
    mock_settings.PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
    return mock_settings


@pytest.fixture
def file_exporter_port() -> PathExporterPort:
    mock_port = MagicMock(spec=PathExporterPort)

    def generate_filename(method: str, path: str) -> str:
        clean_path = path.replace("/", "_").strip("_").replace("{", "").replace("}", "")
        return f"{method.lower()}_{clean_path}.yaml"

    mock_port.generate_filename.side_effect = generate_filename
    return mock_port


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
def api_full_object():
    return MockApiFull(
        api=MockApiPartialInfo(
            id="123",
            name="Test API",
            version="1.0.0",
            description="A test API",
            basePath="/test",
        ),
        interceptors=[
            MockInterceptor(name="Global-Request-Interceptor", position=1),
        ],
        resources=[
            MockResource(
                name="Users",
                description="Resource for user operations",
                operations=[
                    MockOperation(
                        path="/users",
                        method="GET",
                        description="Get all users",
                        interceptors=[
                            MockInterceptor(name="Op-Specific-Interceptor", position=2)
                        ],
                    ),
                    MockOperation(
                        path="/users/{id}", method="POST", description="Create a user"
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
        file_exporter_port: PathExporterPort,
        schema_validator: SchemaValidator,
    ):
        service = JsonToYamlService(
            json_full_object=api_full_object,
            settings=settings,
            file_exporter_port=file_exporter_port,
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

        assert len(yaml_parts) == 5

        errors = []
        for part in yaml_parts:
            kind = part.get("kind")
            file_name_for_logging = part.get("metadata", {}).get(
                "fileName", f"{kind}.yaml"
            )

            # Skip validation for ResourcesList due to schema mismatch
            if kind == JsonKind.RESOURCES.value:
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
