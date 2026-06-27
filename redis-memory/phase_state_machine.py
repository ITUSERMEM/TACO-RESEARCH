"""PhaseStateMachine — Kocoro-inspired 10-phase turn state machine.

Tracks agent loop execution through discrete phases:
PhaseInit → PhaseSetup → PhaseAwaitingLLM → PhaseRetryingLLM →
PhaseCompacting → PhaseAwaitingApproval → PhaseExecutingTools →
PhaseInjectingMessage → PhaseForceStop → PhaseDone

AssertClean mode: panics if EnterTransient() forgets to restore.
"""

from enum import Enum
from typing import Optional


class TurnPhase(Enum):
    INIT = "init"
    SETUP = "setup"
    AWAITING_LLM = "awaiting_llm"
    RETRYING_LLM = "retrying_llm"
    COMPACTING = "compacting"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING_TOOLS = "executing_tools"
    INJECTING_MESSAGE = "injecting_message"
    FORCE_STOP = "force_stop"
    DONE = "done"


class PhaseStateMachine:
    """Turn-level phase state machine with AssertClean pattern.

    Usage:
        psm = PhaseStateMachine(assert_clean=True)
        psm.enter(TurnPhase.AWAITING_LLM)
        # ... do work ...
        psm.enter(TurnPhase.EXECUTING_TOOLS)
        psm.assert_clean()  # raises if any transient not restored
    """

    VALID_TRANSITIONS = {
        TurnPhase.INIT: [TurnPhase.SETUP],
        TurnPhase.SETUP: [TurnPhase.AWAITING_LLM, TurnPhase.DONE],
        TurnPhase.AWAITING_LLM: [TurnPhase.EXECUTING_TOOLS, TurnPhase.RETRYING_LLM,
                                  TurnPhase.COMPACTING, TurnPhase.FORCE_STOP],
        TurnPhase.RETRYING_LLM: [TurnPhase.AWAITING_LLM, TurnPhase.FORCE_STOP],
        TurnPhase.COMPACTING: [TurnPhase.AWAITING_LLM, TurnPhase.SETUP],
        TurnPhase.AWAITING_APPROVAL: [TurnPhase.EXECUTING_TOOLS, TurnPhase.FORCE_STOP],
        TurnPhase.EXECUTING_TOOLS: [TurnPhase.AWAITING_LLM, TurnPhase.INJECTING_MESSAGE,
                                     TurnPhase.DONE, TurnPhase.FORCE_STOP],
        TurnPhase.INJECTING_MESSAGE: [TurnPhase.AWAITING_LLM, TurnPhase.DONE],
        TurnPhase.FORCE_STOP: [TurnPhase.DONE],
        TurnPhase.DONE: [],
    }

    def __init__(self, assert_clean: bool = False):
        self.current: TurnPhase = TurnPhase.INIT
        self._assert_clean_enabled = assert_clean
        self._transient_stack: list[tuple[TurnPhase, TurnPhase]] = []
        self._clean = True

    def enter(self, phase: TurnPhase) -> bool:
        """Transition to a new phase. Returns True if valid."""
        allowed = self.VALID_TRANSITIONS.get(self.current, [])
        if phase not in allowed:
            if self._assert_clean_enabled:
                raise ValueError(
                    f"Invalid phase transition: {self.current.value} → {phase.value}"
                )
            return False
        self.current = phase
        return True

    def enter_transient(self, phase: TurnPhase) -> "PhaseStateMachine":
        """Enter a nested transient phase.

        Like Kocoro's EnterTransient pattern:
        - Saves current phase on stack
        - Transitions to sub-phase
        - Returns self for use as context manager (call restore_transient())
        """
        self._transient_stack.append((phase, self.current))
        self.current = phase
        return self

    def restore_transient(self):
        """Restore from transient phase. Raises if not in transient."""
        if not self._transient_stack:
            if self._assert_clean_enabled:
                raise ValueError("restore_transient called without enter_transient")
            return
        _, prev = self._transient_stack.pop()
        self.current = prev

    @property
    def in_transient(self) -> bool:
        return len(self._transient_stack) > 0

    def assert_clean(self):
        """Assert no transient phases are dangling. Follows AssertClean."""
        if self.in_transient and self._assert_clean_enabled:
            phases = [p.value for p, _ in self._transient_stack]
            raise AssertionError(
                f"Dangling transient phases: {phases}. "
                "A restore_transient() call was missed."
            )

    def reset(self):
        self.current = TurnPhase.INIT
        self._transient_stack.clear()
        self._clean = True


class CheckpointTracker:
    """Dirty flag checkpoint tracker with debounce.

    Like Kocoro's maybeCheckpoint: only persists when dirty,
    with min interval to avoid over-persisting during tool-heavy turns.
    """

    def __init__(self, min_interval_secs: float = 5.0):
        self.dirty = False
        self.min_interval = min_interval_secs
        self.last_checkpoint: float = 0.0

    def mark_dirty(self):
        self.dirty = True

    def should_checkpoint(self) -> bool:
        import time
        if not self.dirty:
            return False
        if time.time() - self.last_checkpoint < self.min_interval:
            return False
        return True

    def checkpoint_done(self, success: bool):
        import time
        if success:
            self.dirty = False
            self.last_checkpoint = time.time()
        # If failed, keep dirty flag set for retry
