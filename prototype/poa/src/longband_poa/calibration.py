from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Protocol

from .trajectory import ContingentRevisionTrajectory, TrajectoryStep


class Participant(Protocol):
    name: str

    def act(self, step: TrajectoryStep) -> object: ...


@dataclass(frozen=True)
class CalibrationResult:
    participant: str
    passed: bool
    transitions: int
    elapsed_ns: int
    failure: str | None = None


def run_contingent_revision(participant: Participant) -> CalibrationResult:
    started = time.monotonic_ns()
    trajectory = ContingentRevisionTrajectory()
    transitions = 0
    try:
        first = trajectory.begin()
        action = participant.act(first)
        transitions += 1
        second = trajectory.observe(action)
        answer = participant.act(second)
        transitions += 1
        passed = trajectory.verify(answer)
        return CalibrationResult(
            participant=participant.name,
            passed=passed,
            transitions=transitions,
            elapsed_ns=time.monotonic_ns() - started,
            failure=None if passed else "final-verification",
        )
    except Exception as exc:
        return CalibrationResult(
            participant=participant.name,
            passed=False,
            transitions=transitions,
            elapsed_ns=time.monotonic_ns() - started,
            failure=type(exc).__name__,
        )
