from fastapi.testclient import TestClient
from longband_relay.app import app

def test_combined_asgi_serves_discovery_and_bootstraps_cold_agent():
    with TestClient(app) as client:
        discovery = client.get("/.well-known/longband")
        assert discovery.status_code == 200
        assert discovery.json()["name"] == "Longband"

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
