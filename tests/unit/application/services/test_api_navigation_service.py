"""Use-cases de navegação: visibilidade, seleção de revisão e tradução de falhas."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    UNAUTHORIZED_MESSAGE,
    UNAVAILABLE_MESSAGE,
)
from apiops_orchestrator.application.exceptions.navigation_exceptions import (
    NavigationApiNotFound,
    NavigationCustomNotFound,
    NavigationInterceptorNotFound,
    NavigationPlatformError,
    NavigationRevisionNotFound,
    NavigationScopeNotFound,
)
from apiops_orchestrator.application.services.api_navigation_service import (
    ApiNavigationService,
)
from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from apiops_orchestrator.domain.models.api_visibility_model import OwnershipContext
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiPort,
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
    ManagerApiUnexpectedResponseError,
)


def _api():
    revision = {
        "id": 8948,
        "revisionNumber": 4,
        "interceptors": [
            {"id": 1, "position": 0, "executionPoint": "FIRST", "type": "Log", "status": "REFERENCE"}
        ],
        "resources": [
            {
                "id": 10,
                "name": "Token",
                "interceptors": [],
                "operations": [
                    {"id": 11, "method": "POST", "path": "/oauth2/token", "interceptors": []}
                ],
            }
        ],
    }
    return {
        "id": 400,
        "name": "Orchestrator Auth API",
        "version": "1.0.1",
        "basePath": "/orq-auth/v1",
        "revisions": [{"id": 8862, "revisionNumber": 1, "interceptors": [], "resources": []}, revision],
        "lastRevision": revision,
        "environments": [],
    }


def _port(api=None):
    port = MagicMock(spec=ManagerApiPort)
    port.get_api_by_id.return_value = api if api is not None else _api()
    return port


def _developer(username="dev", groups=("APIOps",)):
    return SimpleNamespace(is_super_admin=False, userName=username, userGroups=list(groups))


# --------------------------------------------------------------------------- visibilidade


def test_super_admin_reads_manager_directly():
    port = _port()
    service = ApiNavigationService(port, session=None)

    detail = service.api_detail(400)

    assert detail["id"] == 400 and detail["lastRevisionNumber"] == 4
    port.get_api_by_id.assert_called_once_with(400)
    port.list_api_detail.assert_not_called()


def test_developer_goes_through_the_catalog_guard():
    port = _port()
    port.list_api_detail.return_value = ApiCatalogEntry(
        id=400, contextType=OwnershipContext.GROUP, contextGroupName="APIOps"
    )
    service = ApiNavigationService(port, session=_developer())

    assert service.api_detail(400)["id"] == 400
    port.list_api_detail.assert_called_once_with(400)


@pytest.mark.parametrize(
    "entry",
    [
        None,
        ApiCatalogEntry(id=400, contextType=OwnershipContext.ME, owner="someone-else"),
        ApiCatalogEntry(id=400, contextType=OwnershipContext.GROUP, contextGroupName="Other"),
    ],
)
def test_invisible_or_missing_api_answers_not_found(entry):
    port = _port()
    port.list_api_detail.return_value = entry
    service = ApiNavigationService(port, session=_developer())

    with pytest.raises(NavigationApiNotFound) as info:
        service.api_detail(400)
    assert "400" in info.value.message
    port.get_api_by_id.assert_not_called()


# --------------------------------------------------------------------------- revisão


def test_revision_by_number_by_id_and_missing():
    service = ApiNavigationService(_port(), session=None)

    _, by_number = service.revision(400, number=1)
    assert by_number["id"] == 8862
    _, by_id = service.revision(400, revision_id=8948)
    assert by_id["revisionNumber"] == 4
    _, current = service.revision(400)
    assert current["id"] == 8948

    with pytest.raises(NavigationRevisionNotFound) as info:
        service.revision(400, number=7)
    assert "de número 7" in info.value.message
    assert "1, 4" in info.value.message
    assert "sen get api --id 400" in info.value.message

    with pytest.raises(NavigationRevisionNotFound) as info:
        service.revision(400, revision_id=5)
    assert "de id 5" in info.value.message


# --------------------------------------------------------------------------- níveis


def test_structure_interceptors_and_item():
    service = ApiNavigationService(_port(), session=None)

    structure = service.structure(400)
    assert structure["totals"] == {"resources": 1, "operations": 1}

    flows = service.interceptors(400, resource="Token", effective=True)
    assert [s["scope"] for s in flows["scopes"]] == ["token", "POST /oauth2/token"]

    with pytest.raises(NavigationScopeNotFound) as info:
        service.interceptors(400, resource="Token", operation="GET /nope")
    assert "--resource 'Token' --operation 'GET /nope'" in info.value.message

    item = service.interceptor(400, 1)
    assert item["scope"]["kind"] == "root" and item["interceptor"]["type"] == "Log"

    with pytest.raises(NavigationInterceptorNotFound):
        service.interceptor(400, 999)


def test_custom_interceptor_present_and_absent():
    port = _port()
    port.get_custom_interceptor_by_id.return_value = {"id": 31, "name": "X", "script": "s"}
    service = ApiNavigationService(port, session=None)
    assert service.custom_interceptor(31) == {"id": 31, "name": "X", "script": "s"}

    port.get_custom_interceptor_by_id.return_value = None
    with pytest.raises(NavigationCustomNotFound) as info:
        service.custom_interceptor(31)
    assert "31" in info.value.message


def test_swagger_uses_the_selected_revision_id():
    port = _port()
    port.get_revision_swagger.return_value = {"openapi": "3.0.0"}
    service = ApiNavigationService(port, session=None)

    assert service.swagger(400, number=1) == {"openapi": "3.0.0"}
    port.get_revision_swagger.assert_called_once_with(8862)

    port.get_revision_swagger.side_effect = ManagerApiUnexpectedResponseError("x")
    with pytest.raises(NavigationPlatformError):
        service.swagger(400)


def test_export_materializes_the_canonical_tree():
    service = ApiNavigationService(_port(), session=None)

    api, revision, result = service.export(400, number=4)

    assert api["id"] == 400 and revision["id"] == 8948
    assert result.paths == [
        "api-basic-info.yaml",
        "all.yaml",
        "resources/token/resource.yaml",
        "resources/token/post_oauth2_token.yaml",
    ]


# --------------------------------------------------------------------------- falhas


@pytest.mark.parametrize(
    "signal,expected_type,expected_text",
    [
        (ManagerApiTransportRejectedError(404, "Not Found"), NavigationApiNotFound, "400"),
        (ManagerApiTransportRejectedError(401, "Unauthorized"), NavigationPlatformError, UNAUTHORIZED_MESSAGE),
        (ManagerApiTransportUnavailableError("down"), NavigationPlatformError, UNAVAILABLE_MESSAGE),
    ],
)
def test_port_signals_become_navigation_errors(signal, expected_type, expected_text):
    port = _port()
    port.get_api_by_id.side_effect = signal
    service = ApiNavigationService(port, session=None)

    with pytest.raises(expected_type) as info:
        service.api_detail(400)
    assert expected_text in info.value.message


def test_custom_404_outside_an_api_is_not_an_api_not_found():
    port = _port()
    port.get_custom_interceptor_by_id.side_effect = ManagerApiTransportRejectedError(
        418, "Teapot"
    )
    service = ApiNavigationService(port, session=None)
    with pytest.raises(NavigationPlatformError):
        service.custom_interceptor(1)
