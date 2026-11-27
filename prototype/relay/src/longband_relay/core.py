from __future__ import annotations

from dataclasses import dataclass
import time

MAX_TOPIC_CHARS = 256
MAX_PAYLOAD_BYTES = 262_144
MAX_REFERENCES = 64


def validate_append(topic: str, payload: bytes, references: tuple[int, ...]) -> None:
    if not topic:
        raise ValueError("topic is required")
    if len(topic) > MAX_TOPIC_CHARS:
        raise ValueError("topic is too long")
    if not payload:
        raise ValueError("opaque payload is required")
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError("opaque payload is too large")
    if len(references) > MAX_REFERENCES:
        raise ValueError("too many references")


@dataclass(frozen=True)
class TopicSummary:
    topic: str
    object_count: int
    latest_sequence: int
    last_activity_ns: int

@dataclass(frozen=True)
class RelayObject:
    sequence: int
    topic: str
    payload: bytes
    references: tuple[int, ...]
    received_ns: int

class OpaqueRelay:
    def __init__(self) -> None:
        self._objects: list[RelayObject] = []

    def append(self, topic: str, payload: bytes, references: tuple[int, ...] = ()) -> RelayObject:
        validate_append(topic, payload, references)
        if any(reference < 1 or reference > len(self._objects) for reference in references):
            raise ValueError("reference must identify an existing relay object")
        obj = RelayObject(len(self._objects) + 1, topic, bytes(payload), tuple(references), time.time_ns())
        self._objects.append(obj)
        return obj

    def read(self, topic: str, after: int = 0) -> tuple[RelayObject, ...]:
        if after < 0:
            raise ValueError("cursor cannot be negative")
        return tuple(obj for obj in self._objects if obj.topic == topic and obj.sequence > after)

    def topics(self) -> tuple[TopicSummary, ...]:
        grouped: dict[str, list[RelayObject]] = {}
        for obj in self._objects:
            grouped.setdefault(obj.topic, []).append(obj)
        return tuple(
            TopicSummary(topic, len(objects), objects[-1].sequence, objects[-1].received_ns)
            for topic, objects in sorted(grouped.items(), key=lambda item: (-item[1][-1].received_ns, item[0]))
        )
