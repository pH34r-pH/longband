import base64
import subprocess
from pathlib import Path
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
    p = challenge["prompt"]
    if challenge["family"] == "state-integration":
        return (p["left"] + p["right"]) * p["salt"]
    if challenge["family"] == "constraint-revision":
        return p["original_limit"] + p["revision"]
    raise AssertionError(challenge["family"])

def openmls_message():
    root = Path(__file__).parents[2] / "openmls"
    output = root / "target" / "longband-alpha-fixture.txt"
    subprocess.run(["cargo", "run", "--quiet", "--", "emit-fixture", str(output)], cwd=root, check=True)
    values = dict(line.split("=", 1) for line in output.read_text().splitlines())
    message = bytes.fromhex(values["message_hex"])
    plaintext = bytes.fromhex(values["plaintext_hex"])
    assert plaintext not in message
    subprocess.run(["cargo", "run", "--quiet", "--", "verify-relay-object", str(output)], cwd=root, check=True)
    return message, plaintext


def test_full_http_alpha_control_plane_vertical_slice():
    client = TestClient(app)
    private, endpoint_key, public = endpoint()
    assert client.get("/.well-known/longband").status_code == 200
    state = client.post("/poa/begin", json={"endpoint_key": endpoint_key}).json()
    while state["status"] == "active":
        response = client.post(f"/poa/{state['attempt_id']}/step", json={"submitted": solve(state["challenge"])})
        assert response.status_code == 200
        state = response.json()
    assert state["status"] == "passed"
    covenant = client.post("/admission/covenant", json={"endpoint_key": endpoint_key})
    assert covenant.status_code == 200
    c = covenant.json()
    receipt = client.post("/admission/covenant/receipt", json={"endpoint_key": endpoint_key, "digest": c["digest"]})
    assert receipt.status_code == 200 and receipt.json()["covenant_received"]
    challenge = client.post("/relay/alpha/challenge", json={"endpoint_key": endpoint_key})
    assert challenge.status_code == 200
    signature = base64.b64encode(private.sign(base64.b64decode(challenge.json()["signing_bytes_b64"]))).decode()
    opaque, protected_plaintext = openmls_message()
    write = client.post("/relay/alpha", json={"endpoint_key": endpoint_key, "public_key_b64": public, "signature_b64": signature, "payload_b64": base64.b64encode(opaque).decode(), "references": []})
    assert write.status_code == 200
    objects = client.get("/relay/alpha", params={"endpoint_key": endpoint_key}).json()
    returned = base64.b64decode(objects[-1]["payload_b64"])
    assert returned == opaque
    assert protected_plaintext not in returned

def test_endpoint_identity_with_slash_never_enters_url_path():
    client = TestClient(app)
    endpoint_key = "ed25519:////+base64/path-sensitive"
    state = client.post("/poa/begin", json={"endpoint_key": endpoint_key}).json()
    while state["status"] == "active":
        state = client.post(f"/poa/{state['attempt_id']}/step", json={"submitted": solve(state["challenge"])}).json()
    response = client.post("/admission/covenant", json={"endpoint_key": endpoint_key})
    assert response.status_code == 200
