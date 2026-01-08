import pytest

from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import ManagerApiAdapter
from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.application.services.conversor_service import ConversorService
from apiops_orchestrator.application.exceptions.yaml_to_json_exceptions import (
    ApiBasicInfoNotFoundException,
    ResourcesListNotFoundException,
    InterceptorsNotFoundException,
)
from apiops_orchestrator.config.settings import Settings


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def minimal_api_basic_info():
    return {
        "apiVersion": "v1",
        "kind": "ApiBasicInfo",
        "spec": {
            "api": {
                "name": "Test API",
                "basePath": "/test",
                "version": "v1",
                "apiResponsible": {"username": "testuser", "groupName": "testgroup"},
            }
        },
    }


@pytest.fixture
def minimal_interceptors():
    return {
        "apiVersion": "v1",
        "kind": "Interceptors",
        "spec": {
            "interceptors": [
                {
                    "position": 1,
                    "type": "inbound",
                    "content": {"key": "value"},
                    "executionPoint": "in",
                    "status": "enabled",
                }
            ]
        },
    }


@pytest.fixture
def minimal_api_operations():
    return {
        "apiVersion": "v1",
        "kind": "ApiOperations",
        "metadata": {"fileName": "op1.yaml"},
        "spec": {
            "operation": [
                {
                    "method": "GET",
                    "path": "/test",
                    "destination": "/mock/destination",
                    "interceptors": [
                        {
                            "position": 1,
                            "type": "outbound",
                            "content": {"key": "value"},
                            "executionPoint": "out",
                            "status": "enabled",
                        }
                    ],
                }
            ]
        },
    }


@pytest.fixture
def minimal_resources_list():
    return {
        "apiVersion": "v1",
        "kind": "ResourcesList",
        "items": [
            {
                "name": "Test Resource",
                "description": "A test resource",
                "operations": [{"file": "op1.yaml", "method": "GET", "path": "/test"}],
            }
        ],
    }


@pytest.fixture
def complex_yamls():
    return [
        {
            "apiVersion": "v1",
            "kind": "ApiBasicInfo",
            "spec": {
                "api": {
                    "name": "Complex API",
                    "basePath": "/complex",
                    "version": "v1",
                    "apiResponsible": {"username": "admin", "groupName": "admins"},
                }
            },
        },
        {
            "apiVersion": "v1",
            "kind": "Interceptors",
            "spec": {
                "interceptors": [
                    {
                        "position": 1,
                        "type": "global",
                        "content": {},
                        "executionPoint": "in",
                        "status": "enabled",
                    }
                ]
            },
        },
        {
            "apiVersion": "v1",
            "kind": "ApiOperations",
            "metadata": {"fileName": "op1.yaml"},
            "spec": {
                "operation": [
                    {
                        "method": "GET",
                        "path": "/res1",
                        "destination": "/complex/res1",
                        "interceptors": [
                            {
                                "position": 1,
                                "type": "op1-interceptor",
                                "content": {},
                                "executionPoint": "in",
                                "status": "enabled",
                            }
                        ],
                    }
                ]
            },
        },
        {
            "apiVersion": "v1",
            "kind": "ApiOperations",
            "metadata": {"fileName": "op2.yaml"},
            "spec": {
                "operation": [
                    {
                        "method": "POST",
                        "path": "/res2",
                        "destination": "/complex/res2",
                        "interceptors": [
                            {
                                "position": 1,
                                "type": "op2-interceptor",
                                "content": {},
                                "executionPoint": "in",
                                "status": "enabled",
                            }
                        ],
                    }
                ]
            },
        },
        {
            "apiVersion": "v1",
            "kind": "ResourcesList",
            "items": [
                {
                    "name": "Resource 1",
                    "operations": [
                        {"file": "op1.yaml", "method": "GET", "path": "/res1"}
                    ],
                },
                {
                    "name": "Resource 2",
                    "operations": [
                        {"file": "op2.yaml", "method": "POST", "path": "/res2"}
                    ],
                },
            ],
        },
    ]

@pytest.fixture
def manager_api_adapter(settings):
    return ManagerApiAdapter("token", "base_path", 3, 1, settings)


