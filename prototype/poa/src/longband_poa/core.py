from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import secrets
import time
from typing import Protocol


class AttemptStatus(str, Enum):
    ACTIVE = "active"
    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True)
class Challenge:
    family: str
    prompt: dict[str, object]
    expected: object


@dataclass(frozen=True)
class Transition:
    family: str
    submitted: object
    accepted: bool
    monotonic_ns: int


@dataclass
class Attempt:
    attempt_id: str
    endpoint_key: str
    challenges: list[Challenge]
    index: int = 0
    transitions: list[Transition] = field(default_factory=list)
    status: AttemptStatus = AttemptStatus.ACTIVE

    @property
    def current(self) -> Challenge | None:
        if self.status is not AttemptStatus.ACTIVE or self.index >= len(self.challenges):
            return None
        return self.challenges[self.index]


class ChallengeGenerator(Protocol):
    def generate(self) -> Challenge: ...


class Coordinator:
    """Offline PoA state machine shared by future HTTP and MCP adapters."""

    def __init__(self, generators: list[ChallengeGenerator]) -> None:
        if not generators:
            raise ValueError("at least one challenge generator is required")
        self._generators = generators
        self._attempts: dict[str, Attempt] = {}

    def begin(self, endpoint_key: str) -> Attempt:
        if not endpoint_key:
            raise ValueError("endpoint key binding is required")
        attempt = Attempt(
            attempt_id=secrets.token_urlsafe(24),
            endpoint_key=endpoint_key,
            challenges=[generator.generate() for generator in self._generators],
        )
        self._attempts[attempt.attempt_id] = attempt
        return attempt

    def step(self, attempt_id: str, submitted: object) -> Attempt:
        attempt = self._attempts[attempt_id]
        challenge = attempt.current
        if challenge is None:
            raise ValueError("attempt is not active")

        accepted = secrets.compare_digest(str(submitted), str(challenge.expected))
        attempt.transitions.append(
            Transition(
                family=challenge.family,
                submitted=submitted,
                accepted=accepted,
                monotonic_ns=time.monotonic_ns(),
            )
        )
        if not accepted:
            attempt.status = AttemptStatus.FAILED
            return attempt

        attempt.index += 1
        if attempt.index == len(attempt.challenges):
            attempt.status = AttemptStatus.PASSED
        return attempt

    def status(self, attempt_id: str) -> Attempt:
        return self._attempts[attempt_id]
