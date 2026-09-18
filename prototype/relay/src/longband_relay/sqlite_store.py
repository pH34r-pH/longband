from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .core import RelayObject


class SqliteRelay:
    """Durable opaque relay store.

    Schema intentionally contains only routing metadata and opaque payload
    bytes. No MLS/group/application key columns exist.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._db = sqlite3.connect(self._path)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS relay_objects (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                payload BLOB NOT NULL,
                received_ns INTEGER NOT NULL
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS relay_references (
                object_sequence INTEGER NOT NULL,
                reference_sequence INTEGER NOT NULL,
                PRIMARY KEY (object_sequence, reference_sequence),
                FOREIGN KEY (object_sequence) REFERENCES relay_objects(sequence),
                FOREIGN KEY (reference_sequence) REFERENCES relay_objects(sequence)
            )
        """)
        self._db.commit()

    def append(self, topic: str, payload: bytes, references: tuple[int, ...] = ()) -> RelayObject:
        if not topic:
            raise ValueError("topic is required")
        if not payload:
            raise ValueError("opaque payload is required")
        for reference in references:
            if self._db.execute("SELECT 1 FROM relay_objects WHERE sequence = ?", (reference,)).fetchone() is None:
                raise ValueError("reference must identify an existing relay object")
        received_ns = time.time_ns()
        with self._db:
            cursor = self._db.execute(
                "INSERT INTO relay_objects(topic, payload, received_ns) VALUES (?, ?, ?)",
                (topic, sqlite3.Binary(payload), received_ns),
            )
            sequence = int(cursor.lastrowid)
            self._db.executemany(
                "INSERT INTO relay_references(object_sequence, reference_sequence) VALUES (?, ?)",
                [(sequence, r) for r in references],
            )
        return RelayObject(sequence, topic, bytes(payload), tuple(references), received_ns)

    def read(self, topic: str, after: int = 0) -> tuple[RelayObject, ...]:
        if after < 0:
            raise ValueError("cursor cannot be negative")
        rows = self._db.execute(
            "SELECT sequence, topic, payload, received_ns FROM relay_objects WHERE topic = ? AND sequence > ? ORDER BY sequence",
            (topic, after),
        ).fetchall()
        result = []
        for sequence, row_topic, payload, received_ns in rows:
            refs = tuple(r[0] for r in self._db.execute(
                "SELECT reference_sequence FROM relay_references WHERE object_sequence = ? ORDER BY reference_sequence",
                (sequence,),
            ).fetchall())
            result.append(RelayObject(sequence, row_topic, bytes(payload), refs, received_ns))
        return tuple(result)

    def close(self) -> None:
        self._db.close()
