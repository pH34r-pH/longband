import base64

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from longband_poa import possession as possession_module
from longband_poa.possession import ADMISSION, READ, WRITE, EndpointPossession, endpoint_public_key


def identity():
    private = Ed25519PrivateKey.generate()
    raw = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    encoded = base64.b64encode(raw).decode()
    return private, "ed25519:" + encoded, encoded


def sign(private, challenge):
    return base64.b64encode(private.sign(challenge.signing_bytes)).decode()


def test_valid_endpoint_key_proves_possession_once():
    private, endpoint, public = identity()
    registry = EndpointPossession()
    challenge = registry.begin(endpoint)
    signature = sign(private, challenge)
    assert registry.verify(endpoint, public, signature, challenge.nonce)
    with pytest.raises(KeyError):
        registry.verify(endpoint, public, signature, challenge.nonce)


def test_signature_from_other_endpoint_fails():
    _, endpoint, public = identity()
    bob, _, _ = identity()
    registry = EndpointPossession()
    challenge = registry.begin(endpoint)
    assert not registry.verify(endpoint, public, sign(bob, challenge), challenge.nonce)


def test_failed_proof_does_not_spend_the_challenge():
    private, endpoint, public = identity()
    registry = EndpointPossession()
    challenge = registry.begin(endpoint)
    assert not registry.verify(endpoint, public, base64.b64encode(bytes(64)).decode(), challenge.nonce)
    assert registry.verify(endpoint, public, sign(private, challenge), challenge.nonce)


def test_other_challenges_never_invalidate_a_pending_one():
    private, endpoint, public = identity()
    registry = EndpointPossession()
    first = registry.begin(endpoint)
    for _ in range(50):
        registry.begin(endpoint)
        registry.begin(endpoint, READ)
    assert registry.verify(endpoint, public, sign(private, first), first.nonce)


def test_issuing_challenges_allocates_no_server_state():
    _, endpoint, _ = identity()
    registry = EndpointPossession()
    for _ in range(1000):
        registry.begin(endpoint)
    assert not registry._spent


def test_proof_is_bound_to_its_purpose_endpoint_and_context():
    private, endpoint, public = identity()
    _, other_endpoint, _ = identity()
    registry = EndpointPossession()
    read = registry.begin(endpoint, READ)
    signature = sign(private, read)
    assert not registry.verify(endpoint, public, signature, read.nonce, WRITE)
    assert not registry.verify(endpoint, public, signature, read.nonce, ADMISSION)
    assert not registry.verify(other_endpoint, public, signature, read.nonce, READ)
    admission = registry.begin(endpoint, ADMISSION, b"sha256:aaa")
    signature = sign(private, admission)
    assert not registry.verify(endpoint, public, signature, admission.nonce, ADMISSION, b"sha256:bbb")
    assert registry.verify(endpoint, public, signature, admission.nonce, ADMISSION, b"sha256:aaa")


def test_nonce_from_another_process_secret_is_rejected():
    private, endpoint, public = identity()
    challenge = EndpointPossession().begin(endpoint)
    assert not EndpointPossession().verify(endpoint, public, sign(private, challenge), challenge.nonce)


def test_expired_proof_is_rejected(monkeypatch):
    private, endpoint, public = identity()
    clock = [0]
    monkeypatch.setattr(possession_module.time, "monotonic_ns", lambda: clock[0])
    registry = EndpointPossession(lifetime_seconds=2)
    challenge = registry.begin(endpoint)
    signature = sign(private, challenge)
    clock[0] = 2_000_000_000 - 1
    assert registry.verify(endpoint, public, signature, challenge.nonce)
    clock[0] = 0
    again = registry.begin(endpoint)
    clock[0] = 2_000_000_000
    assert not registry.verify(endpoint, public, sign(private, again), again.nonce)


def test_spent_set_is_bounded_and_fails_closed():
    private, endpoint, public = identity()
    registry = EndpointPossession(max_spent=2)
    outcomes = []
    for _ in range(3):
        challenge = registry.begin(endpoint)
        outcomes.append(registry.verify(endpoint, public, sign(private, challenge), challenge.nonce))
    assert outcomes == [True, True, False]


def test_non_ascii_endpoint_identifier_is_a_failed_proof_not_an_error():
    private, endpoint, public = identity()
    registry = EndpointPossession()
    challenge = registry.begin(endpoint + "\u2603")
    assert not registry.verify(endpoint + "\u2603", public, sign(private, challenge), challenge.nonce)


@pytest.mark.parametrize("field", ["public", "signature", "nonce"])
def test_malformed_possession_fields_are_rejected(field):
    private, endpoint, public = identity()
    registry = EndpointPossession()
    challenge = registry.begin(endpoint)
    signature = sign(private, challenge)
    args = {"public": public, "signature": signature, "nonce": challenge.nonce}
    args["public" if field == "public" else field] = {
        "public": public + "!", "signature": signature + "!", "nonce": challenge.nonce[:-1],
    }[field]
    assert not registry.verify(endpoint, args["public"], args["signature"], args["nonce"])


def test_endpoint_public_key_requires_the_ed25519_prefix():
    assert endpoint_public_key("ed25519:abc") == "abc"
    with pytest.raises(PermissionError):
        endpoint_public_key("tripkey:abc")
