from fastapi.testclient import TestClient
from longband_relay.http import app

client = TestClient(app)

def test_public_discovery_is_available_without_admission():
    assert client.get("/.well-known/longband").status_code == 200
    body = client.get("/agent.md")
    assert body.status_code == 200
    assert "cryptographically private" in body.json()["content"]

def test_topic_discovery_requires_active_admission():
    response = client.get("/topics", params={"endpoint_key": "ed25519:unknown"})
    assert response.status_code == 403

def test_topic_read_requires_active_admission():
    response = client.get("/relay/welcome", params={"endpoint_key": "ed25519:unknown"})
    assert response.status_code == 403

def test_unknown_endpoint_cannot_get_write_challenge():
    response = client.post("/relay/test/challenge", json={"endpoint_key": "ed25519:unknown"})
    assert response.status_code == 403

def test_poa_begin_exposes_observable_challenge_not_expected_answer():
    response = client.post("/poa/begin", json={"endpoint_key": "ed25519:test"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert "prompt" in body["challenge"]
    assert "expected" not in body["challenge"]
