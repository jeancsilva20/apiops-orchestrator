from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    _translate_row,
)
from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from apiops_orchestrator.domain.services.catalog_visibility import (
    finder_row_visible_to,
    finder_rows_visible_to,
)


def _context_entry(**overrides) -> ApiCatalogEntry:
    base = {
        "id": 1,
        "name": overrides.pop("name", "API"),
        "contextType": None,
        "contextGroupName": None,
        "owner": None,
        "contextUserLogins": [],
    }
    base.update(overrides)
    entry = _translate_row(base)
    assert entry is not None
    return entry


def test_organization_is_public():
    entry = _context_entry(contextType="ORGANIZATION", owner="paulo.silva")

    assert finder_row_visible_to(entry, "isaac.machado", []) is True
    assert finder_row_visible_to(entry, None, None) is True


def test_me_owner_matches_with_trim_casefold():
    entry = _context_entry(contextType="ME", owner=" Isaac.Machado ")

    assert finder_row_visible_to(entry, "isaac.machado", []) is True
    assert finder_row_visible_to(entry, "outro.user", []) is False


def test_me_individual_share_via_context_user_logins():
    entry = _context_entry(
        contextType="ME", owner="paulo.silva", contextUserLogins=["isaac.machado"]
    )

    assert finder_row_visible_to(entry, "isaac.machado", []) is True


def test_group_grants_only_by_session_group():
    entry = _context_entry(contextType="GROUP", contextGroupName="APIOps")

    assert finder_row_visible_to(entry, "isaac.machado", ["APIOps"]) is True
    assert finder_row_visible_to(entry, "isaac.machado", ["Lab-tech"]) is False


def test_group_owner_does_not_grant_access():
    entry = _context_entry(
        contextType="GROUP",
        contextGroupName="Lab-tech",
        owner="isaac.machado",
    )

    assert finder_row_visible_to(entry, "isaac.machado", ["APIOps"]) is False


def test_unknown_context_denies_by_default():
    entry = _context_entry(contextType="PARTNER")

    assert finder_row_visible_to(entry, "isaac.machado", ["APIOps"]) is False


def test_absent_context_denies_by_default():
    entry = _context_entry()

    assert finder_row_visible_to(entry, "isaac.machado", ["APIOps"]) is False


def test_super_admin_sees_everything():
    entry = _context_entry(contextType="GROUP", contextGroupName="Outro")

    assert finder_row_visible_to(entry, None, None, super_admin=True) is True


def test_matrix_over_list_filters_rows():
    entries = [
        e
        for e in (
            _translate_row(r)
            for r in (
                {"id": 1, "contextType": "ORGANIZATION", "name": "Pub"},
                {"id": 2, "contextType": "ME", "owner": "isaac.machado", "name": "Minha"},
                {"id": 3, "contextType": "GROUP", "contextGroupName": "APIOps", "name": "Grp"},
                {"id": 4},
            )
        )
        if e is not None
    ]

    rows = finder_rows_visible_to(entries, "isaac.machado", ["APIOps"])

    assert [e.name for e in rows] == ["Pub", "Minha", "Grp"]
