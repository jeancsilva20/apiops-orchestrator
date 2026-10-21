from apiops_orchestrator.application.services.api_access_guard import ApiAccessGuard
from apiops_orchestrator.domain.models.api_visibility_model import (
    ApiVisibility,
    OwnershipContext,
)
from apiops_orchestrator.domain.models.login_session_model import LoginSession

GRUPO_ALHEIO = ApiVisibility(context=OwnershipContext.GROUP, groupName="Lab-tech")
GRUPO_DA_SESSAO = ApiVisibility(context=OwnershipContext.GROUP, groupName="APIOps")


def _session(profile: str = "developer") -> LoginSession:
    payload = {
        "accessToken": "x",
        "tokenType": "Bearer",
        "expiresIn": 3600,
        "scope": "list",
        "profile": profile,
    }
    if profile == "developer":
        payload.update(
            userName="isaac.machado",
            userEmail="isaac.machado@sensedia.com",
            userGroups=["APIOps"],
        )
    return LoginSession.model_validate(payload)


def test_dev_sees_only_what_the_rule_allows():
    guard = ApiAccessGuard(_session())

    assert guard.sees_everything() is False
    assert guard.can_see(GRUPO_DA_SESSAO) is True
    assert guard.can_see(GRUPO_ALHEIO) is False


def test_super_admin_sees_everything():
    guard = ApiAccessGuard(_session("super-admin"))

    assert guard.sees_everything() is True
    assert guard.can_see(GRUPO_ALHEIO) is True
    assert guard.can_see(ApiVisibility()) is True


def test_without_session_nothing_is_hidden():
    guard = ApiAccessGuard(None)

    assert guard.sees_everything() is True
    assert guard.can_see(GRUPO_ALHEIO) is True
