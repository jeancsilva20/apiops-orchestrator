from apiops_orchestrator.domain.models.api_catalog_model import (
    ApiCatalogEntry,
    OwnershipContext,
)
from apiops_orchestrator.domain.models.catalog_revision_model import (
    CatalogRevision,
    CatalogRevisionInfo,
)


def full_frame() -> dict:
    return {
        "id": 375,
        "name": "Manager Training 1.0",
        "description": "API de treinamento",
        "version": "1.0",
        "contextType": "organization",
        "contextGroupName": "",
        "owner": "trainer.sensedia",
        "revisions": [],
        "futureUnknownBlock": {"ignored": True},
    }


def test_unknown_wire_fields_are_discarded():
    entry = ApiCatalogEntry.model_validate(full_frame())

    assert not hasattr(entry, "futureUnknownBlock")


def test_full_frame_keeps_declared_fields():
    entry = ApiCatalogEntry.model_validate(full_frame())

    assert entry.id == 375
    assert entry.name == "Manager Training 1.0"
    assert entry.version == "1.0"
    assert entry.owner == "trainer.sensedia"


def test_sparse_frame_degrades_without_raising():
    entry = ApiCatalogEntry.model_validate({"id": 400})

    assert entry.name is None
    assert entry.contextType is None
    assert entry.revisions == []
    assert entry.last_revision_number() is None


def test_context_type_holds_ownership_enum():
    entry = ApiCatalogEntry.model_validate(
        {"id": 1, "contextType": OwnershipContext.ME, "owner": "isaac.machado"}
    )

    assert entry.contextType is OwnershipContext.ME


def test_revisions_hold_the_aggregate_shape():
    entry = ApiCatalogEntry.model_validate(
        {
            "id": 1,
            "revisions": [
                {
                    "id": 10,
                    "revisionNumber": 2,
                    "environments": ["Development"],
                    "completenessScore": 70.5,
                    "workflowId": 7,
                    "workflowStageId": 12,
                }
            ],
        }
    )

    rev = entry.revisions[0]
    assert rev.id == 10
    assert rev.revisionNumber == 2
    assert rev.environments == ["Development"]
    assert rev.completenessScore == 70.5
    assert rev.workflowId == 7
    assert rev.workflowStageId == 12


def test_revisions_environments_defaults_to_empty():
    entry = ApiCatalogEntry.model_validate(
        {"id": 1, "revisions": [{"id": 10}]}
    )

    assert entry.revisions[0].environments == []


def test_last_revision_number_without_source_is_none():
    entry = ApiCatalogEntry.model_validate({})

    assert entry.last_revision_number() is None


def test_listing_dict_keeps_canonical_line_shape():
    entry = ApiCatalogEntry.model_validate(
        {"id": 375, "name": "Manager Training 1.0", "lastRevisionNumber": 4}
    )

    assert entry.to_listing_dict() == {
        "id": 375,
        "name": "Manager Training 1.0",
        "description": None,
        "version": None,
        "basePath": None,
        "lifeCycle": None,
        "owner": None,
        "updateDate": None,
        "lastRevision": {"revisionNumber": 4},
    }


def test_catalog_revision_info_carries_crud_data():
    row = CatalogRevisionInfo(
        revision_id=8862,
        revision_number=1,
        stage_name="Stage One",
        environments="Default, HMG",
        completeness_score=85.0,
    )

    assert row.to_dict() == {
        "revision_id": 8862,
        "revision_number": 1,
        "stage_name": "Stage One",
        "environments": "Default, HMG",
        "completeness_score": 85.0,
    }


def test_catalog_revision_info_score_defaults_none():
    row = CatalogRevisionInfo(
        revision_id=1, revision_number=1, stage_name=None, environments=""
    )

    assert row.completeness_score is None
