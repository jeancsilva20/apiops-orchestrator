from unittest.mock import MagicMock, call

import pytest

from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    _translate_row,
)
from apiops_orchestrator.application.exceptions.completeness_exceptions import (
    CompletenessDenied,
    CompletenessError,
    CompletenessNotFound,
    CompletenessPlatformError,
    CompletenessUnauthorized,
)
from apiops_orchestrator.application.services.completeness_service import (
    GATE_PERCENT_V1,
    CompletenessService,
)
from apiops_orchestrator.domain.models.catalog_revision_model import (
    CatalogRevisionCompleteness,
)
from apiops_orchestrator.domain.models.completeness_view import CompletenessView
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiPort,
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)

READING = CatalogRevisionCompleteness(
    score=85.0, suggestions=["primeira dica", "segunda dica", "terceira dica"]
)

IDENTITY_ROW = {
    "apiId": 375,
    "apiName": "Manager Training 1.0",
    "version": "1.0",
    "contextType": "ORGANIZATION",
    "owner": "trainer.sensedia",
    "revisions": [{"id": 5513, "revisionNumber": 3}],
}


@pytest.fixture
def port() -> MagicMock:
    return MagicMock(spec=ManagerApiPort)


def _entry():
    entry = _translate_row(IDENTITY_ROW)
    assert entry is not None
    return entry


def _sample_view(port: MagicMock) -> CompletenessView:
    port.get_revision_completeness.return_value = READING
    port.list_api_detail.return_value = _entry()
    return CompletenessService(port).get_completeness(375, 5513)


class TestHappyPath:
    def test_returns_typed_usecase_response(self, port):
        view = _sample_view(port)

        assert isinstance(view, CompletenessView)
        assert view.schema == "apiops.sen-completeness/v1"
        assert view.revision_id == 5513
        assert view.revision_number == 3  # mapa id→número do frame (IDENTITY_ROW)
        assert view.score == 85.0
        assert view.gate_percent == GATE_PERCENT_V1
        assert [(s.index, s.text) for s in view.suggestions] == [
            (1, "primeira dica"),
            (2, "segunda dica"),
            (3, "terceira dica"),
        ]

    def test_document_projections_matches_v1_tree_and_no_ghosts(self, port):
        view = _sample_view(port)

        document = view.to_document()

        assert document["schema"] == "apiops.sen-completeness/v1"
        assert document["revision"] == {"managerId": 5513, "revisionNumber": 3}
        assert document["maturity"] == {"score": 85.0}
        assert document["gate"] == {"percent": 70.0}
        assert document["suggestions"] == [
            {"index": 1, "text": "primeira dica"},
            {"index": 2, "text": "segunda dica"},
            {"index": 3, "text": "terceira dica"},
        ]
        assert set(document.keys()) == {
            "schema", "generatedAt", "api", "revision",
            "maturity", "gate", "suggestions",
        }

    def test_unmapped_revision_id_yields_number_null_honestly(self, port):
        port.get_revision_completeness.return_value = READING
        port.list_api_detail.return_value = _entry()

        view = CompletenessService(port).get_completeness(375, 9100)

        assert view.revision_id == 9100
        assert view.revision_number is None
        assert view.to_document()["revision"] == {
            "managerId": 9100, "revisionNumber": None
        }

    def test_identity_block_maps_strenum_context_as_plain_string(self, port):
        view = _sample_view(port)

        assert view.api.manager_id == 375
        assert view.api.name == "Manager Training 1.0"
        assert view.api.version == "1.0"
        assert view.api.context is not None
        assert view.api.context.type == "organization"  # StrEnum -> str puro
        assert view.api.context.owner == "trainer.sensedia"
    def test_document_echoes_identity_for_machine_channel(self, port):
        view = _sample_view(port)

        api = view.to_document()["api"]
        assert api == {
            "managerId": 375,
            "name": "Manager Training 1.0",
            "version": "1.0",
            "context": {
                "type": "organization", "groupName": None, "owner": "trainer.sensedia",
            },
        }

    def test_only_two_sources_are_contacted_no_ag_no_connect_catalog(self, port):
        _sample_view(port)

        assert port.method_calls == [
            call.get_revision_completeness(5513),
            call.list_api_detail(375),
        ]


class TestDegradableIdentity:
    def test_lookup_failure_yields_blind_identity_view(self, port):
        port.get_revision_completeness.return_value = READING
        port.list_api_detail.side_effect = RuntimeError("finder down")

        view = CompletenessService(port).get_completeness(375, 5513)

        assert view.api.manager_id == 375
        assert view.api.name is None
        assert view.api.version is None
        assert view.api.context is None
        assert view.score == 85.0

    def test_blind_document_nulls_identiy_but_keeps_ids(self, port):
        port.get_revision_completeness.return_value = READING
        port.list_api_detail.side_effect = RuntimeError("finder down")

        document = CompletenessService(port).get_completeness(375, 5513).to_document()

        assert document["api"] == {
            "managerId": 375, "name": None, "version": None, "context": None
        }
        assert document["revision"] == {"managerId": 5513, "revisionNumber": None}
        assert document["maturity"]["score"] == 85.0


