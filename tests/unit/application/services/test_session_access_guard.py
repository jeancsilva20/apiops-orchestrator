import pytest

from apiops_orchestrator.application.exceptions.access_exceptions import (
    AccessDeniedError,
)
from apiops_orchestrator.application.exceptions.login_exceptions import LoginError
from apiops_orchestrator.application.services.session_access_guard import (
    PIPELINE_DENIED,
    TEAM_DENIED,
    require_access,
)
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.services.session_access import Access


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


def test_without_session_leaves_the_refusal_to_the_token_resolution():
    require_access(None, Access.WRITE, Access.PIPELINE, command="validate")


def test_team_is_always_required_even_without_extra_requirements():
    with pytest.raises(AccessDeniedError) as caught:
        require_access(_developer(groups=("Lab-tech",)))

    assert caught.value.message == TEAM_DENIED


def test_team_is_checked_before_the_extra_requirements():
    with pytest.raises(AccessDeniedError) as caught:
        require_access(
            _developer(groups=("Lab-tech",), scope="read"), Access.WRITE, command="validate"
        )

    assert caught.value.message == TEAM_DENIED


def test_write_refusal_names_the_command_and_the_session_scope():
    with pytest.raises(AccessDeniedError) as caught:
        require_access(
            _developer(scope="read"),
            Access.WRITE,
            command="validate",
            outcome="Nada foi publicado.",
        )

    message = caught.value.message
    assert "`sen validate`" in message
    assert "scope `write`" in message
    assert "sua sessão tem `read`" in message
    assert "sen login" in message
    assert message.endswith("\n\nNada foi publicado.")


def test_pipeline_refusal_names_the_command():
    with pytest.raises(AccessDeniedError) as caught:
        require_access(_developer(), Access.PIPELINE, command="deploy")

    assert caught.value.message == PIPELINE_DENIED.format(command="deploy")


@pytest.mark.parametrize("required", [(), (Access.WRITE,), (Access.PIPELINE,)])
def test_super_admin_passes_everything(required):
    require_access(_super_admin(), *required, command="publish")


def test_developer_meeting_everything_passes():
    require_access(_developer(), Access.WRITE, command="validate")


def test_refusal_is_a_login_error_with_exit_code_1():
    with pytest.raises(LoginError) as caught:
        require_access(_developer(scope="read"), Access.WRITE, command="validate")

    assert caught.value.exit_code == 1


def test_messages_never_name_the_pipeline_configuration():
    for session, required in (
        (_developer(groups=("Lab-tech",)), ()),
        (_developer(scope="read"), (Access.WRITE,)),
        (_developer(), (Access.PIPELINE,)),
    ):
        with pytest.raises(AccessDeniedError) as caught:
            require_access(session, *required, command="publish")
        for name in ("pipeline", "EXECUTION_MODE"):
            assert name not in caught.value.message
