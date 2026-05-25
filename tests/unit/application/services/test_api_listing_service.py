import pytest
from unittest.mock import MagicMock
from apiops_orchestrator.application.services.api_listing_service import ApiListingService
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort

class TestApiListingService:
    @pytest.fixture
    def mock_manager_api(self):
        return MagicMock(spec=ManagerApiPort)

    @pytest.fixture
    def service(self, mock_manager_api):
        return ApiListingService(manager_api=mock_manager_api)

    def test_list_apis_without_id(self, service, mock_manager_api):
        # Arrange
        expected_apis = [{"id": 1, "name": "API 1"}, {"id": 2, "name": "API 2"}]
        mock_manager_api.get_apis.return_value = expected_apis

        # Act
        result = service.list_apis()

        # Assert
        assert result == expected_apis
        mock_manager_api.get_apis.assert_called_once()
        mock_manager_api.get_api_by_id.assert_not_called()

    def test_list_apis_with_id(self, service, mock_manager_api):
        # Arrange
        api_id = 123
        expected_api = {"id": api_id, "name": "API 123"}
        mock_manager_api.get_api_by_id.return_value = expected_api

        # Act
        result = service.list_apis(api_id=api_id)

        # Assert
        assert result == [expected_api]
        mock_manager_api.get_api_by_id.assert_called_once_with(api_id)
        mock_manager_api.get_apis.assert_not_called()
