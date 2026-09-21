import pytest
from unittest.mock import MagicMock
from apiops_orchestrator.application.services.api_listing_service import ApiListingService
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort
from apiops_orchestrator.domain.models.api_collection_model import (
    InsufficientSessionError,
)
from apiops_orchestrator.domain.models.login_session_model import LoginSession


def _make_session(profile: str = "developer", groups=None) -> LoginSession:
    payload = {
        "accessToken": "x",
        "tokenType": "Bearer",
        "expiresIn": 3600,
        "scope": "list",
        "profile": profile,
        "userName": "isaac.machado",
        "userEmail": "isaac.machado@sensedia.com",
        "userGroups": groups,
    }
    if profile == "developer":
        payload["userGroups"] = groups if groups is not None else ["APIOps"]
    return LoginSession.model_validate(payload)


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


class TestVisibilityOnListing:
    RAW_APIS = [
        {
            "id": 1,
            "name": "Publica",
            "visibility": {
                "visibilityType": "ORGANIZATION",
                "owner": "alguem.nao",
                "users": [],
            },
        },
        {
            "id": 2,
            "name": "Meu Grupo",
            "visibility": {
                "visibilityType": "GROUP",
                "groupVisibility": {"name": "APIOps"},
                "owner": "paulo.silva",
                "users": [],
            },
        },
        {
            "id": 3,
            "name": "Alheia ME",
            "visibility": {"visibilityType": "ME", "owner": "outro.user", "users": []},
        },
    ]

    REVISION_BASIC_ROWS = [
        {"id": 9, "api": {"id": 1, "revisionNumber": 3}, "workflowId": 139},
    ]

    @pytest.fixture
    def mock_manager_api(self):
        mock = MagicMock(spec=ManagerApiPort)
        mock.get_apis.return_value = self.RAW_APIS
        mock.get_revisions_basic.return_value = []
        return mock

    def test_listing_enriches_last_revision_with_one_extra_call(self, mock_manager_api):
        mock_manager_api.get_revisions_basic.return_value = self.REVISION_BASIC_ROWS
        service = ApiListingService(manager_api=mock_manager_api)

        result = service.list_apis()

        public = next(row for row in result if row["id"] == 1)
        group = next(row for row in result if row["id"] == 2)
        assert public["lastRevision"]["revisionNumber"] == 3
        assert "lastRevision" not in group  # api sem linha no catalogo
        mock_manager_api.get_revisions_basic.assert_called_once()

    def test_listing_degrades_silently_when_revision_catalog_fails(
        self, mock_manager_api
    ):
        mock_manager_api.get_revisions_basic.side_effect = RuntimeError("boom")
        service = ApiListingService(manager_api=mock_manager_api)

        result = service.list_apis()

        assert [row["id"] for row in result] == [1, 2, 3]
        assert all("lastRevision" not in row for row in result)

    def test_drill_down_does_not_pay_the_enrichment_call(self, mock_manager_api):
        mock_manager_api.get_api_by_id.return_value = {
            "id": 9,
            "name": "Qualquer",
            "lastRevision": {"revisionNumber": 1},
        }
        service = ApiListingService(manager_api=mock_manager_api)

        result = service.list_apis(api_id=9)

        assert result[0]["lastRevision"]["revisionNumber"] == 1
        mock_manager_api.get_revisions_basic.assert_not_called()

    def test_without_session_passes_through_unfiltered_legacy(self, mock_manager_api):
        service = ApiListingService(manager_api=mock_manager_api, session=None)

        result = service.list_apis()

        assert [row["id"] for row in result] == [1, 2, 3]

    def test_developer_session_filters_by_visibility(self, mock_manager_api):
        service = ApiListingService(
            manager_api=mock_manager_api, session=_make_session(groups=["APIOps"])
        )

        result = service.list_apis()

        assert [row["id"] for row in result] == [1, 2]

    def test_super_admin_session_sees_everything(self, mock_manager_api):
        service = ApiListingService(
            manager_api=mock_manager_api, session=_make_session(profile="super-admin")
        )

        result = service.list_apis()

        assert [row["id"] for row in result] == [1, 2, 3]

    def test_developer_session_without_groups_blocked(
        self, mock_manager_api
    ):
        # Sessao defensiva (o modelo valida e impede o estado em producao);
        # exercita a defesa em profundidade do service.
        session = MagicMock(spec=LoginSession)
        session.is_super_admin = False
        session.userName = "isaac.machado"
        session.userGroups = []

        service = ApiListingService(manager_api=mock_manager_api, session=session)

        with pytest.raises(InsufficientSessionError, match="grupos de acesso"):
            service.list_apis()

        # Bloqueio ANTES de consumir/complementar dados na colecao
        mock_manager_api.get_apis.assert_not_called()

    def test_drill_down_by_id_ignores_visibility_session(
        self, mock_manager_api
    ):
        mock_manager_api.get_api_by_id.return_value = {"id": 9, "name": "Qualquer"}
        session = MagicMock(spec=LoginSession)
        session.is_super_admin = False
        session.userName = "isaac.machado"
        session.userGroups = []

        service = ApiListingService(manager_api=mock_manager_api, session=session)
        result = service.list_apis(api_id=9)

        assert result == [{"id": 9, "name": "Qualquer"}]
