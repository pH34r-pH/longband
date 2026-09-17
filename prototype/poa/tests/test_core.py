from longband_poa.challenges import ConstraintRevision, StateIntegration
from longband_poa.core import AttemptStatus, Coordinator


def solve(challenge):
    prompt = challenge.prompt
    if challenge.family == "state-integration":
        return (prompt["left"] + prompt["right"]) * prompt["salt"]
    if challenge.family == "constraint-revision":
        return prompt["original_limit"] + prompt["revision"]
    raise AssertionError(challenge.family)


def test_attempt_is_endpoint_bound_and_passes_all_steps():
    coordinator = Coordinator([StateIntegration(), ConstraintRevision()])
    attempt = coordinator.begin("tripkey:test-endpoint")

    assert attempt.endpoint_key == "tripkey:test-endpoint"
    assert attempt.status is AttemptStatus.ACTIVE

    while attempt.current is not None:
        attempt = coordinator.step(attempt.attempt_id, solve(attempt.current))

    assert attempt.status is AttemptStatus.PASSED
    assert len(attempt.transitions) == 2
    assert all(t.accepted for t in attempt.transitions)


def test_wrong_transition_fails_without_advancing():
    coordinator = Coordinator([StateIntegration(), ConstraintRevision()])
    attempt = coordinator.begin("tripkey:test-endpoint")
    attempt = coordinator.step(attempt.attempt_id, "wrong")

    assert attempt.status is AttemptStatus.FAILED
    assert attempt.index == 0
    assert len(attempt.transitions) == 1
    assert not attempt.transitions[0].accepted
