import pytest

from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.services.session_access import (
    Access,
    first_unmet,
    meets,
)


def _developer(groups=("APIOps",), scope="write") -> LoginSession:
    return LoginSession(
        accessToken="dev",
        tokenType="Bearer",
        expiresIn=3600,
        scope=scope,
        profile="developer",
        userName="dev.user",
        userEmail="dev@company.test",
        userGroups=list(groups),
    )


def _super_admin() -> LoginSession:
    return LoginSession(
        accessToken="admin",
        tokenType="Bearer",
        expiresIn=3600,
        scope="admin",
        profile="super-admin",
        adminAccessToken="admin",
    )


@pytest.mark.parametrize("group", ["APIOps", "apiops", "  APIOPS  "])
def test_developer_in_the_team_meets_it_ignoring_case_and_spaces(group):
    assert meets(_developer(groups=("Lab-tech", group)), Access.APIOPS_TEAM)


@pytest.mark.parametrize("groups", [("Lab-tech",), ("API Ops",), ("APIOps-dev",)])
def test_developer_outside_the_team_does_not_meet_it(groups):
    assert not meets(_developer(groups=groups), Access.APIOPS_TEAM)


@pytest.mark.parametrize("scope", ["write", "WRITE", " write "])
def test_write_scope_meets_write(scope):
    assert meets(_developer(scope=scope), Access.WRITE)


@pytest.mark.parametrize("scope", ["read", "apis/read", "admin", "write-only"])
def test_other_scopes_do_not_meet_write(scope):
    assert not meets(_developer(scope=scope), Access.WRITE)


def test_developer_never_meets_pipeline():
    assert not meets(_developer(), Access.PIPELINE)


@pytest.mark.parametrize("access", list(Access))
def test_super_admin_meets_every_requirement(access):
    assert meets(_super_admin(), access)


def test_first_unmet_follows_the_given_order():
    session = _developer(groups=("Lab-tech",), scope="read")

    assert first_unmet(session, (Access.APIOPS_TEAM, Access.WRITE)) is Access.APIOPS_TEAM
    assert first_unmet(session, (Access.WRITE, Access.APIOPS_TEAM)) is Access.WRITE


def test_first_unmet_is_none_when_all_are_met():
    assert first_unmet(_developer(), (Access.APIOPS_TEAM, Access.WRITE)) is None
