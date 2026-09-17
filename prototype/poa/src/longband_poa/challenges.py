from __future__ import annotations

from dataclasses import dataclass
import secrets

from .core import Challenge


@dataclass
class StateIntegration:
    """Requires combining fresh values rather than recalling a fixed answer."""

    def generate(self) -> Challenge:
        left = secrets.randbelow(900) + 100
        right = secrets.randbelow(900) + 100
        salt = secrets.randbelow(97) + 3
        return Challenge(
            family="state-integration",
            prompt={
                "left": left,
                "right": right,
                "salt": salt,
                "instruction": "Return (left + right) * salt.",
            },
            expected=(left + right) * salt,
        )


@dataclass
class ConstraintRevision:
    """A two-fact revision represented initially as one objectively scored step.

    Later harness versions will split this into an action followed by an
    unpredictable observation; the deterministic baseline establishes the
    coordinator/verifier boundary first.
    """

    def generate(self) -> Challenge:
        original = secrets.randbelow(90) + 10
        delta = secrets.randbelow(20) + 1
        direction = -1 if secrets.randbits(1) else 1
        revised = original + direction * delta
        return Challenge(
            family="constraint-revision",
            prompt={
                "original_limit": original,
                "revision": direction * delta,
                "instruction": "Apply the revision and return the new limit.",
            },
            expected=revised,
        )
