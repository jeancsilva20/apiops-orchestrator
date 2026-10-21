import pytest
from unittest.mock import MagicMock, call
from apiops_orchestrator.application.services.api_listing_service import ApiListingService
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort
from apiops_orchestrator.domain.ports.manager_api_port import ApiCatalogPage
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiResponseTooLargeError,
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)
from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    FORBIDDEN_MESSAGE,
    INTERNAL_ERROR_MESSAGE,
    UNAUTHORIZED_MESSAGE,
    UNAVAILABLE_MESSAGE,
)
from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    _translate_row,
)
from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from apiops_orchestrator.domain.models.catalog_revision_model import (
    CatalogRevisionCompleteness,
)
from apiops_orchestrator.domain.models.workflow_stage_model import WorkflowStage
from apiops_orchestrator.application.exceptions.listing_exceptions import (
    ApiCollectionError,
    ApiNotFound,
    InsufficientSessionError,
)
from apiops_orchestrator.domain.models.login_session_model import LoginSession


def _wire(raw) -> ApiCatalogEntry:
    entry = _translate_row(raw)
    assert entry is not None
    return entry


def _page(rows, total):
    return ApiCatalogPage(rows=[_wire(r) for r in rows], total=total)


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
        # Arrange: listagem nascida do finder (port devolve TIPADO)
        mock_manager_api.list_catalog_apis.return_value = _page(
            [
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

        # Assert - pagina curta (2 < 25) encerra a leitura numa unica chamada
        assert [entry.id for entry in result] == [1, 2]
        # lastRevision = ID; numero resolvido pelo revisions[] local (2 e 1)
        assert [entry.last_revision_number() for entry in result] == [2, 1]
        mock_manager_api.list_catalog_apis.assert_called_once_with(
            limit=25, offset=0, query=None
        )
        mock_manager_api.get_apis.assert_not_called()
        mock_manager_api.get_api_by_id.assert_not_called()

    def test_list_apis_with_id(self, mock_manager_api):
        # Arrange: detalhe via catalogo (opcao A) - port devolve entry TIPADA
        mock_manager_api.list_api_detail.return_value = _wire({
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
        })
        service = ApiListingService(manager_api=mock_manager_api)

        # Act
        result = service.list_apis(api_id=123)

        # lastRevision do finder = ID (88); numero vem do revisions[] local
        assert [entry.id for entry in result] == [123]
        assert result[0].last_revision_number() == 9
        mock_manager_api.list_api_detail.assert_called_once_with(123)
        mock_manager_api.get_api_by_id.assert_not_called()


class TestVisibilityOnListing:
    """Task 6 (rewire finder, sondas r5): listagem = API-FINDER, onlyMyContextApi=false.

    Visibilidade calculada no CLIENTE sobre contextType/contextGroupName
    (GROUP exclusivamente por grupo; contextUserLogins so pesa em ME).
    Paginacao server-side NAO caminha (skip inerte) - service pede
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
        mock.list_catalog_apis.return_value = _page(
            self.FINDER_ROWS, len(self.FINDER_ROWS)
        )
        return mock

    def test_listing_sources_from_finder_without_revisions_basic(
        self, mock_manager_api
    ):
        service = ApiListingService(manager_api=mock_manager_api)

        result = service.list_apis()

        assert [entry.id for entry in result] == [1, 2, 3, 4]
        # lastRevision do finder = ID; numero resolve no revisions[] LOCAL da linha
        by_id = {entry.id: entry for entry in result}
        assert by_id[1].last_revision_number() == 3
        # pagina curta ja cobre o universo: uma unica leitura
        assert mock_manager_api.list_catalog_apis.call_args_list == [
            call(limit=25, offset=0, query=None)
        ]

    def test_offset_beyond_total_without_session_reads_from_server_offset(
        self, mock_manager_api
    ):
        """Sem sessao (visibilidade total) o offset vai direto ao servidor."""
        mock_manager_api.list_catalog_apis.return_value = _page([], 108)
        service = ApiListingService(manager_api=mock_manager_api)

        result = service.list_apis(offset=90, limit=5)

        assert result == []
        mock_manager_api.list_catalog_apis.assert_called_once_with(
            limit=25, offset=90, query=None
        )

    def test_drill_down_does_not_pay_the_enrichment_call(self, mock_manager_api):
        mock_manager_api.list_api_detail.return_value = _wire({
            "apiId": 9,
            "apiName": "Qualquer",
            "description": "d",
            "version": "1",
            "basePath": "/q/v1",
            "lastRevision": 900,
            "revisions": [{"id": 900, "revisionNumber": 1}],
        })
        service = ApiListingService(manager_api=mock_manager_api)

        result = service.list_apis(api_id=9)

        assert result[0].last_revision_number() == 1
        mock_manager_api.list_catalog_apis.assert_not_called()

    def test_without_session_passes_through_unfiltered_legacy(
        self, mock_manager_api
    ):
        service = ApiListingService(manager_api=mock_manager_api, session=None)

        result = service.list_apis()

        assert [entry.id for entry in result] == [1, 2, 3, 4]

    def test_developer_session_filters_by_visibility(self, mock_manager_api):
        service = ApiListingService(
            manager_api=mock_manager_api,
            session=_make_session(groups=["APIOps"]),
        )

        result = service.list_apis()

        # developer em APIOps ve ORGANIZATION (1) + GROUP APIOps (2);
        # ME alheia (3) some; Shared-ME (4) aparece via contextUserLogins
        assert [entry.id for entry in result] == [1, 2, 4]

    def test_group_context_denied_when_only_in_context_user_logins(
        self, mock_manager_api
    ):
        # Restricao selada: GROUP exige pertenca ao GRUPO - a lista de logins
        # nao concede. isaac NAO esta em APIOps aqui.
        service = ApiListingService(
            manager_api=mock_manager_api,
            session=_make_session(groups=["OutroGrupo"]),
        )

        result = service.list_apis()

        assert [entry.id for entry in result] == [1, 4]

    def test_super_admin_session_sees_everything(self, mock_manager_api):
        service = ApiListingService(
            manager_api=mock_manager_api,
            session=_make_session(profile="super-admin"),
        )

        result = service.list_apis()

        assert [entry.id for entry in result] == [1, 2, 3, 4]

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
        mock_manager_api.list_api_detail.return_value = _wire({
            "apiId": 9, "apiName": "Qualquer", "description": "d",
            "version": "1", "basePath": "/q/v1",
        })
        session = MagicMock(spec=LoginSession)
        session.is_super_admin = False
        session.userName = "isaac.machado"
        session.userGroups = []

        service = ApiListingService(manager_api=mock_manager_api, session=session)
        result = service.list_apis(api_id=9)

        assert [entry.id for entry in result] == [9]


MANAGER_SCORES = {8862: 74.3, 8876: 75.8, 8882: 88.8}


def _manager_completeness(revision_id):
    return CatalogRevisionCompleteness(score=MANAGER_SCORES[revision_id])


class TestApiRevisionsOrchestration:
    """Drill-down de revisões: frame do catálogo + completeness lido no Manager."""

    @pytest.fixture
    def mock_manager_api(self):
        mock = MagicMock(spec=ManagerApiPort)
        mock.list_api_detail.return_value = _wire({
            "apiId": 400,
            "apiName": "Orchestrator Auth API",
            "revisions": [
                {"id": 8882, "revisionNumber": 3},
                {"id": 8862, "revisionNumber": 1},
                {"id": 8876, "revisionNumber": 2},
            ],
            "completeness": [
                {"score": 68.5, "apiRevision": 8862},
                {"score": 66.8, "apiRevision": 8876},
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
        })
        mock.get_revision_completeness.side_effect = _manager_completeness
        return mock

    def test_one_catalog_call_rows_ordered_stage_names_complete(
        self, mock_manager_api
    ):
        mock_manager_api.get_workflow_stages.return_value = [
            WorkflowStage(workflowStageId=420, workflowStageName="Stage One"),
            WorkflowStage(workflowStageId=753, workflowStageName="Teste"),
        ]
        service = ApiListingService(manager_api=mock_manager_api)

        rows = service.api_revisions(400)

        assert [row.revision_id for row in rows] == [8862, 8876, 8882]
        assert [row.revision_number for row in rows] == [1, 2, 3]
        assert rows[0].stage_name == "Stage One"
        assert rows[1].stage_name == "Teste"

        # economia: 1 chamada de frame + 1 de stages (workflow 139 unico)
        mock_manager_api.list_api_detail.assert_called_once_with(400)
        mock_manager_api.get_workflow_stages.assert_called_once_with(139)

    def test_complete_comes_from_manager_not_from_the_frame(self, mock_manager_api):
        service = ApiListingService(manager_api=mock_manager_api)

        rows = service.api_revisions(400)

        assert [row.completeness_score for row in rows] == [74.3, 75.8, 88.8]
        assert sorted(
            c.args[0] for c in mock_manager_api.get_revision_completeness.call_args_list
        ) == [8862, 8876, 8882]

    @pytest.mark.parametrize(
        "failure",
        [
            ManagerApiTransportRejectedError(status_code=404, title="Not Found"),
            ManagerApiTransportUnavailableError("timeout"),
        ],
    )
    def test_completeness_failure_degrades_only_that_row(self, mock_manager_api, failure):
        def completeness(revision_id):
            if revision_id == 8876:
                raise failure
            return _manager_completeness(revision_id)

        mock_manager_api.get_revision_completeness.side_effect = completeness
        service = ApiListingService(manager_api=mock_manager_api)

        rows = service.api_revisions(400)

        assert [row.completeness_score for row in rows] == [74.3, None, 88.8]

    def test_unexpected_completeness_error_is_not_swallowed(self, mock_manager_api):
        mock_manager_api.get_revision_completeness.side_effect = RuntimeError("bug")
        service = ApiListingService(manager_api=mock_manager_api)

        with pytest.raises(RuntimeError):
            service.api_revisions(400)

    def test_not_found_does_not_read_completeness(self, mock_manager_api):
        mock_manager_api.list_api_detail.return_value = None
        service = ApiListingService(manager_api=mock_manager_api)

        with pytest.raises(ApiNotFound):
            service.api_revisions(999)

        mock_manager_api.get_revision_completeness.assert_not_called()

    def test_stage_failure_degrades_to_workflow_id(self, mock_manager_api):
        mock_manager_api.get_workflow_stages.return_value = []
        service = ApiListingService(manager_api=mock_manager_api)

        rows = service.api_revisions(400)

        assert all(row.stage_name == 139 for row in rows)

    def test_created_and_last_deploy_are_placeholder_cells(self, mock_manager_api):
        service = ApiListingService(manager_api=mock_manager_api)

        rows = service.api_revisions(400)

        # opcao A: celulas nao existentes no frame NEM entram nas linhas
        assert all(not hasattr(row, "created") for row in rows)
        assert all(not hasattr(row, "last_deploy") for row in rows)

    def test_not_found_raises_friendly_error(self, mock_manager_api):
        mock_manager_api.list_api_detail.return_value = None
        service = ApiListingService(manager_api=mock_manager_api)

        with pytest.raises(ApiCollectionError, match="não encontrada"):
            service.api_revisions(999)


class TestManagerFailureTranslation:
    """Falhas do Manager seguem a classificação compartilhada (sen-list E1)."""

    @pytest.fixture
    def port(self):
        return MagicMock(spec=ManagerApiPort)

    @pytest.mark.parametrize("status", [400, 413, 429])
    def test_other_4xx_is_internal_error_never_login_advice(self, port, status):
        port.list_catalog_apis.side_effect = ManagerApiTransportRejectedError(
            status_code=status, title="BACKEND_RESPONSE_TOO_LARGE",
            code="BACKEND_RESPONSE_TOO_LARGE", request_id="r-1",
        )

        with pytest.raises(ApiCollectionError) as excinfo:
            ApiListingService(manager_api=port).list_apis(offset=0, limit=10)

        message = str(excinfo.value)
        assert message == INTERNAL_ERROR_MESSAGE
        assert "sen login" not in message
        assert str(status) not in message and "BACKEND_RESPONSE_TOO_LARGE" not in message
        assert excinfo.value.exit_code == 1

    @pytest.mark.parametrize(
        ("status", "expected"),
        [(401, UNAUTHORIZED_MESSAGE), (403, FORBIDDEN_MESSAGE)],
    )
    def test_session_families_keep_their_message(self, port, status, expected):
        port.list_catalog_apis.side_effect = ManagerApiTransportRejectedError(
            status_code=status, title="x"
        )

        with pytest.raises(ApiCollectionError) as excinfo:
            ApiListingService(manager_api=port).list_apis(offset=0, limit=10)

        assert str(excinfo.value) == expected

    def test_unavailable_has_its_own_message(self, port):
        port.list_catalog_apis.side_effect = ManagerApiTransportUnavailableError("timeout")

        with pytest.raises(ApiCollectionError) as excinfo:
            ApiListingService(manager_api=port).list_apis(offset=0, limit=10)

        assert str(excinfo.value) == UNAVAILABLE_MESSAGE

    def test_404_on_drill_down_is_api_not_found(self, port):
        port.list_api_detail.side_effect = ManagerApiTransportRejectedError(
            status_code=404, title="Not Found"
        )

        with pytest.raises(ApiNotFound):
            ApiListingService(manager_api=port).list_apis(api_id=400)

    def test_404_on_catalog_listing_has_no_business_reading(self, port):
        port.list_catalog_apis.side_effect = ManagerApiTransportRejectedError(
            status_code=404, title="Not Found"
        )

        with pytest.raises(ApiCollectionError) as excinfo:
            ApiListingService(manager_api=port).list_apis(offset=0, limit=10)

        assert str(excinfo.value) == INTERNAL_ERROR_MESSAGE


def _catalog_row(api_id: int, visible: bool) -> ApiCatalogEntry:
    """GROUP do grupo da sessão (visível) ou de outro grupo (oculta)."""
    return _wire({
        "apiId": api_id, "apiName": f"API {api_id}", "description": "d",
        "version": "1", "basePath": f"/a{api_id}", "contextType": "GROUP",
        "contextGroupName": "APIOps" if visible else "Outro_Grupo",
        "owner": "alguem", "contextUserLogins": [], "revisions": [],
    })


class _PagedCatalog:
    """Fake do api-finder que honra `_offset`/`_limit` e registra as chamadas."""

    def __init__(self, rows, max_page=None, send_count=True, ignore_offset=False):
        self.rows = rows
        self.max_page = max_page
        self.send_count = send_count
        self.ignore_offset = ignore_offset
        self.calls = []

    def __call__(self, limit, offset=0, query=None):
        self.calls.append({"limit": limit, "offset": offset, "query": query})
        if self.max_page is not None and limit > self.max_page:
            raise ManagerApiResponseTooLargeError(
                status_code=413, title="BACKEND_RESPONSE_TOO_LARGE",
                code="BACKEND_RESPONSE_TOO_LARGE",
            )
        start = 0 if self.ignore_offset else offset
        page = self.rows[start : start + limit]
        return ApiCatalogPage(
            rows=page, total=len(self.rows) if self.send_count else -1
        )


def _paged_service(catalog, profile="developer"):
    port = MagicMock(spec=ManagerApiPort)
    port.list_catalog_apis.side_effect = catalog
    session = _make_session(profile=profile, groups=["APIOps"])
    return ApiListingService(manager_api=port, session=session)


class TestPagedCatalogScan:
    """Leitura paginada do catálogo (sen-list: Comando `sen list api`)."""

    def test_window_filled_on_first_page_costs_one_call(self):
        catalog = _PagedCatalog([_catalog_row(i, True) for i in range(1, 128)])

        result = _paged_service(catalog).list_apis(offset=0, limit=10)

        assert [e.id for e in result] == list(range(1, 11))
        assert catalog.calls == [{"limit": 25, "offset": 0, "query": None}]

    def test_no_request_ever_asks_more_than_one_page(self):
        catalog = _PagedCatalog([_catalog_row(i, True) for i in range(1, 128)])

        _paged_service(catalog).list_apis(offset=0, limit=100)

        assert all(call["limit"] <= 25 for call in catalog.calls)
        assert [c["offset"] for c in catalog.calls] == [0, 25, 50, 75]

    def test_low_visibility_keeps_reading_until_window_is_filled(self):
        # só 1 a cada 10 APIs é visível: 10 visíveis exigem ~100 linhas
        rows = [_catalog_row(i, i % 10 == 0) for i in range(1, 128)]
        catalog = _PagedCatalog(rows)

        result = _paged_service(catalog).list_apis(offset=0, limit=10)

        assert [e.id for e in result] == [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        assert [c["offset"] for c in catalog.calls] == [0, 25, 50, 75]

    def test_catalog_ends_before_window_is_filled(self):
        rows = [_catalog_row(i, i in (3, 40)) for i in range(1, 51)]
        catalog = _PagedCatalog(rows)

        result = _paged_service(catalog).list_apis(offset=0, limit=10)

        assert [e.id for e in result] == [3, 40]
        assert [c["offset"] for c in catalog.calls] == [0, 25]

    def test_window_offset_counts_over_visible_rows(self):
        rows = [_catalog_row(i, i % 2 == 0) for i in range(1, 61)]
        catalog = _PagedCatalog(rows)

        result = _paged_service(catalog).list_apis(offset=5, limit=3)

        assert [e.id for e in result] == [12, 14, 16]

    def test_413_halves_page_and_keeps_smaller_size_until_the_end(self):
        catalog = _PagedCatalog([_catalog_row(i, True) for i in range(1, 41)], max_page=12)

        result = _paged_service(catalog).list_apis(offset=0, limit=30)

        assert [e.id for e in result] == list(range(1, 31))
        assert [(c["limit"], c["offset"]) for c in catalog.calls] == [
            (25, 0), (12, 0), (12, 12), (12, 24),
        ]

    def test_halving_sequence_goes_down_to_one(self):
        catalog = _PagedCatalog([_catalog_row(i, True) for i in range(1, 4)], max_page=1)

        result = _paged_service(catalog).list_apis(offset=0, limit=2)

        assert [e.id for e in result] == [1, 2]
        assert [c["limit"] for c in catalog.calls] == [25, 12, 6, 3, 1, 1]

    def test_413_even_with_single_row_page_is_internal_error(self):
        catalog = _PagedCatalog([_catalog_row(1, True)], max_page=0)

        with pytest.raises(ApiCollectionError) as excinfo:
            _paged_service(catalog).list_apis(offset=0, limit=10)

        assert str(excinfo.value) == INTERNAL_ERROR_MESSAGE
        assert [c["limit"] for c in catalog.calls] == [25, 12, 6, 3, 1]

    def test_platform_ignoring_offset_stops_with_internal_error(self):
        rows = [_catalog_row(i, i == 1) for i in range(1, 60)]
        catalog = _PagedCatalog(rows, ignore_offset=True)

        with pytest.raises(ApiCollectionError) as excinfo:
            _paged_service(catalog).list_apis(offset=0, limit=10)

        assert str(excinfo.value) == INTERNAL_ERROR_MESSAGE
        assert len(catalog.calls) == 2  # a 2ª página idêntica interrompe o loop

    def test_row_repeated_across_pages_is_listed_once(self):
        rows = [_catalog_row(i, True) for i in range(1, 26)]
        # deslocamento concorrente: a API 25 reaparece no topo da 2ª página
        rows += [_catalog_row(25, True)] + [_catalog_row(i, True) for i in range(26, 30)]
        catalog = _PagedCatalog(rows)

        result = _paged_service(catalog).list_apis(offset=0, limit=50)

        assert [e.id for e in result] == list(range(1, 30))

    def test_super_admin_sends_offset_straight_to_the_server(self):
        catalog = _PagedCatalog([_catalog_row(i, False) for i in range(1, 128)])

        result = _paged_service(catalog, profile="super-admin").list_apis(offset=50, limit=10)

        assert [e.id for e in result] == list(range(51, 61))
        assert catalog.calls == [{"limit": 25, "offset": 50, "query": None}]

    def test_missing_count_header_stops_on_short_page(self):
        catalog = _PagedCatalog(
            [_catalog_row(i, i == 30) for i in range(1, 31)], send_count=False
        )

        result = _paged_service(catalog).list_apis(offset=0, limit=10)

        assert [e.id for e in result] == [30]
        assert [c["offset"] for c in catalog.calls] == [0, 25]

    def test_query_is_forwarded_on_every_page(self):
        rows = [_catalog_row(i, i % 10 == 0) for i in range(1, 80)]
        catalog = _PagedCatalog(rows)

        _paged_service(catalog).list_apis(query="pagamentos", offset=0, limit=5)

        assert len(catalog.calls) > 1
        assert all(c["query"] == "pagamentos" for c in catalog.calls)

    def test_without_limit_reads_the_whole_catalog(self):
        rows = [_catalog_row(i, i % 3 == 0) for i in range(1, 128)]
        catalog = _PagedCatalog(rows)

        result = _paged_service(catalog).list_apis(offset=0, limit=None)

        assert [e.id for e in result] == [i for i in range(1, 128) if i % 3 == 0]
        assert [c["offset"] for c in catalog.calls] == [0, 25, 50, 75, 100, 125]
