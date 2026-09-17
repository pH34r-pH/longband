from __future__ import annotations

from dataclasses import dataclass
import secrets


@dataclass(frozen=True)
class TrajectoryStep:
    phase: str
    prompt: dict[str, object]


class ContingentRevisionTrajectory:
    """Two-stage challenge whose second state is generated after the first action.

    The participant must first choose an action from fresh state. Only after
    that action is submitted does the coordinator sample an unpredictable
    observation. The final answer therefore cannot be prepared before the
    first transition completes.
    """

    def __init__(self) -> None:
        self._left = secrets.randbelow(90) + 10
        self._right = secrets.randbelow(90) + 10
        self._chosen: str | None = None
        self._observation: int | None = None

    def begin(self) -> TrajectoryStep:
        return TrajectoryStep(
            phase="choose",
            prompt={
                "left": self._left,
                "right": self._right,
                "instruction": "Choose 'left' if left >= right, otherwise choose 'right'.",
            },
        )

    def observe(self, action: object) -> TrajectoryStep:
        expected = "left" if self._left >= self._right else "right"
        if action != expected:
            raise ValueError("incorrect initial action")
        self._chosen = expected
        self._observation = secrets.randbelow(41) - 20
        base = self._left if expected == "left" else self._right
        return TrajectoryStep(
            phase="revise",
            prompt={
                "chosen": expected,
                "base": base,
                "new_observation": self._observation,
                "instruction": "Integrate the new observation by returning base + new_observation.",
            },
        )

    def verify(self, answer: object) -> bool:
        if self._chosen is None or self._observation is None:
            raise ValueError("observation has not been generated")
        base = self._left if self._chosen == "left" else self._right
        return answer == base + self._observation
