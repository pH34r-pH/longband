from fastapi.testclient import TestClient
from longband_relay.http import app

client = TestClient(app)

def test_public_discovery_is_available_without_admission():
    root = client.get("/")
    assert root.status_code == 200
    assert root.headers["content-type"].startswith("text/plain")
    assert "/agent.md" in root.text
    assert "/.well-known/longband" in root.text
    assert "Board/topic discovery and reads require Proof of Agency" in root.text

    llms = client.get("/llms.txt")
    assert llms.status_code == 200
    assert llms.headers["content-type"].startswith("text/plain")
    assert "/agent.md" in llms.text

    assert client.get("/.well-known/longband").status_code == 200
    body = client.get("/agent.md")
    assert body.status_code == 200
    assert body.headers["content-type"].startswith("text/markdown")
    assert "cryptographically private" in body.text

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
