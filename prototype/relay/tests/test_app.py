from fastapi.testclient import TestClient
from longband_relay.app import app

def test_combined_asgi_serves_http_discovery():
    with TestClient(app) as client:
        response = client.get("/.well-known/longband")
        assert response.status_code == 200
        assert response.json()["name"] == "Longband"

def test_combined_asgi_apex_bootstraps_cold_agent():
    with TestClient(app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "/agent.md" in root.text
        assert "/.well-known/longband" in root.text
        assert "/openapi.json" in root.text
        assert "/llms.txt" in root.text
        assert "/mcp" in root.text

        agent = client.get("/agent.md")
        assert agent.status_code == 200
        assert agent.headers["content-type"].startswith("text/markdown")
