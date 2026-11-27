from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import secrets
import time
from typing import Protocol

MAX_ENDPOINT_KEY_CHARS = 128
MAX_SUBMITTED_CHARS = 256
DEFAULT_ATTEMPT_TTL_SECONDS = 900
DEFAULT_MAX_ATTEMPTS = 10_000


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
    created_ns: int = 0

    @property
    def current(self) -> Challenge | None:
        if self.status is not AttemptStatus.ACTIVE or self.index >= len(self.challenges):
            return None
        return self.challenges[self.index]


class ChallengeGenerator(Protocol):
    def generate(self) -> Challenge: ...


class Coordinator:
    """Offline PoA state machine shared by future HTTP and MCP adapters."""

    def __init__(
        self,
        generators: list[ChallengeGenerator],
        attempt_ttl_seconds: int = DEFAULT_ATTEMPT_TTL_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        if not generators:
            raise ValueError("at least one challenge generator is required")
        if attempt_ttl_seconds <= 0 or max_attempts <= 0:
            raise ValueError("attempt lifetime and capacity must be positive")
        self._generators = generators
        self._attempt_ttl_ns = attempt_ttl_seconds * 1_000_000_000
        self._max_attempts = max_attempts
        self._attempts: dict[str, Attempt] = {}

    def _prune(self, now_ns: int) -> None:
        expired = [key for key, attempt in self._attempts.items() if now_ns - attempt.created_ns >= self._attempt_ttl_ns]
        for key in expired:
            del self._attempts[key]

    def begin(self, endpoint_key: str) -> Attempt:
        if not endpoint_key:
            raise ValueError("endpoint key binding is required")
        if len(endpoint_key) > MAX_ENDPOINT_KEY_CHARS:
            raise ValueError("endpoint key is too long")
        now = time.monotonic_ns()
        self._prune(now)
        if len(self._attempts) >= self._max_attempts:
            raise ValueError("PoA capacity reached")
        attempt = Attempt(
            attempt_id=secrets.token_urlsafe(24),
            endpoint_key=endpoint_key,
            challenges=[generator.generate() for generator in self._generators],
            created_ns=now,
        )
        self._attempts[attempt.attempt_id] = attempt
        return attempt

    def step(self, attempt_id: str, submitted: object) -> Attempt:
        attempt = self._attempts[attempt_id]
        challenge = attempt.current
        if challenge is None:
            raise ValueError("attempt is not active")
        if not isinstance(submitted, (str, int, float, bool, type(None))) or len(str(submitted)) > MAX_SUBMITTED_CHARS:
            raise ValueError("submitted value must be a short scalar")

        accepted = secrets.compare_digest(
            str(submitted).encode("utf-8", errors="surrogatepass"),
            str(challenge.expected).encode("utf-8", errors="surrogatepass"),
        )
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
