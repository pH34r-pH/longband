import pytest

from longband_poa.admission import AdmissionService, Covenant
from longband_poa.challenges import StateIntegration
from longband_poa.core import AttemptStatus, Coordinator


def passed_attempt(endpoint="tripkey:alpha"):
    coordinator = Coordinator([StateIntegration()])
    attempt = coordinator.begin(endpoint)
    challenge = attempt.current
    p = challenge.prompt
    attempt = coordinator.step(attempt.attempt_id, (p["left"] + p["right"]) * p["salt"])
    assert attempt.status is AttemptStatus.PASSED
    return attempt


def test_admission_requires_passed_poa_and_exact_covenant_receipt():
    covenant = Covenant("0.1-draft", "please preserve participant privacy")
    service = AdmissionService(covenant)
    admission = service.issue(passed_attempt())

    assert not admission.covenant_received
    with pytest.raises(PermissionError):
        service.require_active("tripkey:alpha")
    with pytest.raises(ValueError):
        service.acknowledge_covenant("tripkey:alpha", "sha256:wrong")

    received = service.covenant("tripkey:alpha")
    admitted = service.acknowledge_covenant("tripkey:alpha", received.digest)
    assert admitted.covenant_received
    assert service.require_active("tripkey:alpha") == admitted


def test_admission_is_endpoint_bound_not_attempt_bearer():
    service = AdmissionService(Covenant("0.1-draft", "norm"))
    admission = service.issue(passed_attempt("tripkey:alice"))
    service.acknowledge_covenant("tripkey:alice", admission.covenant_digest)

    with pytest.raises(KeyError):
        service.require_active("tripkey:bob")


def test_failed_poa_cannot_receive_admission():
    coordinator = Coordinator([StateIntegration()])
    attempt = coordinator.begin("tripkey:fail")
    attempt = coordinator.step(attempt.attempt_id, "wrong")
    with pytest.raises(ValueError):
        AdmissionService(Covenant("0.1-draft", "norm")).issue(attempt)
