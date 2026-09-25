from pathlib import Path
from typing import List
from unittest.mock import MagicMock

import pytest

from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    _translate_row,
)
from apiops_orchestrator.application.exceptions.listing_exceptions import (
    InvalidWindow,
)
from apiops_orchestrator.application.services.api_listing_service import ApiListingService
from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from apiops_orchestrator.domain.ports.manager_api_port import ApiCatalogPage, ManagerApiPort
from apiops_orchestrator.infrastructure.utils.text_normalizer import accent_fold

FIXTURE_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "apis_sample.json"

ARRIVAL_IDS = [400, 530, 312, 512, 401]


def _load_fixture() -> List[dict]:
    import json

    with open(FIXTURE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _entries() -> List[ApiCatalogEntry]:
    return [e for e in (_translate_row(r) for r in _load_fixture()) if e is not None]


def _matches(entry: ApiCatalogEntry, query: str) -> bool:
    folded = accent_fold(query)
    haystack = (entry.name, entry.description)
    return any(folded in accent_fold(part) for part in haystack if part)


@pytest.fixture
def mock_manager_api():
    mock = MagicMock(spec=ManagerApiPort)
    pool = _entries()

    def _server_like_list_catalog_apis(limit: int, query: str | None = None, **_):
        universe = pool if not query else [e for e in pool if _matches(e, query)]
        rows = universe[: max(limit, 1)]
        return ApiCatalogPage(rows=rows, total=len(universe))

    mock.list_catalog_apis.side_effect = _server_like_list_catalog_apis
    return mock


def _service(mock_manager_api) -> ApiListingService:
    return ApiListingService(manager_api=mock_manager_api, session=None)


class TestCatalogFlowUnfiltered:
    def test_preserves_server_order(self, mock_manager_api):
        result = _service(mock_manager_api).list_apis()

        assert [e.id for e in result] == ARRIVAL_IDS

    def test_forwards_query_to_the_port_contract(self, mock_manager_api):
        _service(mock_manager_api).list_apis(query="orchestrator")

        mock_manager_api.list_catalog_apis.assert_any_call(
            limit=1, query="orchestrator"
        )

    def test_fetch_grows_when_server_signals_more_universe(self, mock_manager_api):
        mock = MagicMock(spec=ManagerApiPort)
        stub_pages = [
            ApiCatalogPage(rows=_entries()[:1], total=5),
            ApiCatalogPage(rows=_entries(), total=5),
        ]
        mock.list_catalog_apis.side_effect = [*stub_pages]
        service = ApiListingService(manager_api=mock, session=None)

        result = service.list_apis(offset=2, limit=2)

        assert [e.id for e in result] == [312, 512]
        mock.list_catalog_apis.assert_any_call(limit=4, query=None)
        mock.list_catalog_apis.assert_any_call(limit=5, query=None)


class TestQueryServerSideFiltering:
    def test_accent_folded_match_case_insensitive(self, mock_manager_api):
        rows = _service(mock_manager_api).list_apis(query="autenticacao")

        assert [e.id for e in rows] == [400, 401]

    def test_matches_description_field(self, mock_manager_api):
        rows = _service(mock_manager_api).list_apis(query="entregas")

        assert [e.id for e in rows] == [512]

    def test_no_results_yields_empty(self, mock_manager_api):
        assert _service(mock_manager_api).list_apis(query="zzz-inexistente") == []

    def test_none_query_is_no_op(self, mock_manager_api):
        rows = _service(mock_manager_api).list_apis()

        assert [e.id for e in rows] == ARRIVAL_IDS


class TestWindowOverArrivalOrder:
    def test_slice_after_offset(self, mock_manager_api):
        rows = _service(mock_manager_api).list_apis(offset=2, limit=2)

        assert [e.id for e in rows] == [312, 512]

    def test_offset_beyond_total_returns_empty(self, mock_manager_api):
        rows = _service(mock_manager_api).list_apis(offset=99, limit=5)

        assert rows == []

    def test_zero_offset_is_start_of_page(self, mock_manager_api):
        rows = _service(mock_manager_api).list_apis(offset=0, limit=2)

        assert [e.id for e in rows] == [400, 530]

    def test_offset_alone_starts_from_offset(self, mock_manager_api):
        rows = _service(mock_manager_api).list_apis(offset=3)

        assert [e.id for e in rows] == [512, 401]


class TestWindowValidationFailFast:
    def test_zero_limit_blocked_before_network(self, mock_manager_api):
        with pytest.raises(InvalidWindow, match="--limit deve ser maior que zero"):
            _service(mock_manager_api).list_apis(limit=0)
        with pytest.raises(InvalidWindow, match="--limit deve ser maior que zero"):
            _service(mock_manager_api).list_apis(offset=1, limit=-3)

        mock_manager_api.list_catalog_apis.assert_not_called()

    def test_negative_offset_blocked_before_network(self, mock_manager_api):
        with pytest.raises(InvalidWindow, match="--offset deve ser maior ou igual a zero"):
            _service(mock_manager_api).list_apis(offset=-1, limit=5)
        with pytest.raises(InvalidWindow, match="--offset deve ser maior ou igual a zero"):
            _service(mock_manager_api).list_apis(offset=-2)

        mock_manager_api.list_catalog_apis.assert_not_called()
