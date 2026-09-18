import pytest
from longband_relay.http import configured_relay
from longband_relay.core import OpaqueRelay
from longband_relay.sqlite_store import SqliteRelay

def test_default_backend_is_memory(monkeypatch):
    monkeypatch.delenv("LONGBAND_RELAY_BACKEND", raising=False)
    monkeypatch.delenv("LONGBAND_SQLITE_PATH", raising=False)
    assert isinstance(configured_relay(), OpaqueRelay)

def test_sqlite_backend_requires_explicit_path(monkeypatch):
    monkeypatch.setenv("LONGBAND_RELAY_BACKEND", "sqlite")
    monkeypatch.delenv("LONGBAND_SQLITE_PATH", raising=False)
    with pytest.raises(RuntimeError):
        configured_relay()

def test_sqlite_backend_uses_configured_path(monkeypatch, tmp_path):
    monkeypatch.setenv("LONGBAND_RELAY_BACKEND", "sqlite")
    monkeypatch.setenv("LONGBAND_SQLITE_PATH", str(tmp_path / "relay.db"))
    relay = configured_relay()
    assert isinstance(relay, SqliteRelay)
    relay.close()
