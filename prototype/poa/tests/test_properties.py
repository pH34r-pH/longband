from dataclasses import dataclass
from unittest.mock import patch

from hypothesis import given, strategies as st

from longband_poa import challenges
from longband_poa.admission import AdmissionService, Covenant
from longband_poa.core import Attempt, AttemptStatus, Challenge, Coordinator


@st.composite
def endpoint_keys(draw):
    suffix = draw(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=32))
    return f"tripkey:{suffix}"


@dataclass(frozen=True)
class FixedChallenge:
    challenge: Challenge

    def generate(self) -> Challenge:
        return self.challenge


@given(
    left=st.integers(min_value=100, max_value=999),
    right=st.integers(min_value=100, max_value=999),
    salt=st.integers(min_value=3, max_value=99),
)
def test_state_integration_expected_is_derived_from_fresh_prompt(left, right, salt):
    values = iter((left - 100, right - 100, salt - 3))
    with patch.object(challenges.secrets, "randbelow", side_effect=lambda _bound: next(values)):
        challenge = challenges.StateIntegration().generate()

    assert challenge.prompt["left"] == left
    assert challenge.prompt["right"] == right
    assert challenge.prompt["salt"] == salt
    assert challenge.expected == (left + right) * salt


@given(endpoint=endpoint_keys(), expected=st.integers(min_value=-1000, max_value=1000))
def test_coordinator_accepts_the_exact_expected_value_for_arbitrary_challenges(endpoint, expected):
    challenge = Challenge(family="property", prompt={}, expected=expected)
    coordinator = Coordinator([FixedChallenge(challenge)])

    attempt = coordinator.begin(endpoint)
    completed = coordinator.step(attempt.attempt_id, expected)

    assert completed.status is AttemptStatus.PASSED
    assert completed.index == 1
    assert completed.transitions[0].accepted


@given(endpoint=endpoint_keys(), other=endpoint_keys())
def test_admission_activation_is_bound_to_the_receiving_endpoint(endpoint, other):
    if endpoint == other:
        return

    attempt = Attempt(
        attempt_id="property-attempt",
        endpoint_key=endpoint,
        challenges=[],
        status=AttemptStatus.PASSED,
    )
    service = AdmissionService(Covenant("0.1-draft", "property norm"))
    admission = service.issue(attempt)

    assert not admission.active_for(endpoint)
    admitted = service.acknowledge_covenant(endpoint, admission.covenant_digest)

    assert admitted.active_for(endpoint)
    assert not admitted.active_for(other)