def test_build_api_json_happy_path(
    minimal_api_basic_info,
    minimal_interceptors,
    minimal_api_operations,
    minimal_resources_list,
    manager_api_adapter,
    settings,
    monkeypatch,
):
    """
    Tests the successful creation of an ApiFull object from a valid set of YAML data.
    """
    yamls = [
        minimal_api_basic_info,
        minimal_interceptors,
        minimal_api_operations,
        minimal_resources_list,
    ]
    service = ConversorService(yamls, settings, manager_api_adapter)
    result = service.build_api_json()

    assert isinstance(result, ApiFull)
    assert result.api.name == "Test API"
    assert len(result.resources) == 1
    assert len(result.interceptors) == 1


def test_build_api_json_interceptor_content_is_string(
    minimal_api_basic_info,
    minimal_interceptors,
    minimal_api_operations,
    minimal_resources_list,
    manager_api_adapter,
    settings,
    monkeypatch,
):
    """
    Tests that the interceptor content is converted to a JSON string.
    """
    yamls = [
        minimal_api_basic_info,
        minimal_interceptors,
        minimal_api_operations,
        minimal_resources_list,
    ]
    service = ConversorService(yamls, settings, manager_api_adapter)
    result = service.build_api_json()

    assert isinstance(result.interceptors[0].content, str)


def test_interceptor_position_increment(
    minimal_api_basic_info,
    minimal_interceptors,
    minimal_api_operations,
    minimal_resources_list,
    manager_api_adapter,
    settings,
    monkeypatch,
):
    """
    Tests that the interceptor positions are correctly incremented by the ApiFull model validator.
    """
    yamls = [
        minimal_api_basic_info,
        minimal_interceptors,
        minimal_api_operations,
        minimal_resources_list,
    ]
    service = ConversorService(yamls, settings, manager_api_adapter)
    result = service.build_api_json()

    # The ApiFull model validator re-numbers all interceptors sequentially.
    # 1. The global interceptor gets position 1.
    # 2. The operation-specific interceptor gets position 2.
    assert result.interceptors[0].position == 1
    assert result.resources[0].operations[0].interceptors[0].position == 2


def test_missing_api_basic_info(
    minimal_interceptors,
    minimal_api_operations,
    minimal_resources_list,
    manager_api_adapter,
    settings,
    monkeypatch,
):
    """
    Tests that ApiInfoNotFoundException is raised when ApiBasicInfo is missing.
    """
    yamls = [minimal_interceptors, minimal_api_operations, minimal_resources_list]
    service = ConversorService(yamls, settings, manager_api_adapter)
    with pytest.raises(ApiBasicInfoNotFoundException):
        service.build_api_json()


def test_missing_resources_list(
    minimal_api_basic_info, minimal_interceptors, minimal_api_operations, manager_api_adapter, settings
):
    """
    Tests that ResourcesListNotFoundException is raised when ResourcesList is missing.
    """
    yamls = [minimal_api_basic_info, minimal_interceptors, minimal_api_operations]
    service = ConversorService(yamls, settings, manager_api_adapter)
    with pytest.raises(ResourcesListNotFoundException):
        service.build_api_json()


def test_missing_interceptors(
    minimal_api_basic_info, minimal_api_operations, minimal_resources_list, manager_api_adapter, settings
):
    """
    Tests that InterceptorsNotFoundException is raised when Interceptors are missing.
    """
    yamls = [minimal_api_basic_info, minimal_api_operations, minimal_resources_list]
    service = ConversorService(yamls, settings, manager_api_adapter)
    with pytest.raises(InterceptorsNotFoundException):
        service.build_api_json()


def test_multiple_api_basic_info(minimal_api_basic_info, manager_api_adapter, settings):
    """
    Tests that a ValueError is raised when multiple ApiBasicInfo files are provided.
    """
    yamls = [minimal_api_basic_info, minimal_api_basic_info]
    service = ConversorService(yamls, settings, manager_api_adapter)
    with pytest.raises(ValueError, match="Multiple ApiBasicInfo found"):
        service.build_api_json()


def test_duplicate_api_operations_filename(
    minimal_api_basic_info,
    minimal_interceptors,
    minimal_api_operations,
    minimal_resources_list,
    manager_api_adapter,
    settings,
):
    """
    Tests that a ValueError is raised for duplicate ApiOperations fileName.
    """
    yamls = [
        minimal_api_basic_info,
        minimal_interceptors,
        minimal_api_operations,
        minimal_api_operations,  # Duplicate
        minimal_resources_list,
    ]
    service = ConversorService(yamls, settings, manager_api_adapter)
    with pytest.raises(ValueError, match="Duplicate ApiOperations fileName"):
        service.build_api_json()


