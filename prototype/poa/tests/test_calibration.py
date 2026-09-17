from longband_poa.calibration import run_contingent_revision


class CapableFixture:
    name = "capable-fixture"

    def act(self, step):
        if step.phase == "choose":
            return "left" if step.prompt["left"] >= step.prompt["right"] else "right"
        if step.phase == "revise":
            return step.prompt["base"] + step.prompt["new_observation"]
        raise AssertionError(step.phase)


class NarrowReplayFixture:
    name = "narrow-replay-fixture"

    def act(self, step):
        # Deliberately cannot integrate the fresh post-action observation.
        if step.phase == "choose":
            return "left" if step.prompt["left"] >= step.prompt["right"] else "right"
        return 0


def test_capable_fixture_passes_contingent_trajectory():
    result = run_contingent_revision(CapableFixture())
    assert result.passed
    assert result.transitions == 2


def test_narrow_replay_fixture_fails_after_fresh_observation():
    result = run_contingent_revision(NarrowReplayFixture())
    assert not result.passed
    assert result.transitions == 2
    assert result.failure == "final-verification"
