import pytest
from unittest.mock import MagicMock
import requests
from apiops_orchestrator.application.services.publisher_service import PublisherService
from apiops_orchestrator.domain.ports.manager_api_port import PublisherPort


def test_fetch_remote_api_data_success():
    mock_adapter = MagicMock(spec=PublisherPort)
    expected_json = {"id": "123", "name": "My API Test"}
    mock_adapter.get_api_by_id.return_value = expected_json

    service = PublisherService(mock_adapter)
    result = service.fetch_remote_api_data()
    assert result == expected_json
    mock_adapter.get_api_by_id.assert_called_once()

def test_fetch_remote_api_data_propagates_error():
    mock_adapter = MagicMock(spec=PublisherPort)
    original_error = requests.exceptions.HTTPError("Erro 500 - Server Error")
    mock_adapter.get_api_by_id.side_effect = original_error

    service = PublisherService(mock_adapter)

    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        service.fetch_remote_api_data()

    assert "Erro 500" in str(excinfo.value)