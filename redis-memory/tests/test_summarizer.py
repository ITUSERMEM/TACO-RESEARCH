"""8 tests for two-phase summarizer."""
import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from summarizer import PhaseSummarizer


class TestSummarizer:
    def test_summarize_returns_dict(self):
        s = PhaseSummarizer()
        result = s.summarize([{"role": "user", "content": "test"}], phase=1)
        assert isinstance(result, dict)
        assert "analysis" in result
        assert "summary" in result

    def test_analysis_contains_phase(self):
        s = PhaseSummarizer()
        result = s.summarize([{"role": "user", "content": "test"}], phase=2)
        assert "analysis" in result
        assert "<analysis" in result["analysis"]

    def test_summary_contains_sections(self):
        s = PhaseSummarizer()
        result = s.summarize([{"role": "user", "content": "test"}], phase=1)
        assert "<summary" in result["summary"]

    def test_cap_transcript_limits(self):
        s = PhaseSummarizer(max_input_chars=100)
        long_msgs = [{"role": "user", "content": "x" * 200}] * 10
        transcript = s._cap_transcript(long_msgs)
        assert len(transcript) <= 200

    def test_template_phases_exist(self):
        from summarizer import PHASE_SUMMARY_TEMPLATES
        for phase in range(6):
            assert phase in PHASE_SUMMARY_TEMPLATES

    def test_analysis_captures_decisions(self):
        s = PhaseSummarizer()
        msgs = [{"role": "assistant", "content": "Decision: Use method A"},
                {"role": "user", "content": "Correction: Actually use B"}]
        result = s.summarize(msgs, phase=1)
        analysis = result.get("analysis", "") or ""
        assert len(analysis) > 0

    def test_empty_messages_handled(self):
        s = PhaseSummarizer()
        result = s.summarize([], phase=0)
        assert isinstance(result, dict)

    def test_get_template_text(self):
        s = PhaseSummarizer()
        text = s._get_template_text(1)
        assert "Literature" in text
