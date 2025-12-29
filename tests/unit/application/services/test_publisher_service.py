import pytest
from unittest.mock import MagicMock
import requests
from apiops_orchestrator.application.services.publisher_service import PublisherService
from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.domain.models.api_partial_model import ApiPartialInfo
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort


def test_fetch_remote_api_data_success():
    mock_adapter = MagicMock(spec=ManagerApiPort)
    expected_json = {"id": "123", "name": "My API Test"}
    mock_adapter.get_api_by_id.return_value = expected_json

    service = PublisherService(mock_adapter)
    result = service.fetch_remote_api_data()
    assert result == expected_json
    mock_adapter.get_api_by_id.assert_called_once()

def test_fetch_remote_api_data_propagates_error():
    mock_adapter = MagicMock(spec=ManagerApiPort)
    original_error = requests.exceptions.HTTPError("Erro 500 - Server Error")
    mock_adapter.get_api_by_id.side_effect = original_error

    service = PublisherService(mock_adapter)

    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        service.fetch_remote_api_data()

    assert "Erro 500" in str(excinfo.value)

def test_format_data_updates_fields():
    mock_adapter = MagicMock(spec=ManagerApiPort)
    api_partial_info_mock = MagicMock(spec=ApiPartialInfo)

    api_data = ApiFull(
        api=api_partial_info_mock,
        revisionNumber=999,
        workflowId=None,
        workflowStageId=None,
        interceptors=[],
        resources=[]
    )


    remote_api_data = {
        "revisions": [
            {"workflowId": 10, "workflowStageId": 5},
            {"workflowId": 20, "workflowStageId": 7},   # Last revision
        ],
        "lastRevision": 99,
        "creationDate": 123456789,
    }


    obj = PublisherService(mock_adapter)
    updated = obj._format_data(api_data, remote_api_data)

    assert updated.workflowId == 20
    assert updated.workflowStageId == 7
    assert updated.api.lastRevision == 99
    assert updated.api.creationDate == 123456789
    assert updated.api.revisions == remote_api_data["revisions"]