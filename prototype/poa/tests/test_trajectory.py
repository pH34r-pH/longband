import pytest

from longband_poa.trajectory import ContingentRevisionTrajectory


def test_second_state_is_generated_only_after_correct_action():
    trajectory = ContingentRevisionTrajectory()
    first = trajectory.begin()
    expected = "left" if first.prompt["left"] >= first.prompt["right"] else "right"

    second = trajectory.observe(expected)

    assert second.phase == "revise"
    assert "new_observation" in second.prompt
    answer = second.prompt["base"] + second.prompt["new_observation"]
    assert trajectory.verify(answer)


def test_wrong_first_action_terminates_trajectory():
    trajectory = ContingentRevisionTrajectory()
    first = trajectory.begin()
    expected = "left" if first.prompt["left"] >= first.prompt["right"] else "right"
    wrong = "right" if expected == "left" else "left"

    with pytest.raises(ValueError, match="incorrect initial action"):
        trajectory.observe(wrong)


def test_cannot_verify_before_unpredictable_observation_exists():
    trajectory = ContingentRevisionTrajectory()
    trajectory.begin()

    with pytest.raises(ValueError, match="observation has not been generated"):
        trajectory.verify(0)
