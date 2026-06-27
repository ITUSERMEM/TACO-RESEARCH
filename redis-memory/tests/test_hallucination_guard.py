"""12 tests for 3-layer hallucination guard."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from hallucination_guard import HallucinationGuard


class TestHallucinationGuard:
    def test_fabricated_tool_xml(self):
        g = HallucinationGuard()
        nudge = g.check('I called the search tool and got <tool_exec id="1">result</tool_exec>')
        assert nudge is not None

    def test_fabricated_function_call(self):
        g = HallucinationGuard()
        nudge = g.check("I called the read_file function and received the file contents")
        assert nudge is not None

    def test_unverified_claim(self):
        g = HallucinationGuard()
        nudge = g.check("I searched the literature and found 15 relevant papers")
        assert nudge is not None

    def test_success_after_denial(self):
        g = HallucinationGuard()
        nudge = g.check("I successfully completed the file_write operation", denied_tools=["file_write"])
        assert nudge is not None

    def test_clean_text_no_trigger(self):
        g = HallucinationGuard()
        nudge = g.check("Based on my analysis, the transformer architecture uses self-attention")
        assert nudge is None

    def test_empty_text_no_trigger(self):
        g = HallucinationGuard()
        nudge = g.check("")
        assert nudge is None

    def test_max_nudge_limit(self):
        g = HallucinationGuard()
        g.nudge_count = 2
        nudge = g.check("I searched the literature and found results", turn=5)
        assert nudge is None

    def test_needs_force_stop_true(self):
        g = HallucinationGuard()
        g.nudge_count = 2
        assert g.needs_force_stop(turn=3) is True

    def test_needs_force_stop_false(self):
        g = HallucinationGuard()
        assert g.needs_force_stop(turn=1) is False

    def test_new_turn_resets(self):
        g = HallucinationGuard()
        g.check("I searched the literature and found results")
        g.new_turn()
        assert g.nudges_this_turn == 0

    def test_multiple_detections_first_wins(self):
        g = HallucinationGuard()
        nudge = g.check("I called the search tool and I searched the literature")
        assert nudge is not None

    def test_layer3_specific_tool_check(self):
        g = HallucinationGuard()
        nudge = g._detect_success_after_denial(
            "I successfully completed the denied_operation",
            ["denied_operation"])
        assert nudge is True
