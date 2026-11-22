import pytest

from apiops_orchestrator.domain.models.governance_model import GovernanceAvailability


@pytest.mark.parametrize(
    "availability, absent",
    [
        (GovernanceAvailability.ENABLED, False),
        (GovernanceAvailability.UNKNOWN, False),
        (GovernanceAvailability.DISABLED, True),
    ],
)
def test_only_a_confirmed_absence_turns_the_governance_off(availability, absent):
    assert availability.absent is absent


def test_availability_compares_as_its_text_value():
    assert GovernanceAvailability.DISABLED == "disabled"
    assert GovernanceAvailability("unknown") is GovernanceAvailability.UNKNOWN
