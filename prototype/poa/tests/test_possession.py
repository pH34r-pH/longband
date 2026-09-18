import base64
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from longband_poa.possession import EndpointPossession

def identity():
    private = Ed25519PrivateKey.generate()
    raw = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    encoded = base64.b64encode(raw).decode()
    return private, "ed25519:" + encoded, encoded

def test_valid_endpoint_key_proves_possession_once():
    private, endpoint, public = identity()
    registry = EndpointPossession()
    challenge = registry.begin(endpoint)
    signature = base64.b64encode(private.sign(challenge.signing_bytes)).decode()
    assert registry.verify(endpoint, public, signature)
    with pytest.raises(KeyError):
        registry.verify(endpoint, public, signature)

def test_signature_from_other_endpoint_fails():
    _, endpoint, public = identity()
    bob, _, _ = identity()
    registry = EndpointPossession()
    challenge = registry.begin(endpoint)
    signature = base64.b64encode(bob.sign(challenge.signing_bytes)).decode()
    assert not registry.verify(endpoint, public, signature)
