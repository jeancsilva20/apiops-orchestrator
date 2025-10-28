import pytest
from apiops_orchestrator.domain.services.yaml_to_json_service import YamlToJsonService
from apiops_orchestrator.domain.services.yaml_to_json_exceptions import (
    ApiBasicInfoNotFoundException,
    ResourcesListNotFoundException,
    InterceptorsNotFoundException,
)


# Mock Data
# Basic valid data for happy path
@pytest.fixture
def minimal_api_basic_info():
    return {
        "apiVersion": "v1",
        "kind": "ApiBasicInfo",
        "spec": {
            "api": {
                "name": "Test API",
                "version": "v1",
                "basePath": "/test",
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
                    "content": {},
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
        "metadata": {"file_name": "op1.yaml"},
        "spec": {
            "operation": [
                {
                    "method": "GET",
                    "path": "/test",
                    "interceptors": [
                        {
                            "position": 1,
                            "type": "outbound",
                            "content": {},
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
                "operations": [{"method": "GET", "path": "/test", "file": "op1.yaml"}],
            }
        ],
    }


# Fixture for more complex scenario
@pytest.fixture
def complex_yamls():
    api_basic_info = {
        "apiVersion": "v1",
        "kind": "ApiBasicInfo",
        "spec": {
            "api": {
                "name": "Complex API",
                "version": "v2",
                "basePath": "/complex",
                "apiResponsible": {"username": "admin", "groupName": "admins"},
            }
        },
    }
    interceptors = {
        "apiVersion": "v1",
        "kind": "Interceptors",
        "spec": {
            "interceptors": [
                {
                    "position": 1,
                    "type": "inbound",
                    "content": {},
                    "executionPoint": "in",
                    "status": "enabled",
                },
                {
                    "position": 2,
                    "type": "inbound",
                    "content": {},
                    "executionPoint": "in",
                    "status": "enabled",
                },
            ]
        },
    }
    op1 = {
        "apiVersion": "v1",
        "kind": "ApiOperations",
        "metadata": {"file_name": "op1.yaml"},
        "spec": {
            "operation": [
                {
                    "method": "GET",
                    "path": "/res1",
                    "interceptors": [
                        {
                            "position": 1,
                            "type": "outbound",
                            "content": {},
                            "executionPoint": "out",
                            "status": "enabled",
                        }
                    ],
                }
            ]
        },
    }
    op2 = {
        "apiVersion": "v1",
        "kind": "ApiOperations",
        "metadata": {"file_name": "op2.yaml"},
        "spec": {
            "operation": [
                {
                    "method": "POST",
                    "path": "/res2",
                    "interceptors": [
                        {
                            "position": 1,
                            "type": "inbound",
                            "content": {},
                            "executionPoint": "in",
                            "status": "enabled",
                        },
                        {
                            "position": 2,
                            "type": "outbound",
                            "content": {},
                            "executionPoint": "out",
                            "status": "enabled",
                        },
                    ],
                }
            ]
        },
    }
    resources_list = {
        "apiVersion": "v1",
        "kind": "ResourcesList",
        "items": [
            {
                "name": "Resource 1",
                "operations": [{"method": "GET", "path": "/res1", "file": "op1.yaml"}],
            },
            {
                "name": "Resource 2",
                "operations": [{"method": "POST", "path": "/res2", "file": "op2.yaml"}],
            },
        ],
    }
    return [api_basic_info, interceptors, op1, op2, resources_list]


def test_build_api_json_happy_path(
    minimal_api_basic_info,
    minimal_interceptors,
    minimal_api_operations,
    minimal_resources_list,
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
    service = YamlToJsonService(yamls)
    result = service.build_api_json()

    assert result.api.name == "Test API"
    assert len(result.interceptors) == 1
    assert len(result.resources) == 1
    assert len(result.resources[0].operations) == 1
    assert len(result.resources[0].operations[0].interceptors) == 1


def test_interceptor_position_increment(
    minimal_api_basic_info,
    minimal_interceptors,
    minimal_api_operations,
    minimal_resources_list,
):
    """
    Tests that the interceptor positions are correctly incremented.
    """
    yamls = [
        minimal_api_basic_info,
        minimal_interceptors,
        minimal_api_operations,
        minimal_resources_list,
    ]
    service = YamlToJsonService(yamls)
    result = service.build_api_json()

    assert result.interceptors[0].position == 1
    assert result.resources[0].operations[0].interceptors[0].position == 2


def test_missing_api_basic_info(
    minimal_interceptors, minimal_api_operations, minimal_resources_list
):
    """
    Tests that ApiInfoNotFoundException is raised when ApiBasicInfo is missing.
    """
    yamls = [minimal_interceptors, minimal_api_operations, minimal_resources_list]
    service = YamlToJsonService(yamls)
    with pytest.raises(ApiBasicInfoNotFoundException):
        service.build_api_json()


def test_missing_resources_list(
    minimal_api_basic_info, minimal_interceptors, minimal_api_operations
):
    """
    Tests that ResourcesListNotFoundException is raised when ResourcesList is missing.
    """
    yamls = [minimal_api_basic_info, minimal_interceptors, minimal_api_operations]
    service = YamlToJsonService(yamls)
    with pytest.raises(ResourcesListNotFoundException):
        service.build_api_json()


def test_missing_interceptors(
    minimal_api_basic_info, minimal_api_operations, minimal_resources_list
):
    """
    Tests that InterceptorsNotFoundException is raised when Interceptors are missing.
    """
    yamls = [minimal_api_basic_info, minimal_api_operations, minimal_resources_list]
    service = YamlToJsonService(yamls)
    with pytest.raises(InterceptorsNotFoundException):
        service.build_api_json()


def test_multiple_api_basic_info(minimal_api_basic_info):
    """
    Tests that a ValueError is raised when multiple ApiBasicInfo files are provided.
    """
    yamls = [minimal_api_basic_info, minimal_api_basic_info]
    service = YamlToJsonService(yamls)
    with pytest.raises(ValueError, match="Multiple ApiBasicInfo found"):
        service.build_api_json()


def test_duplicate_api_operations_filename(
    minimal_api_basic_info,
    minimal_interceptors,
    minimal_api_operations,
    minimal_resources_list,
):
    """
    Tests that a ValueError is raised for duplicate ApiOperations file_name.
    """
    yamls = [
        minimal_api_basic_info,
        minimal_interceptors,
        minimal_api_operations,
        minimal_api_operations,
        minimal_resources_list,
    ]
    service = YamlToJsonService(yamls)
    with pytest.raises(ValueError, match="Duplicate ApiOperations file_name"):
        service.build_api_json()


def test_api_operation_file_not_found(
    minimal_api_basic_info, minimal_interceptors, minimal_resources_list
):
    """
    Tests that a ValueError is raised if a resource references a non-existent ApiOperation file.
    """
    yamls = [minimal_api_basic_info, minimal_interceptors, minimal_resources_list]
    service = YamlToJsonService(yamls)
    with pytest.raises(ValueError, match="ApiOperation file 'op1.yaml' not found"):
        service.build_api_json()


def test_operation_mismatch(
    minimal_api_basic_info,
    minimal_interceptors,
    minimal_api_operations,
    minimal_resources_list,
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
    service = YamlToJsonService(yamls)
    with pytest.raises(ValueError, match="Operation mismatch"):
        service.build_api_json()


def test_empty_interceptors_list(
    minimal_api_basic_info, minimal_api_operations, minimal_resources_list
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
    service = YamlToJsonService(yamls)
    with pytest.raises(InterceptorsNotFoundException):
        service.build_api_json()


def test_empty_resources_list(
    minimal_api_basic_info, minimal_interceptors, minimal_api_operations
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
    service = YamlToJsonService(yamls)
    with pytest.raises(ResourcesListNotFoundException):
        service.build_api_json()


def test_interceptor_missing_position(minimal_api_basic_info, minimal_resources_list):
    """
    Tests that a validation error is raised if an interceptor is missing the 'position' field.
    """
    invalid_interceptors = {
        "apiVersion": "v1",
        "kind": "Interceptors",
        "spec": {
            "interceptors": [
                {
                    # No position here
                    "type": "inbound",
                    "content": {},
                    "executionPoint": "in",
                    "status": "enabled",
                }
            ]
        },
    }
    yamls = [minimal_api_basic_info, invalid_interceptors, minimal_resources_list]
    service = YamlToJsonService(yamls)
    with pytest.raises(ValueError, match="YAML content validation failed"):
        service.build_api_json()


def test_complex_scenario_multiple_interceptors(complex_yamls):
    """
    Tests a more complex scenario with multiple resources and interceptors.
    """
    service = YamlToJsonService(complex_yamls)
    result = service.build_api_json()

    assert result.api.name == "Complex API"
    # Global interceptors
    assert len(result.interceptors) == 2
    assert result.interceptors[0].position == 1
    assert result.interceptors[1].position == 2

    # Resource 1, Operation 1
    assert len(result.resources) == 2
    res1 = result.resources[0]
    assert res1.name == "Resource 1"
    assert len(res1.operations) == 1
    op1 = res1.operations[0]
    assert len(op1.interceptors) == 1
    assert op1.interceptors[0].position == 3  # 2 global + 1st operational

    # Resource 2, Operation 1
    res2 = result.resources[1]
    assert res2.name == "Resource 2"
    assert len(res2.operations) == 1
    op2 = res2.operations[0]
    assert len(op2.interceptors) == 2
    assert op2.interceptors[0].position == 4  # Continues from the previous one
    assert op2.interceptors[1].position == 5
