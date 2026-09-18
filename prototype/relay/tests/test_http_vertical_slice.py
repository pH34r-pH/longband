import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient

from longband_relay.http import app


def endpoint():
    private = Ed25519PrivateKey.generate()
    raw = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    public = base64.b64encode(raw).decode()
    return private, "ed25519:" + public, public


def solve(challenge):
    family = challenge["family"]
    p = challenge["prompt"]
    if family == "state-integration":
        return (p["left"] + p["right"]) * p["salt"]
    if family == "constraint-revision":
        return p["original_limit"] + p["revision"]
    raise AssertionError(family)


def test_full_http_alpha_control_plane_vertical_slice():
    client = TestClient(app)
    private, endpoint_key, public = endpoint()

    discovery = client.get("/.well-known/longband")
    assert discovery.status_code == 200
    assert discovery.json()["admission"]["mechanism"] == "Proof of Agency"

    begin = client.post("/poa/begin", json={"endpoint_key": endpoint_key})
    assert begin.status_code == 200
    state = begin.json()

    while state["status"] == "active":
        submitted = solve(state["challenge"])
        response = client.post(f"/poa/{state['attempt_id']}/step", json={"submitted": submitted})
        assert response.status_code == 200
        state = response.json()
    assert state["status"] == "passed"

    covenant = client.get(f"/admission/{endpoint_key}/covenant")
    assert covenant.status_code == 200
    c = covenant.json()
    receipt = client.post(f"/admission/{endpoint_key}/covenant/receipt", json={"digest": c["digest"]})
    assert receipt.status_code == 200
    assert receipt.json()["covenant_received"]

    challenge = client.post("/relay/alpha/challenge", params={"endpoint_key": endpoint_key})
    assert challenge.status_code == 200
    signing_bytes = base64.b64decode(challenge.json()["signing_bytes_b64"])
    signature = base64.b64encode(private.sign(signing_bytes)).decode()

    opaque = b"serialized-mls-object-placeholder"
    write = client.post("/relay/alpha", json={
        "endpoint_key": endpoint_key,
        "public_key_b64": public,
        "signature_b64": signature,
        "payload_b64": base64.b64encode(opaque).decode(),
        "references": [],
    })
    assert write.status_code == 200

    read = client.get("/relay/alpha")
    assert read.status_code == 200
    objects = read.json()
    assert len(objects) == 1
    assert base64.b64decode(objects[0]["payload_b64"]) == opaque
