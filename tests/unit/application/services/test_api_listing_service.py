import pytest
from unittest.mock import MagicMock, call
from apiops_orchestrator.application.services.api_listing_service import ApiListingService
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort
from apiops_orchestrator.domain.ports.manager_api_port import ApiCatalogPage
from apiops_orchestrator.domain.models.api_collection_model import (
    ApiCollectionError,
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

    def test_list_apis_without_id(self, mock_manager_api):
        # Arrange: listagem nascida do finder (projecao canonica)
        mock_manager_api.list_catalog_apis.return_value = ApiCatalogPage(
            rows=[
                {"apiId": 1, "apiName": "API 1", "description": "d", "version": "1",
                 "basePath": "/a1", "apiLifeCycle": "DRAFT", "lastRevision": 3,
                 "contextType": "ORGANIZATION",
                 "revisions": [{"id": 3, "revisionNumber": 2}]},
                {"apiId": 2, "apiName": "API 2", "description": "d", "version": "1",
                 "basePath": "/b/v1", "apiLifeCycle": "DRAFT", "lastRevision": 4,
                 "contextType": "ORGANIZATION",
                 "revisions": [{"id": 4, "revisionNumber": 1}]},
            ],
            total=2,
        )
        service = ApiListingService(manager_api=mock_manager_api)

        # Act
        result = service.list_apis()

        # Assert — mundo inteiro (limit omitido) numa unica chamada
        assert [row["id"] for row in result] == [1, 2]
        # lastRevision = ID; número resolvido pelo revisions[] local (2 e 1)
        assert [row["lastRevision"]["revisionNumber"] for row in result] == [2, 1]
        mock_manager_api.list_catalog_apis.assert_called_once_with(limit=1)
        mock_manager_api.get_apis.assert_not_called()
        mock_manager_api.get_api_by_id.assert_not_called()

    def test_list_apis_with_id(self, mock_manager_api):
        # Arrange: detalhe via catálogo (opção A)
        mock_manager_api.list_api_detail.return_value = {
            "apiId": 123,
            "apiName": "API 123",
            "description": "d",
            "version": "1.0",
            "basePath": "/x/v1",
            "apiLifeCycle": "DRAFT",
            "lastRevision": 88,
            "revisions": [
                {"id": 77, "revisionNumber": 8},
                {"id": 88, "revisionNumber": 9},
            ],
        }
        service = ApiListingService(manager_api=mock_manager_api)

        # Act
        result = service.list_apis(api_id=123)

        # lastRevision do finder = ID (88); número vem do revisions[] local
        assert [row["id"] for row in result] == [123]
        by_id = {row["id"]: row for row in result}
        assert by_id[123]["lastRevision"]["revisionNumber"] == 9
        mock_manager_api.list_api_detail.assert_called_once_with(123)
        mock_manager_api.get_api_by_id.assert_not_called()


class TestVisibilityOnListing:
    """Task 6 (rewire finder, sondas r5): listagem = API-FINDER, onlyMyContextApi=false.

    Visibilidade calculada no CLIENTE sobre contextType/contextGroupName
    (GROUP exclusivamente por grupo; contextUserLogins so pesa em ME).
    Paginacao server-side NAO caminha (skip inerte) — service pede
    _limit = offset+limit e janela client-side (A3).
    """

    FINDER_ROWS = [
        {
            "apiId": 1, "apiName": "Publica", "description": "x", "version": "1",
            "basePath": "/p/v1", "contextType": "ORGANIZATION", "owner": "alguem.nao",
            "contextUserLogins": [], "apiLifeCycle": "PUBLISHED", "lastRevision": 77,
            "revisions": [{"id": 77, "revisionNumber": 3}],
        },
        {
            "apiId": 2, "apiName": "Meu Grupo", "description": "d2", "version": "1",
            "basePath": "/g/v1", "contextType": "GROUP", "contextGroupName": "APIOps",
            "owner": "paulo.silva", "contextUserLogins": [], "apiLifeCycle": "DRAFT",
            "lastRevision": 88,
            "revisions": [
                {"id": 77, "revisionNumber": 6},
                {"id": 88, "revisionNumber": 7},
            ],
        },
        {
            "apiId": 3, "apiName": "Alheia ME", "description": "d3", "version": "1",
            "basePath": "/m/v1", "contextType": "ME", "owner": "outro.user",
            "contextUserLogins": [], "apiLifeCycle": "DRAFT", "lastRevision": 5,
        },
        {
            "apiId": 4, "apiName": "Shared-ME", "description": "d4", "version": "1",
            "basePath": "/s/v1", "contextType": "ME", "owner": "titular.only",
            "contextUserLogins": ["isaac.machado"], "apiLifeCycle": "DRAFT",
            "lastRevision": 2,
        },
    ]

    @pytest.fixture
    def mock_manager_api(self):
        mock = MagicMock(spec=ManagerApiPort)
        mock.list_catalog_apis.return_value = ApiCatalogPage(
            rows=[dict(row) for row in self.FINDER_ROWS], total=len(self.FINDER_ROWS)
        )
        return mock

    def test_listing_sources_from_finder_without_revisions_basic(
        self, mock_manager_api
    ):
        service = ApiListingService(manager_api=mock_manager_api)

        result = service.list_apis()

        assert [row["id"] for row in result] == [1, 2, 3, 4]
        # lastRevision do finder = ID; número resolve no revisions[] LOCAL da linha
        by_id = {row["id"]: row for row in result}
        assert by_id[1]["lastRevision"]["revisionNumber"] == 3
        # pagina inteira ja cobre o universo (len==total): NAO ha refetch
        assert mock_manager_api.list_catalog_apis.call_args_list == [call(limit=1)]

    def test_server_pagination_inert_so_universe_refetch_grows(
        self, mock_manager_api
    ):
        """A3-1c exige universo completo: skip inerte no server → refetch com total."""
        mock_manager_api.list_catalog_apis.side_effect = [
            ApiCatalogPage(rows=[dict(self.FINDER_ROWS[0])], total=108),
            ApiCatalogPage(rows=[dict(r) for r in self.FINDER_ROWS], total=108),
        ]
        service = ApiListingService(manager_api=mock_manager_api)

        result = service.list_apis(offset=90, limit=5)

        assert [row["id"] for row in result] == []  # offset 90 além do total (4 visíveis)
        assert mock_manager_api.list_catalog_apis.call_count == 2
        mock_manager_api.list_catalog_apis.assert_any_call(limit=95)
        mock_manager_api.list_catalog_apis.assert_any_call(limit=108)

    def test_drill_down_does_not_pay_the_enrichment_call(self, mock_manager_api):
        mock_manager_api.list_api_detail.return_value = {
            "apiId": 9,
            "apiName": "Qualquer",
            "description": "d",
            "version": "1",
            "basePath": "/q/v1",
            "lastRevision": 900,
            "revisions": [{"id": 900, "revisionNumber": 1}],
        }
        service = ApiListingService(manager_api=mock_manager_api)

        result = service.list_apis(api_id=9)

        assert result[0]["lastRevision"]["revisionNumber"] == 1
        mock_manager_api.list_catalog_apis.assert_not_called()

    def test_without_session_passes_through_unfiltered_legacy(
        self, mock_manager_api
    ):
        service = ApiListingService(manager_api=mock_manager_api, session=None)

        result = service.list_apis()

        assert [row["id"] for row in result] == [1, 2, 3, 4]

    def test_developer_session_filters_by_visibility(self, mock_manager_api):
        service = ApiListingService(
            manager_api=mock_manager_api,
            session=_make_session(groups=["APIOps"]),
        )

        result = service.list_apis()

        # developer em APIOps vê ORGANIZATION (1) + GROUP APIOps (2);
        # ME alheia (3) some; Shared-ME (4) aparece via contextUserLogins
        assert [row["id"] for row in result] == [1, 2, 4]

    def test_group_context_denied_when_only_in_context_user_logins(
        self, mock_manager_api
    ):
        # Restrição selada: GROUP exige pertença ao GRUPO — a lista de logins
        # não concede. isaac NÃO está em APIOps aqui.
        service = ApiListingService(
            manager_api=mock_manager_api,
            session=_make_session(groups=["OutroGrupo"]),
        )

        result = service.list_apis()

        assert [row["id"] for row in result] == [1, 4]

    def test_super_admin_session_sees_everything(self, mock_manager_api):
        service = ApiListingService(
            manager_api=mock_manager_api,
            session=_make_session(profile="super-admin"),
        )

        result = service.list_apis()

        assert [row["id"] for row in result] == [1, 2, 3, 4]

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
        mock_manager_api.list_api_detail.return_value = {
            "apiId": 9, "apiName": "Qualquer", "description": "d",
            "version": "1", "basePath": "/q/v1",
        }
        session = MagicMock(spec=LoginSession)
        session.is_super_admin = False
        session.userName = "isaac.machado"
        session.userGroups = []

        service = ApiListingService(manager_api=mock_manager_api, session=session)
        result = service.list_apis(api_id=9)

        assert [row["id"] for row in result] == [9]


class TestApiRevisionsOrchestration:
    """Task 6 — drill-down de revisões, opção A (fonte única = frame do catálogo)."""

    @pytest.fixture
    def mock_manager_api(self):
        mock = MagicMock(spec=ManagerApiPort)
        mock.list_api_detail.return_value = {
            "apiId": 400,
            "apiName": "Orchestrator Auth API",
            "revisions": [
                {"id": 8862, "revisionNumber": 1},
                {"id": 8876, "revisionNumber": 2},
                {"id": 8882, "revisionNumber": 3},
            ],
            "completeness": [
                {"score": 85.0, "apiRevision": 8862},
                {"score": 85.0, "apiRevision": 8876},
            ],
            "environments": [
                {"id": 1, "name": "Default", "isDeployed": True, "apiRevision": 8862},
                {"id": 9, "name": "HMG-APIOPS", "isDeployed": True, "apiRevision": 8948},
            ],
            "wokflow": [
                {"workflowId": 139, "workflowStageId": 420, "apiRevision": 8862},
                {"workflowId": 139, "workflowStageId": 753, "apiRevision": 8876},
                {"workflowId": 139, "workflowStageId": 420, "apiRevision": 8882},
            ],
        }
        return mock

    def test_one_catalog_call_rows_ordered_stage_names_complete(
        self, mock_manager_api
    ):
        mock_manager_api.get_workflow_stages.return_value = [
            {"workflowStageId": 420, "workflowStageName": "Stage One"},
            {"workflowStageId": 753, "workflowStageName": "Teste"},
        ]
        service = ApiListingService(manager_api=mock_manager_api)

        rows = service.api_revisions(400)

        assert [row["revision_id"] for row in rows] == [8862, 8876, 8882]
        assert [row["revision_number"] for row in rows] == ["1", "2", "3"] or [
            row["revision_number"] for row in rows
        ] == [1, 2, 3]
        assert rows[0]["stage_name"] == "Stage One"
        assert rows[1]["stage_name"] == "Teste"
        assert rows[0]["complete"] == "85%"
        assert rows[2]["complete"] == "-"

        # economia: 1 chamada de frame + 1 de stages (workflow 139 único)
        mock_manager_api.list_api_detail.assert_called_once_with(400)
        mock_manager_api.get_workflow_stages.assert_called_once_with(139)

    def test_stage_failure_degrades_to_workflow_id(self, mock_manager_api):
        mock_manager_api.get_workflow_stages.side_effect = RuntimeError("gov down")
        service = ApiListingService(manager_api=mock_manager_api)

        rows = service.api_revisions(400)

        assert all(row["stage_name"] == 139 for row in rows)

    def test_created_and_last_deploy_are_placeholder_cells(self, mock_manager_api):
        service = ApiListingService(manager_api=mock_manager_api)

        rows = service.api_revisions(400)

        # opção A: células não existentes no frame NEM entram nas linhas
        assert all("created" not in row for row in rows)
        assert all("last_deploy" not in row for row in rows)

    def test_not_found_raises_friendly_error(self, mock_manager_api):
        mock_manager_api.list_api_detail.return_value = None
        service = ApiListingService(manager_api=mock_manager_api)

        with pytest.raises(ApiCollectionError, match="não encontrada"):
            service.api_revisions(999)