class TestVisibilityMatrix:
    @staticmethod
    def _session(profile: str = "developer", groups=None):
        from apiops_orchestrator.domain.models.login_session_model import (
            PROFILE_SUPER_ADMIN,
            LoginSession,
        )

        if profile == PROFILE_SUPER_ADMIN:
            return LoginSession.model_validate({
                "accessToken": "x", "tokenType": "Bearer", "expiresIn": 3600,
                "scope": "list", "profile": profile, "adminAccessToken": "adm",
            })
        return LoginSession.model_validate({
            "accessToken": "x", "tokenType": "Bearer", "expiresIn": 3600,
            "scope": "list", "profile": profile,
            "userName": "isaac.machado", "userEmail": "i@sensedia.com",
            "userGroups": groups if groups is not None else ["APIOps"],
        })

    @classmethod
    def _view_with_identity(cls, port, identity_override: dict, profile: str = "developer") -> CompletenessView:
        port.get_revision_completeness.return_value = READING
        port.list_api_detail.return_value = _translate_row({**IDENTITY_ROW, **identity_override})
        service = CompletenessService(port, session=cls._session(profile=profile))
        return service.get_completeness(375, 5513)

    def test_group_owned_api_hidden_without_matching_group_degrades_identity(self, port):
        view = self._view_with_identity(port, {"contextType": "GROUP", "contextGroupName": "AnotherTeam"})

        assert view.api.name is None
        assert view.api.context is None
        assert view.score == 85.0

    def test_me_owned_api_visible_to_owner_session(self, port):
        view = self._view_with_identity(
            port,
            {"contextType": "ME", "owner": "isaac.machado"},
            profile="developer",
        )

        assert view.api.name == "Manager Training 1.0"
        assert view.api.context is not None and view.api.context.type == "me"

    def test_super_admin_sees_regardless_of_context(self, port):
        view = self._view_with_identity(
            port,
            {"contextType": "GROUP", "contextGroupName": "AnotherTeam"},
            profile="super-admin",
        )

        assert view.api.name == "Manager Training 1.0"

    def test_unknown_context_degrades_like_lookup_failure_never_error(self, port):
        view = self._view_with_identity(port, {"contextType": "UNKNOWN_CONTEXT"})

        assert view.api.name is None
        assert view.score == 85.0


class TestRefusalMapping:
    def test_404_maps_to_not_found(self, port):
        port.get_revision_completeness.side_effect = ManagerApiTransportRejectedError(
            status_code=404, title="Not Found"
        )

        with pytest.raises(CompletenessNotFound) as excinfo:
            CompletenessService(port).get_completeness(375, 5501)
        assert "5501" in str(excinfo.value)

    def test_401_maps_to_unauthorized(self, port):
        port.get_revision_completeness.side_effect = ManagerApiTransportRejectedError(
            status_code=401, title="Unauthorized"
        )

        with pytest.raises(CompletenessUnauthorized):
            CompletenessService(port).get_completeness(375, 5513)

    def test_403_maps_to_denied_same_facade_as_not_found(self, port):
        port.get_revision_completeness.side_effect = ManagerApiTransportRejectedError(
            status_code=403, title="Forbidden"
        )

        with pytest.raises(CompletenessDenied) as excinfo:
            CompletenessService(port).get_completeness(375, 5513)
        assert str(excinfo.value) == str(CompletenessNotFound(5513))

    def test_409_wraps_into_platform_error(self, port):
        port.get_revision_completeness.side_effect = ManagerApiTransportRejectedError(
            status_code=409, title="Conflict"
        )

        with pytest.raises(CompletenessPlatformError):
            CompletenessService(port).get_completeness(375, 5513)

    def test_unavailable_maps_to_platform_error(self, port):
        port.get_revision_completeness.side_effect = (
            ManagerApiTransportUnavailableError("timeout")
        )

        with pytest.raises(CompletenessPlatformError):
            CompletenessService(port).get_completeness(375, 5513)


def test_all_errors_share_exit_code_two_bucket():
    assert CompletenessError("x").exit_code == 2
    assert CompletenessNotFound(1).exit_code == 2
    assert CompletenessUnauthorized().exit_code == 2
    assert CompletenessDenied(1).exit_code == 2
    assert CompletenessPlatformError("boom").exit_code == 2