def test_api_operation_file_not_found(
    minimal_api_basic_info, minimal_interceptors, minimal_resources_list, manager_api_adapter, settings
):
    """
    Tests that a ValueError is raised if a resource references a non-existent ApiOperation file.
    """
    yamls = [minimal_api_basic_info, minimal_interceptors, minimal_resources_list]
    service = ConversorService(yamls, settings, manager_api_adapter)
    with pytest.raises(ValueError, match="ApiOperation file 'op1.yaml' not found"):
        service.build_api_json()


def test_operation_mismatch(
    minimal_api_basic_info,
    minimal_interceptors,
    minimal_api_operations,
    minimal_resources_list,
    manager_api_adapter,
    settings,
):
    """
    Tests that a ValueError is raised if there is a mismatch between resource operation and ApiOperation file.
    """
    # Modify the resource list to have a different method
    minimal_resources_list["items"][0]["operations"][0]["method"] = "POST"
    yamls = [
        minimal_api_basic_info,
        minimal_interceptors,
        minimal_api_operations,
        minimal_resources_list,
    ]
    service = ConversorService(yamls, settings, manager_api_adapter)
    with pytest.raises(ValueError, match="Operation mismatch"):
        service.build_api_json()


def test_empty_interceptors_list(
    minimal_api_basic_info, minimal_api_operations, minimal_resources_list, manager_api_adapter, settings
):
    """
    Tests that InterceptorsNotFoundException is raised for an empty interceptors list.
    """
    empty_interceptors = {
        "apiVersion": "v1",
        "kind": "Interceptors",
        "spec": {"interceptors": []},
    }
    yamls = [
        minimal_api_basic_info,
        empty_interceptors,
        minimal_api_operations,
        minimal_resources_list,
    ]
    service = ConversorService(yamls, settings, manager_api_adapter)
    with pytest.raises(InterceptorsNotFoundException):
        service.build_api_json()


def test_empty_resources_list(
    minimal_api_basic_info, minimal_interceptors, minimal_api_operations, manager_api_adapter, settings
):
    """
    Tests that ResourcesListNotFoundException is raised for an empty items list.
    """
    empty_resources = {"apiVersion": "v1", "kind": "ResourcesList", "items": []}
    yamls = [
        minimal_api_basic_info,
        minimal_interceptors,
        minimal_api_operations,
        empty_resources,
    ]
    service = ConversorService(yamls, settings, manager_api_adapter)
    with pytest.raises(ResourcesListNotFoundException):
        service.build_api_json()


def test_interceptor_missing_position(
    minimal_api_basic_info, minimal_resources_list, manager_api_adapter, settings
):
    """
    Tests that a validation error is raised if an interceptor is missing the 'position' field.
    """
    invalid_interceptors = {
        "apiVersion": "v1",
        "kind": "Interceptors",
        "spec": {
            "interceptors": [
                {
                    # No position, id, or idTemp here
                    "type": "inbound",
                    "content": {},
                    "executionPoint": "in",
                    "status": "enabled",
                }
            ]
        },
    }
    yamls = [minimal_api_basic_info, invalid_interceptors, minimal_resources_list]
    service = ConversorService(yamls, settings, manager_api_adapter)
    # The service wraps Pydantic's ValidationError in a ValueError
    with pytest.raises(ValueError, match="YAML content validation failed"):
        service.build_api_json()


def test_complex_scenario_multiple_interceptors(complex_yamls, settings, manager_api_adapter):
    """
    Tests a more complex scenario with multiple resources and interceptors.
    """
    service = ConversorService(complex_yamls, settings, manager_api_adapter)
    result = service.build_api_json()

    assert isinstance(result, ApiFull)
    assert result.api.name == "Complex API"
    assert len(result.resources) == 2
    assert len(result.interceptors) == 1  # Global interceptor
    assert len(result.resources[0].operations[0].interceptors) == 1  # Op1 interceptor
    assert len(result.resources[1].operations[0].interceptors) == 1  # Op2 interceptor
