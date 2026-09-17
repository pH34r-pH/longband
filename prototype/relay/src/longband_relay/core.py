from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass(frozen=True)
class RelayObject:
    sequence: int
    topic: str
    payload: bytes
    references: tuple[int, ...]
    received_ns: int


class OpaqueRelay:
    """In-memory ciphertext/object relay with no content interpretation."""

    def __init__(self) -> None:
        self._objects: list[RelayObject] = []

    def append(
        self,
        topic: str,
        payload: bytes,
        references: tuple[int, ...] = (),
    ) -> RelayObject:
        if not topic:
            raise ValueError("topic is required")
        if not payload:
            raise ValueError("opaque payload is required")
        known = {obj.sequence for obj in self._objects}
        if any(reference not in known for reference in references):
            raise ValueError("reference must identify an existing relay object")
        obj = RelayObject(
            sequence=len(self._objects) + 1,
            topic=topic,
            payload=bytes(payload),
            references=tuple(references),
            received_ns=time.time_ns(),
        )
        self._objects.append(obj)
        return obj

    def read(self, topic: str, after: int = 0) -> tuple[RelayObject, ...]:
        if after < 0:
            raise ValueError("cursor cannot be negative")
        return tuple(
            obj for obj in self._objects
            if obj.topic == topic and obj.sequence > after
        )
