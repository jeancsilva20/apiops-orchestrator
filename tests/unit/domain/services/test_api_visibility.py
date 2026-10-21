import pytest

from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    _translate_row,
)
from apiops_orchestrator.domain.models.api_visibility_model import (
    ApiVisibility,
    OwnershipContext,
)
from apiops_orchestrator.domain.services.api_visibility import (
    from_api_payload,
    visible_to,
)


def _catalog(**overrides) -> ApiVisibility:
    base = {
        "id": 1,
        "name": "API",
        "contextType": None,
        "contextGroupName": None,
        "owner": None,
        "contextUserLogins": [],
    }
    base.update(overrides)
    entry = _translate_row(base)
    assert entry is not None
    return entry.visibility()


def test_organization_is_public():
    visibility = _catalog(contextType="ORGANIZATION", owner="paulo.silva")

    assert visible_to(visibility, "isaac.machado", []) is True
    assert visible_to(visibility, None, None) is True


def test_me_owner_matches_with_trim_casefold():
    visibility = _catalog(contextType="ME", owner=" Isaac.Machado ")

    assert visible_to(visibility, "isaac.machado", []) is True
    assert visible_to(visibility, "outro.user", []) is False


def test_me_individual_share_via_context_user_logins():
    visibility = _catalog(
        contextType="ME", owner="paulo.silva", contextUserLogins=["isaac.machado"]
    )

    assert visible_to(visibility, "isaac.machado", []) is True


def test_group_grants_only_by_session_group():
    visibility = _catalog(contextType="GROUP", contextGroupName="APIOps")

    assert visible_to(visibility, "isaac.machado", ["APIOps"]) is True
    assert visible_to(visibility, "isaac.machado", ["Lab-tech"]) is False


def test_group_owner_does_not_grant_access():
    visibility = _catalog(
        contextType="GROUP",
        contextGroupName="Lab-tech",
        owner="isaac.machado",
    )

    assert visible_to(visibility, "isaac.machado", ["APIOps"]) is False


def test_unknown_context_denies_by_default():
    visibility = _catalog(contextType="PARTNER")

    assert visible_to(visibility, "isaac.machado", ["APIOps"]) is False


def test_absent_context_denies_by_default():
    visibility = _catalog()

    assert visible_to(visibility, "isaac.machado", ["APIOps"]) is False


def test_super_admin_sees_everything():
    visibility = _catalog(contextType="GROUP", contextGroupName="Outro")

    assert visible_to(visibility, None, None, super_admin=True) is True


# --- GET /apis/{id} (formato sondado em 21/10/2026) ---------------------------


def test_payload_group_reads_group_name_and_owner():
    visibility = from_api_payload(
        {
            "visibility": {
                "id": -2,
                "visibilityType": "GROUP",
                "groupVisibility": {"name": "Arquitetura"},
                "owner": "paulo.silva@sensedia.com",
                "users": [],
            }
        }
    )

    assert visibility == ApiVisibility(
        context=OwnershipContext.GROUP,
        owner="paulo.silva@sensedia.com",
        groupName="Arquitetura",
    )


def test_payload_organization_without_owner():
    visibility = from_api_payload(
        {"visibility": {"id": 10580, "visibilityType": "ORGANIZATION", "users": []}}
    )

    assert visibility.context is OwnershipContext.ORGANIZATION
    assert visibility.owner is None


def test_payload_me_reads_usernames_of_users():
    visibility = from_api_payload(
        {
            "visibility": {
                "visibilityType": "me",
                "owner": "paulo.silva",
                "users": [{"id": 7, "username": "isaac.machado"}, {"id": 8}],
            }
        }
    )

    assert visibility.userLogins == ["isaac.machado"]
    assert visible_to(visibility, "isaac.machado", []) is True


@pytest.mark.parametrize(
    "api",
    [
        {},
        {"visibility": None},
        {"visibility": {"visibilityType": "EVERYONE", "owner": "isaac.machado"}},
        {"visibility": {"owner": "isaac.machado"}},
    ],
)
def test_payload_without_known_type_denies(api):
    assert visible_to(from_api_payload(api), "isaac.machado", ["APIOps"]) is False


def test_both_sources_give_the_same_visibility():
    catalog = _catalog(
        contextType="GROUP", contextGroupName="APIOps", owner="paulo.silva"
    )
    payload = from_api_payload(
        {
            "visibility": {
                "visibilityType": "GROUP",
                "groupVisibility": {"name": "APIOps"},
                "owner": "paulo.silva",
                "users": [],
            }
        }
    )

    assert catalog == payload
