from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    _build_custom_search,
    _merge_wire_blocks,
    _resolve_last_revision_number,
    _translate_row,
)
from apiops_orchestrator.domain.models.api_catalog_model import (
    ApiCatalogEntry,
    OwnershipContext,
)


def _row(raw) -> ApiCatalogEntry:
    entry = _translate_row(raw)
    assert entry is not None
    return entry


def test_translation_returns_none_without_identifiable_id():
    assert _translate_row({"apiName": "Sem id"}) is None
    assert _translate_row("nope") is None
    assert _translate_row(None) is None


def test_listing_aliases_map_to_canonical_fields():
    entry = _row(
        {
            "apiId": 7,
            "apiName": "Pública",
            "description": "d",
            "version": "1",
            "basePath": "/p/v1",
            "apiLifeCycle": "PUBLISHED",
            "owner": "dueño",
            "contextType": "ME",
            "contextGroupName": "g",
            "contextUserLogins": ["isaac.machado"],
            "lastRevision": 5,
            "revisions": [{"id": 5, "revisionNumber": 1}],
        }
    )

    assert entry is not None
    assert entry.id == 7
    assert entry.name == "Pública"
    assert entry.lifeCycle == "PUBLISHED"
    assert entry.last_revision_number() == 1
    assert entry.contextUserLogins == ["isaac.machado"]


def test_blank_strings_become_none_and_valid_survive():
    entry = _row(
        {"apiId": 9, "apiName": "   ", "description": "", "owner": "ok.user"}
    )

    assert entry.name is None
    assert entry.description is None
    assert entry.owner == "ok.user"


def test_numeric_wire_values_are_coerced_and_junk_row_is_dropped():
    entry = _row(
        {"apiId": "375", "revisions": [{"id": "10", "revisionNumber": "2"}]}
    )
    assert entry.id == 375
    assert entry.revisions[0].revisionNumber == 2

    junky = _translate_row({"apiId": "abc", "revisions": [{}]})
    assert junky is None


def test_context_type_maps_case_insensitive_and_unknown_denies():
    mapped = _translate_row({"apiId": 1, "contextType": " OrganiZation "})
    assert mapped.contextType is OwnershipContext.ORGANIZATION

    stranger = _translate_row({"apiId": 2, "contextType": "PARTNER"})
    assert stranger.contextType is None


def test_merge_attaches_environments_completeness_and_workflow():
    raw = {
        "revisions": [
            {"id": 5513, "revisionNumber": 3},
            {"id": 5514, "revisionNumber": 4},
        ],
        "completeness": [
            {"score": "70.5", "apiRevision": "5513"},
            {"score": 85.0, "apiRevision": 5514},
            {"score": "not-a-number", "apiRevision": 5514},
        ],
        "environments": [
            {"name": "Development", "apiRevision": 5514},
            {"name": "Homologação", "apiRevision": 5513},
            {"name": "", "apiRevision": 5514},
            {"name": "Orfã", "apiRevision": 9999},
        ],
        "wokflow": [
            {"workflowId": 7, "workflowStageId": 12, "apiRevision": 5513},
        ],
    }

    revisions = {r.id: r for r in _merge_wire_blocks(raw)}

    assert revisions[5514].environments == ["Development"]
    assert revisions[5513].environments == ["Homologação"]
    assert revisions[5513].completenessScore == 70.5
    assert revisions[5514].completenessScore == 85.0
    assert revisions[5514].workflowStageId is None
    assert revisions[5513].workflowStageId == 12


def test_merge_first_score_wins_and_later_is_ignored():
    raw = {
        "revisions": [{"id": 9}],
        "completeness": [
            {"score": 10.0, "apiRevision": 9},
            {"score": 99.0, "apiRevision": 9},
        ],
    }

    (rev,) = _merge_wire_blocks(raw)

    assert rev.completenessScore == 10.0


def test_merge_last_workflow_ref_wins():
    raw = {
        "revisions": [{"id": 9}],
        "wokflow": [
            {"workflowId": 1, "workflowStageId": 11, "apiRevision": 9},
            {"workflowId": 2, "workflowStageId": 22, "apiRevision": 9},
        ],
    }

    (rev,) = _merge_wire_blocks(raw)

    assert (rev.workflowId, rev.workflowStageId) == (2, 22)


def test_resolve_last_revision_object_direct_number():
    assert _resolve_last_revision_number({"lastRevision": {"revisionNumber": 4}}, []) == 4


def test_resolve_last_revision_scalar_resolves_by_id_never_falls_back():
    revisions = _merge_wire_blocks(
        {"revisions": [{"id": 77, "revisionNumber": 8}, {"id": 88, "revisionNumber": 9}]}
    )

    assert _resolve_last_revision_number({"lastRevision": 88}, revisions) == 9
    assert _resolve_last_revision_number({"lastRevision": 99}, revisions) is None
    assert _resolve_last_revision_number({}, revisions) is None


def test_build_custom_search_quotes_both_fields_and_strips_breakers():
    built = _build_custom_search('orchestrator "x"')

    assert built == '(apiName:"orchestrator x" OR description:"orchestrator x")'
