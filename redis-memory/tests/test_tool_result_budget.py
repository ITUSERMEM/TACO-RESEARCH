"""8 tests for ToolResultBudget spill and aggregate cap."""
import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_result_budget import ToolResultBudget, SPILL_THRESHOLD, AGGREGATE_CAP


class TestToolResultBudget:
    def make_result(self, content, call_id="call-1"):
        return {"call_id": call_id, "content": content}

    def test_small_result_not_spilled(self):
        budget = ToolResultBudget(session_id="test")
        r = self.make_result("small" * 1000)
        result = budget.apply_all([r])
        assert result[0]["content"] == "small" * 1000

    def test_large_result_spilled(self):
        budget = ToolResultBudget(session_id="test")
        large = "x" * (SPILL_THRESHOLD + 1000)
        r = self.make_result(large, "big-call")
        result = budget.apply_all([r])
        assert len(result[0]["content"]) < len(large)
        assert "spilled" in result[0]["content"].lower()

    def test_aggregate_cap(self):
        budget = ToolResultBudget(session_id="test")
        results = [self.make_result("x" * (AGGREGATE_CAP // 2), f"big-{i}") for i in range(3)]
        processed = budget.apply_all(results)
        total = sum(len(r["content"]) for r in processed)
        assert total <= AGGREGATE_CAP * 2

    def test_spill_file_created(self):
        from tool_result_budget import SPILL_DIR
        budget = ToolResultBudget(session_id="spill-test")
        large = "y" * (SPILL_THRESHOLD + 1000)
        r = self.make_result(large, "spill-call")
        budget.apply_all([r])
        import os as _os
        spill_files = _os.listdir(SPILL_DIR)
        assert len(spill_files) > 0

    def test_reuse_replacement(self):
        budget = ToolResultBudget(session_id="reuse")
        budget._replacements["test-call"] = "replaced"
        assert budget.get_replacement("test-call") == "replaced"

    def test_cleanup(self):
        budget = ToolResultBudget(session_id="clean-test")
        budget._replacements["x"] = "y"
        budget.cleanup()
        assert budget.get_replacement("x") is None

    def test_small_result_not_spilled_aggregate(self):
        budget = ToolResultBudget(session_id="test")
        r = self.make_result("small content")
        result = budget.apply_all([r])
        assert result[0]["content"] == "small content"

    def test_empty_results_noop(self):
        budget = ToolResultBudget(session_id="test")
        result = budget.apply_all([])
        assert result == []
