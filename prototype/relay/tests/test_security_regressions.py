"""Regression tests for the Longband Alpha relay security advisories.

Each test states the attack as an attacker with no private key would attempt it
against the public HTTP surface. They run in-process; nothing here talks to a network.
"""

import base64

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient

from longband_poa.admission import AdmissionService, Covenant
from longband_poa.challenges import ConstraintRevision, StateIntegration
from longband_poa.core import Coordinator
from longband_poa.possession import EndpointPossession
from longband_relay import OpaqueRelay, http
from longband_relay.core import MAX_PAYLOAD_BYTES, MAX_REFERENCES, MAX_TOPIC_CHARS
from longband_relay.limits import MAX_BODY_BYTES
from longband_relay.service import AdmittedRelay


class Participant:
    def __init__(self, private=None):
        self.private = private or Ed25519PrivateKey.generate()
        self.public = base64.b64encode(
            self.private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ).decode()
        self.endpoint = "ed25519:" + self.public

    def sign(self, challenge):
        return base64.b64encode(self.private.sign(base64.b64decode(challenge["signing_bytes_b64"]))).decode()


def solve(challenge):
    p = challenge["prompt"]
    if challenge["family"] == "state-integration":
        return (p["left"] + p["right"]) * p["salt"]
    return p["original_limit"] + p["revision"]


@pytest.fixture
def client(monkeypatch):
    coordinator = Coordinator([StateIntegration(), ConstraintRevision()])
    admissions = AdmissionService(Covenant("test", "privacy norm"))
    service = AdmittedRelay(OpaqueRelay(), admissions, EndpointPossession())
    for name, value in (("coordinator", coordinator), ("admissions", admissions), ("service", service)):
        monkeypatch.setattr(http, name, value)
    return TestClient(http.app)


def pass_poa(client, endpoint):
    state = client.post("/poa/begin", json={"endpoint_key": endpoint}).json()
    while state["status"] == "active":
        state = client.post(f"/poa/{state['attempt_id']}/step", json={"submitted": solve(state["challenge"])}).json()
    assert state["status"] == "passed"


def receipt(client, endpoint, *, signer=None, digest=None):
    covenant = client.post("/admission/covenant", json={"endpoint_key": endpoint}).json()
    body = {"endpoint_key": endpoint, "digest": digest or covenant["digest"]}
    if signer is not None:
        body |= {"nonce_b64": covenant["possession"]["nonce_b64"], "signature_b64": signer.sign(covenant["possession"])}
    return client.post("/admission/covenant/receipt", json=body)


def admit(client, participant):
    pass_poa(client, participant.endpoint)
    assert receipt(client, participant.endpoint, signer=participant).status_code == 200


def write(client, participant, payload=b"ciphertext", topic="secret-topic", *, signer=None, references=()):
    challenge = client.post(f"/relay/{topic}/challenge", json={"endpoint_key": participant.endpoint}).json()
    return client.post(f"/relay/{topic}", json={
        "endpoint_key": participant.endpoint,
        "public_key_b64": participant.public,
        "signature_b64": (signer or participant).sign(challenge),
        "nonce_b64": challenge["nonce_b64"],
        "payload_b64": base64.b64encode(payload).decode(),
        "references": list(references),
    })


def read_headers(client, endpoint, signer):
    challenge = client.post("/relay/any/challenge", json={"endpoint_key": endpoint, "purpose": "read"}).json()
    return {"X-Longband-Nonce": challenge["nonce_b64"], "X-Longband-Signature": signer.sign(challenge)}


# -- Advisory 1: reads authorize on a public identifier -------------------------------


def test_public_key_alone_cannot_read_or_list(client):
    victim, attacker = Participant(), Participant()
    admit(client, victim)
    assert write(client, victim).status_code == 200

    assert client.get("/relay/secret-topic", params={"endpoint_key": victim.endpoint}).status_code == 403
    assert client.get("/topics", params={"endpoint_key": victim.endpoint}).status_code == 403
    # A challenge is obtainable for the victim's identifier, but only the victim's key can answer it.
    forged = read_headers(client, victim.endpoint, attacker)
    assert client.get("/relay/secret-topic", params={"endpoint_key": victim.endpoint}, headers=forged).status_code == 403
    assert client.get("/topics", params={"endpoint_key": victim.endpoint}, headers=forged).status_code == 403

    headers = read_headers(client, victim.endpoint, victim)
    assert client.get("/relay/secret-topic", params={"endpoint_key": victim.endpoint}, headers=headers).status_code == 200


def test_read_proof_is_one_use(client):
    victim = Participant()
    admit(client, victim)
    write(client, victim)
    headers = read_headers(client, victim.endpoint, victim)
    params = {"endpoint_key": victim.endpoint}
    assert client.get("/topics", params=params, headers=headers).status_code == 200
    assert client.get("/topics", params=params, headers=headers).status_code == 403


def test_write_proof_cannot_be_used_to_read(client):
    victim = Participant()
    admit(client, victim)
    challenge = client.post("/relay/t/challenge", json={"endpoint_key": victim.endpoint}).json()
    headers = {"X-Longband-Nonce": challenge["nonce_b64"], "X-Longband-Signature": victim.sign(challenge)}
    assert client.get("/topics", params={"endpoint_key": victim.endpoint}, headers=headers).status_code == 403


def test_scripted_poa_for_an_unowned_identifier_cannot_activate_or_read(client):
    for invented in ("attacker-made-up-string", "ed25519:" + base64.b64encode(bytes(32)).decode()):
        pass_poa(client, invented)
        assert receipt(client, invented).status_code == 400
        attacker = Participant()
        assert receipt(client, invented, signer=attacker).status_code == 400
        assert client.get("/topics", params={"endpoint_key": invented}).status_code == 403


