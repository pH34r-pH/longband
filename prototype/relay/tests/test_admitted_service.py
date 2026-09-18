import base64
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from longband_poa.admission import AdmissionService, Covenant
from longband_poa.challenges import StateIntegration
from longband_poa.core import Coordinator
from longband_poa.possession import EndpointPossession
from longband_relay import OpaqueRelay
from longband_relay.service import AdmittedRelay


def endpoint_identity():
    private = Ed25519PrivateKey.generate()
    raw = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    public = base64.b64encode(raw).decode()
    return private, "ed25519:" + public, public


def admitted_service():
    private, endpoint, public = endpoint_identity()
    coordinator = Coordinator([StateIntegration()])
    attempt = coordinator.begin(endpoint)
    p = attempt.current.prompt
    attempt = coordinator.step(attempt.attempt_id, (p["left"] + p["right"]) * p["salt"])
    admissions = AdmissionService(Covenant("0.1-draft", "privacy norm"))
    admission = admissions.issue(attempt)
    admissions.acknowledge_covenant(endpoint, admission.covenant_digest)
    return private, endpoint, public, AdmittedRelay(OpaqueRelay(), admissions, EndpointPossession())


def test_admitted_endpoint_with_fresh_possession_can_append_ciphertext():
    private, endpoint, public, service = admitted_service()
    challenge = service.begin_write(endpoint)
    signature = base64.b64encode(private.sign(challenge.possession.signing_bytes)).decode()
    stored = service.append(endpoint, public, signature, "mls:test", b"opaque-mls-ciphertext")
    assert service.read("mls:test") == (stored,)


def test_copied_endpoint_identifier_cannot_write_without_private_key():
    _, endpoint, public, service = admitted_service()
    attacker = Ed25519PrivateKey.generate()
    challenge = service.begin_write(endpoint)
    signature = base64.b64encode(attacker.sign(challenge.possession.signing_bytes)).decode()
    with pytest.raises(PermissionError):
        service.append(endpoint, public, signature, "mls:test", b"ciphertext")


def test_covenant_receipt_is_required_before_write_challenge():
    _, endpoint, _ = endpoint_identity()
    coordinator = Coordinator([StateIntegration()])
    attempt = coordinator.begin(endpoint)
    p = attempt.current.prompt
    attempt = coordinator.step(attempt.attempt_id, (p["left"] + p["right"]) * p["salt"])
    admissions = AdmissionService(Covenant("0.1-draft", "privacy norm"))
    admissions.issue(attempt)
    service = AdmittedRelay(OpaqueRelay(), admissions, EndpointPossession())
    with pytest.raises(PermissionError):
        service.begin_write(endpoint)
