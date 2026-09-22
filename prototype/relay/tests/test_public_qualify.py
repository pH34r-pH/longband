from __future__ import annotations

import base64

from longband_relay.http import app
from fastapi.testclient import TestClient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import public_qualify


class Response:
    def __init__(self, response):
        self.response = response
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def __iter__(self):
        return iter(self.response.content.splitlines())
    def read(self, *args):
        return self.response.content
    def getcode(self):
        return self.response.status_code


def test_public_qualifier_exercises_full_vertical_slice(monkeypatch):
    client = TestClient(app)

    def urlopen(req, timeout=15):
        path = req.full_url.removeprefix("https://example.test")
        body = None
        if req.data:
            import json
            body = json.loads(req.data)
        response = client.request(req.method, path, json=body)
        response.raise_for_status()
        class Wrapped:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return response.content
        return Wrapped()

    monkeypatch.setattr(public_qualify.urllib.request, "urlopen", urlopen)
    result = public_qualify.qualify("https://example.test", "qualification-test")
    assert result["status"] == "passed"
    assert result["poa_families"] == ["state-integration", "constraint-revision"]
    assert result["sequence"] >= 1