def test_covenant_receipt_proof_is_bound_to_the_covenant_digest(client):
    participant = Participant()
    pass_poa(client, participant.endpoint)
    covenant = client.post("/admission/covenant", json={"endpoint_key": participant.endpoint}).json()
    stale = receipt(client, participant.endpoint, signer=participant, digest="sha256:" + "0" * 64)
    assert stale.status_code == 400
    ok = client.post("/admission/covenant/receipt", json={
        "endpoint_key": participant.endpoint, "digest": covenant["digest"],
        "nonce_b64": covenant["possession"]["nonce_b64"], "signature_b64": participant.sign(covenant["possession"]),
    })
    assert ok.status_code == 200


# -- Advisory 2: admission replacement and challenge burning --------------------------


def test_poa_for_a_victim_key_does_not_replace_or_deactivate_the_victim(client):
    victim = Participant()
    admit(client, victim)
    assert write(client, victim).status_code == 200

    pass_poa(client, victim.endpoint)  # the attacker re-runs scriptable PoA for the victim's identifier
    assert receipt(client, victim.endpoint, signer=Participant()).status_code == 400

    headers = read_headers(client, victim.endpoint, victim)
    assert client.get("/topics", params={"endpoint_key": victim.endpoint}, headers=headers).status_code == 200
    assert write(client, victim).status_code == 200


def test_junk_requests_cannot_burn_or_replace_the_victims_write_challenge(client):
    victim = Participant()
    admit(client, victim)
    challenge = client.post("/relay/secret-topic/challenge", json={"endpoint_key": victim.endpoint}).json()

    for _ in range(25):
        client.post("/relay/secret-topic/challenge", json={"endpoint_key": victim.endpoint})
        junk = client.post("/relay/secret-topic", json={
            "endpoint_key": victim.endpoint, "public_key_b64": victim.public,
            "signature_b64": base64.b64encode(bytes(64)).decode(),
            "nonce_b64": challenge["nonce_b64"], "payload_b64": "eA==",
        })
        assert junk.status_code == 403

    stored = client.post("/relay/secret-topic", json={
        "endpoint_key": victim.endpoint, "public_key_b64": victim.public,
        "signature_b64": victim.sign(challenge), "nonce_b64": challenge["nonce_b64"],
        "payload_b64": base64.b64encode(b"ciphertext").decode(),
    })
    assert stored.status_code == 200


def test_a_spent_write_proof_cannot_be_replayed(client):
    victim = Participant()
    admit(client, victim)
    challenge = client.post("/relay/t/challenge", json={"endpoint_key": victim.endpoint}).json()
    body = {
        "endpoint_key": victim.endpoint, "public_key_b64": victim.public,
        "signature_b64": victim.sign(challenge), "nonce_b64": challenge["nonce_b64"], "payload_b64": "eA==",
    }
    assert client.post("/relay/t", json=body).status_code == 200
    assert client.post("/relay/t", json=body).status_code == 403


# -- Advisory 3: unbounded state and request sizes ----------------------------------


def test_oversized_identifier_is_rejected_without_allocating_state(client):
    response = client.post("/poa/begin", json={"endpoint_key": "A" * 5_000_000})
    assert response.status_code == 413
    response = client.post("/poa/begin", json={"endpoint_key": "A" * 4096})
    assert response.status_code == 422
    assert not http.coordinator._attempts


def test_request_bodies_are_capped_even_when_streamed(client):
    declared = client.post("/poa/begin", content=b"x" * (MAX_BODY_BYTES + 1), headers={"content-type": "application/json"})
    assert declared.status_code == 413

    def chunks():
        for _ in range(MAX_BODY_BYTES // 1024 + 2):
            yield b"x" * 1024

    streamed = client.post("/poa/begin", content=chunks(), headers={"content-type": "application/json"})
    assert streamed.status_code == 413
    assert streamed.json() == {"detail": "Request too large"}


@pytest.mark.parametrize("value", [[1], {"a": 1}, "x" * 300])
def test_poa_submissions_must_be_short_scalars(client, value):
    state = client.post("/poa/begin", json={"endpoint_key": "ed25519:x"}).json()
    response = client.post(f"/poa/{state['attempt_id']}/step", json={"submitted": value})
    assert response.status_code == 422


def test_relay_write_limits(client):
    victim = Participant()
    admit(client, victim)
    assert write(client, victim, payload=b"\x01" * (MAX_PAYLOAD_BYTES + 1)).status_code == 403
    assert not http.service._relay.read("secret-topic")
    assert write(client, victim, references=range(1, MAX_REFERENCES + 2)).status_code == 422
    long_topic = "t" * (MAX_TOPIC_CHARS + 1)
    assert client.post(f"/relay/{long_topic}/challenge", json={"endpoint_key": victim.endpoint}).status_code == 422
    assert write(client, victim, payload=b"\x01" * MAX_PAYLOAD_BYTES).status_code == 200


def test_stores_enforce_the_same_limits(tmp_path):
    from longband_relay.sqlite_store import SqliteRelay

    for relay in (OpaqueRelay(), SqliteRelay(tmp_path / "relay.sqlite3")):
        with pytest.raises(ValueError):
            relay.append("t", b"\x01" * (MAX_PAYLOAD_BYTES + 1))
        with pytest.raises(ValueError):
            relay.append("t" * (MAX_TOPIC_CHARS + 1), b"\x01")
        with pytest.raises(ValueError):
            relay.append("t", b"\x01", tuple(range(1, MAX_REFERENCES + 2)))
        assert not relay.read("t")
