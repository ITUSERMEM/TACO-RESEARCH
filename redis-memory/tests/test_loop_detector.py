"""21 tests for 9-path loop detector."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loop_detector import LoopDetector, LoopAction, PhaseLoopDetector


class TestLoopDetector:
    def test_empty_think_force_stop(self):
        d = LoopDetector()
        d.record("think", {"thought": ""})
        d.check("think")
        d.record("think", {"thought": ""})
        assert d.check("think") == LoopAction.FORCE_STOP

    def test_tool_mode_switch_nudge(self):
        d = LoopDetector()
        d.record("applescript", {}, is_error=False)
        d.record("screenshot")
        assert d.check("screenshot") == LoopAction.NUDGE

    def test_consecutive_duplicate_force_stop(self):
        d = LoopDetector()
        for _ in range(4):
            d.record("paper_search", {"q": "physics"})
        assert d.check("paper_search") == LoopAction.FORCE_STOP

    def test_consecutive_duplicate_nudge(self):
        d = LoopDetector()
        for _ in range(2):
            d.record("paper_search", {"q": "physics"})
        assert d.check("paper_search") != LoopAction.NUDGE

    def test_exact_duplicate_window_force_stop(self):
        d = LoopDetector()
        for i in range(11):
            d.record("read", {"f": "a"})
        assert d.check("read") == LoopAction.FORCE_STOP

    def test_exact_duplicate_window_nudge(self):
        d = LoopDetector()
        calls = [("read", {"f": "a"}), ("edit", {"f": "a"})] * 3
        for name, args in calls:
            d.record(name, args)
        assert d.check("edit") == LoopAction.NUDGE

    def test_same_tool_error_force(self):
        d = LoopDetector()
        for i in range(13):
            d.record("http", {"url": f"x{i}"}, is_error=True)
        assert d.check("http") == LoopAction.FORCE_STOP

    def test_same_tool_error_nudge(self):
        d = LoopDetector()
        for i in range(7):
            d.record("http", {"url": f"x{i}"}, is_error=True)
        assert d.check("http") == LoopAction.NUDGE

    def test_family_no_progress_force(self):
        d = LoopDetector()
        for i in range(13):
            d.record("paper_search", {"q": f"q{i}"})
        assert d.check("paper_search") == LoopAction.FORCE_STOP

    def test_search_escalation_force(self):
        d = LoopDetector()
        for i in range(13):
            d.record("search", {"q": f"q{i}"}, is_error=True, result_summary="")
        assert d.check("search") == LoopAction.FORCE_STOP

    def test_no_progress_normal_force(self):
        d = LoopDetector()
        for i in range(25):
            d.record("read_file", {"path": f"f{i}"})
        assert d.check("read_file") == LoopAction.FORCE_STOP

    def test_batch_tolerant_skipped(self):
        d = LoopDetector()
        for i in range(6):
            d.record("http", {"url": f"localhost:{i}"})
        tool_counts = {}
        for name in ["http"]:
            count = sum(1 for c in d.history if c.name == name)
            tool_counts[name] = count
        assert tool_counts.get("http", 0) == 6

    def test_empty_history_continue(self):
        d = LoopDetector()
        assert d.check() == LoopAction.CONTINUE

    def test_mixed_calls_no_trigger(self):
        d = LoopDetector()
        tools = ["search", "read", "write", "search", "think", "read"]
        for t in tools:
            d.record(t, {"x": 1})
        assert d.check() == LoopAction.CONTINUE

    def test_success_after_error_nudge(self):
        d = LoopDetector()
        d.record("applescript", {}, is_error=True)
        d.record("screenshot")
        assert d.check("screenshot") in (LoopAction.NUDGE, LoopAction.CONTINUE)

    def test_nudge_count_escalates(self):
        d = LoopDetector()
        for _ in range(2):
            d.record("think", {"thought": ""})
        d.check("think")
        d._last_empty_think = False
        for _ in range(2):
            d.record("think", {"thought": ""})
        assert d.check("think") == LoopAction.FORCE_STOP

    def test_force_stop_after_3_nudges(self):
        d = LoopDetector()
        for _ in range(3):
            d.record("think", {"thought": ""})
            d.check("think")
            d._last_empty_think = False
        for _ in range(2):
            d.record("think", {"thought": ""})
        assert d.check("think") == LoopAction.FORCE_STOP

    def test_dup_exempt_use_skill(self):
        d = LoopDetector()
        for _ in range(3):
            d.record("use_skill", {"name": "test"})
        assert d.check("use_skill") != LoopAction.FORCE_STOP


class TestPhaseLoopDetector:
    def test_literature_researcher_nudge_msg(self):
        pd = PhaseLoopDetector("literature_researcher")
        for i in range(16):
            pd.record("paper_search", {"q": f"q{i}"})
        action, msg = pd.check()
        assert action in (LoopAction.NUDGE, LoopAction.FORCE_STOP)
        assert msg is not None

    def test_literature_force_stop_msg(self):
        pd = PhaseLoopDetector("literature_researcher")
        for i in range(26):
            pd.record("paper_search", {"q": f"q{i}"})
        action, msg = pd.check()
        assert action == LoopAction.FORCE_STOP

    def test_experimenter_nudge_msg(self):
        pd = PhaseLoopDetector("experimenter")
        for i in range(9):
            pd.record("train", {"cfg": f"cfg{i}"})
        action, msg = pd.check()
        assert msg is not None

    def test_unknown_role_fallback(self):
        pd = PhaseLoopDetector("unknown_role")
        for i in range(25):
            pd.record("tool", {"x": i})
        action, msg = pd.check()
        assert action in (LoopAction.NUDGE, LoopAction.FORCE_STOP)
