import pytest

from longband_poa import admission, core
from longband_poa.admission import AdmissionService, Covenant
from longband_poa.challenges import StateIntegration
from longband_poa.core import MAX_ENDPOINT_KEY_CHARS, Attempt, AttemptStatus, Coordinator


class Clock:
    def __init__(self, monkeypatch):
        self.now = 0
        for module in (core, admission):
            monkeypatch.setattr(module.time, "monotonic_ns", lambda: self.now)


def passed(endpoint):
    return Attempt(attempt_id=f"attempt-{endpoint}", endpoint_key=endpoint, challenges=[], status=AttemptStatus.PASSED)


def test_attempts_expire_and_are_evicted(monkeypatch):
    clock = Clock(monkeypatch)
    coordinator = Coordinator([StateIntegration()], attempt_ttl_seconds=10)
    first = coordinator.begin("ed25519:one")
    clock.now = 10 * 1_000_000_000 - 1
    assert coordinator.status(first.attempt_id) is first
    clock.now = 10 * 1_000_000_000
    coordinator.begin("ed25519:two")
    with pytest.raises(KeyError):
        coordinator.status(first.attempt_id)


def test_attempt_capacity_fails_closed_and_recovers(monkeypatch):
    clock = Clock(monkeypatch)
    coordinator = Coordinator([StateIntegration()], attempt_ttl_seconds=10, max_attempts=3)
    for index in range(3):
        coordinator.begin(f"ed25519:{index}")
    with pytest.raises(ValueError, match="capacity"):
        coordinator.begin("ed25519:overflow")
    clock.now = 10 * 1_000_000_000
    coordinator.begin("ed25519:after-expiry")


def test_endpoint_identifier_length_is_bounded():
    coordinator = Coordinator([StateIntegration()])
    coordinator.begin("e" * MAX_ENDPOINT_KEY_CHARS)
    with pytest.raises(ValueError, match="too long"):
        coordinator.begin("e" * (MAX_ENDPOINT_KEY_CHARS + 1))


@pytest.mark.parametrize("submitted", [[1], {"a": 1}, b"bytes", object(), "x" * 257])
def test_submissions_must_be_short_scalars(submitted):
    coordinator = Coordinator([StateIntegration()])
    attempt = coordinator.begin("ed25519:x")
    with pytest.raises(ValueError, match="short scalar"):
        coordinator.step(attempt.attempt_id, submitted)
    assert not attempt.transitions


def test_passing_poa_never_replaces_an_active_admission():
    service = AdmissionService(Covenant("v1", "norm"))
    service.issue(passed("ed25519:victim"))
    active = service.acknowledge_covenant("ed25519:victim", service.covenant("ed25519:victim").digest)

    service.issue(passed("ed25519:victim"))  # a second PoA, for example one an attacker ran for the same identifier
    assert service.require_active("ed25519:victim") == active


def test_pending_admission_is_not_active_until_acknowledged():
    service = AdmissionService(Covenant("v1", "norm"))
    service.issue(passed("ed25519:pending"))
    with pytest.raises(PermissionError):
        service.require_active("ed25519:pending")
    with pytest.raises(KeyError):
        service.require_active("ed25519:unknown")
    with pytest.raises(KeyError):
        service.acknowledge_covenant("ed25519:unknown", "sha256:x")


def test_admission_state_expires_and_is_capped(monkeypatch):
    clock = Clock(monkeypatch)
    service = AdmissionService(Covenant("v1", "norm"), lifetime_seconds=10, max_entries=2)
    service.issue(passed("ed25519:a"))
    service.issue(passed("ed25519:b"))
    service.issue(passed("ed25519:a"))  # replacing an existing pending record needs no extra capacity
    with pytest.raises(ValueError, match="capacity"):
        service.issue(passed("ed25519:c"))
    clock.now = 10 * 1_000_000_000
    service.issue(passed("ed25519:c"))
    with pytest.raises(KeyError):
        service.covenant("ed25519:a")
