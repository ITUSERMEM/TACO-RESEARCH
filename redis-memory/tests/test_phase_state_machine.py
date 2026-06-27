"""12 tests for phase state machine + checkpoint tracker."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from phase_state_machine import PhaseStateMachine, TurnPhase, CheckpointTracker


class TestPhaseStateMachine:
    def test_valid_transition(self):
        psm = PhaseStateMachine()
        assert psm.enter(TurnPhase.SETUP) is True
        assert psm.current == TurnPhase.SETUP

    def test_invalid_transition_raises(self):
        psm = PhaseStateMachine(assert_clean=True)
        with pytest.raises(ValueError):
            psm.enter(TurnPhase.EXECUTING_TOOLS)

    def test_invalid_transition_silent(self):
        psm = PhaseStateMachine(assert_clean=False)
        assert psm.enter(TurnPhase.EXECUTING_TOOLS) is False

    def test_enter_transient_restore(self):
        psm = PhaseStateMachine()
        psm.enter(TurnPhase.SETUP)
        psm.enter(TurnPhase.AWAITING_LLM)
        psm.enter_transient(TurnPhase.COMPACTING)
        assert psm.current == TurnPhase.COMPACTING
        assert psm.in_transient is True
        psm.restore_transient()
        assert psm.current == TurnPhase.AWAITING_LLM
        assert psm.in_transient is False

    def test_dangling_transient(self):
        psm = PhaseStateMachine(assert_clean=True)
        psm.enter(TurnPhase.SETUP)
        psm.enter(TurnPhase.AWAITING_LLM)
        psm.enter_transient(TurnPhase.COMPACTING)
        assert psm.in_transient is True

    def test_assert_clean_passes(self):
        psm = PhaseStateMachine(assert_clean=True)
        psm.enter(TurnPhase.SETUP)
        psm.assert_clean()
        assert psm.current == TurnPhase.SETUP

    def test_full_pipeline(self):
        psm = PhaseStateMachine(assert_clean=True)
        assert psm.enter(TurnPhase.SETUP)
        assert psm.enter(TurnPhase.AWAITING_LLM)
        assert psm.enter(TurnPhase.EXECUTING_TOOLS)
        assert psm.enter(TurnPhase.DONE)
        psm.assert_clean()

    def test_reset(self):
        psm = PhaseStateMachine()
        psm.enter(TurnPhase.AWAITING_LLM)
        psm.enter_transient(TurnPhase.COMPACTING)
        psm.reset()
        assert psm.current == TurnPhase.INIT
        assert psm.in_transient is False

    def test_restore_without_transient(self):
        psm = PhaseStateMachine(assert_clean=False)
        psm.restore_transient()

    def test_restore_without_transient_raises(self):
        psm = PhaseStateMachine(assert_clean=True)
        with pytest.raises(ValueError):
            psm.restore_transient()


class TestCheckpointTracker:
    def test_mark_dirty(self):
        ct = CheckpointTracker()
        ct.mark_dirty()
        assert ct.dirty is True

    def test_checkpoint_success_clears(self):
        ct = CheckpointTracker(min_interval_secs=0)
        ct.mark_dirty()
        assert ct.should_checkpoint() is True
        ct.checkpoint_done(success=True)
        assert ct.dirty is False

    def test_checkpoint_failure_retains(self):
        ct = CheckpointTracker(min_interval_secs=0)
        ct.mark_dirty()
        ct.checkpoint_done(success=False)
        assert ct.dirty is True
