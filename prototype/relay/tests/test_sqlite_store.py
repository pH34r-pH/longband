import sqlite3
import pytest

from longband_relay.sqlite_store import SqliteRelay


def test_ciphertext_survives_close_and_reopen(tmp_path):
    path = tmp_path / "longband.db"
    relay = SqliteRelay(path)
    first = relay.append("alpha", b"opaque-mls-a")
    relay.append("alpha", b"opaque-mls-b", (first.sequence,))
    relay.close()

    reopened = SqliteRelay(path)
    objects = reopened.read("alpha")
    assert [o.payload for o in objects] == [b"opaque-mls-a", b"opaque-mls-b"]
    assert objects[1].references == (objects[0].sequence,)
    reopened.close()


def test_schema_has_no_plaintext_or_key_columns(tmp_path):
    path = tmp_path / "longband.db"
    relay = SqliteRelay(path)
    relay.append("alpha", b"ciphertext")
    relay.close()

    db = sqlite3.connect(path)
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"relay_objects", "relay_references"} <= tables
    columns = {
        row[1].lower()
        for table in ("relay_objects", "relay_references")
        for row in db.execute(f"PRAGMA table_info({table})")
    }
    forbidden = {"plaintext", "decryption_key", "private_key", "group_secret", "exporter_secret"}
    assert columns.isdisjoint(forbidden)


def test_invalid_reference_rolls_back_object_insert(tmp_path):
    relay = SqliteRelay(tmp_path / "longband.db")
    with pytest.raises(ValueError):
        relay.append("alpha", b"ciphertext", (999,))
    assert relay.read("alpha") == ()
    relay.close()
