"""Tests for log_analyzer.py — Log root cause analysis."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestLogAnalyzer:
    def _make_log_file(self, entries: list[dict]) -> str:
        f = tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w")
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
        f.close()
        return f.name

    def test_no_log_file(self):
        from log_analyzer import LogAnalyzer
        analyzer = LogAnalyzer(audit_log_path="/nonexistent/audit.log")
        result = analyzer.analyze_local()
        assert "error" in result or result["hypotheses"]

    def test_empty_log(self):
        from log_analyzer import LogAnalyzer
        path = self._make_log_file([])
        try:
            analyzer = LogAnalyzer(audit_log_path=path)
            result = analyzer.analyze_local()
            assert "error" in result or result.get("hypotheses") is not None
        finally:
            os.unlink(path)

    def test_detect_rate_limit(self):
        from log_analyzer import LogAnalyzer
        entries = [
            {"timestamp": "2026-06-27T10:00:00+00:00", "event": "error",
             "details": "RateLimitError: 429 Too Many Requests"},
            {"timestamp": "2026-06-27T10:00:01+00:00", "event": "tool_call",
             "tool": "research-lit", "output_summary": "ok"},
        ]
        path = self._make_log_file(entries)
        try:
            analyzer = LogAnalyzer(audit_log_path=path)
            result = analyzer.analyze_local("2026-06-27T10:00:00+00:00")
            hypotheses = result["hypotheses"]
            assert any("429" in h.get("hypothesis", "") or "速率" in h.get("hypothesis", "")
                       for h in hypotheses)
        finally:
            os.unlink(path)

    def test_detect_timeout(self):
        from log_analyzer import LogAnalyzer
        entries = [
            {"timestamp": "2026-06-27T10:00:00+00:00", "event": "error",
             "details": "APITimeoutError: connection timed out"},
        ]
        path = self._make_log_file(entries)
        try:
            analyzer = LogAnalyzer(audit_log_path=path)
            result = analyzer.analyze_local("2026-06-27T10:00:00+00:00")
            hypotheses = result["hypotheses"]
            assert any("超时" in h.get("hypothesis", "") or "timeout" in h.get("hypothesis", "").lower()
                       for h in hypotheses)
        finally:
            os.unlink(path)

    def test_detect_llm_error_passthrough(self):
        from log_analyzer import LogAnalyzer
        entries = [
            {"timestamp": "2026-06-27T10:00:00+00:00", "event": "error",
             "details": "[LLM error: connection refused]"},
        ]
        path = self._make_log_file(entries)
        try:
            analyzer = LogAnalyzer(audit_log_path=path)
            result = analyzer.analyze_local("2026-06-27T10:00:00+00:00")
            hypotheses = result["hypotheses"]
            assert any("LLM" in h.get("hypothesis", "") for h in hypotheses)
        finally:
            os.unlink(path)

    def test_detect_hung_skill(self):
        from log_analyzer import LogAnalyzer
        entries = [
            {"timestamp": "2026-06-27T10:00:00+00:00", "event": "tool_call",
             "tool": "research-lit", "output_summary": "[SKILL HANG] 卡住 30s"},
        ]
        path = self._make_log_file(entries)
        try:
            analyzer = LogAnalyzer(audit_log_path=path)
            result = analyzer.analyze_local("2026-06-27T10:00:00+00:00")
            hypotheses = result["hypotheses"]
            assert any("卡住" in h.get("hypothesis", "") or "hang" in h.get("hypothesis", "").lower()
                       for h in hypotheses)
        finally:
            os.unlink(path)

    def test_detect_rapid_phase_transitions(self):
        from log_analyzer import LogAnalyzer
        entries = [
            {"timestamp": "2026-06-27T10:00:00+00:00", "event": "phase_transition", "phase": 1},
            {"timestamp": "2026-06-27T10:00:01+00:00", "event": "phase_transition", "phase": 2},
            {"timestamp": "2026-06-27T10:00:02+00:00", "event": "phase_transition", "phase": 3},
        ]
        path = self._make_log_file(entries)
        try:
            analyzer = LogAnalyzer(audit_log_path=path)
            result = analyzer.analyze_local("2026-06-27T10:00:01+00:00")
            hypotheses = result["hypotheses"]
            assert any("Phase" in h.get("hypothesis", "") or "快速" in h.get("hypothesis", "")
                       for h in hypotheses)
        finally:
            os.unlink(path)

    def test_unknown_failure_fallback(self):
        from log_analyzer import LogAnalyzer
        entries = [
            {"timestamp": "2026-06-27T10:00:00+00:00", "event": "tool_call",
             "tool": "test", "output_summary": "ok"},
        ]
        path = self._make_log_file(entries)
        try:
            analyzer = LogAnalyzer(audit_log_path=path)
            result = analyzer.analyze_local("2026-06-27T10:00:00+00:00")
            assert len(result["hypotheses"]) >= 1
        finally:
            os.unlink(path)

    def test_system_health(self):
        from log_analyzer import LogAnalyzer
        analyzer = LogAnalyzer(audit_log_path="/nonexistent/audit.log")
        health = analyzer.get_system_health()
        assert health["audit_log_exists"] is False
        assert health["redis_connected"] is False

    def test_system_health_with_real_log(self):
        from log_analyzer import LogAnalyzer
        path = self._make_log_file([
            {"timestamp": "2026-06-27T10:00:00+00:00", "event": "tool_call"},
            {"timestamp": "2026-06-27T10:00:01+00:00", "event": "error"},
        ])
        try:
            analyzer = LogAnalyzer(audit_log_path=path)
            health = analyzer.get_system_health()
            assert health["audit_log_exists"] is True
            assert health["audit_log_size"] > 0
            assert health["total_entries"] == 2
            assert health["recent_errors"] == 1
        finally:
            os.unlink(path)

    def test_extract_window(self):
        from log_analyzer import LogAnalyzer
        entries = [
            {"timestamp": "2026-06-27T09:00:00+00:00", "event": "old"},
            {"timestamp": "2026-06-27T10:00:00+00:00", "event": "target"},
            {"timestamp": "2026-06-27T10:01:00+00:00", "event": "near"},
            {"timestamp": "2026-06-27T12:00:00+00:00", "event": "far"},
        ]
        analyzer = LogAnalyzer()
        window = analyzer._extract_window(entries, "2026-06-27T10:00:00+00:00", 5)
        assert len(window) == 2
        events = [e["event"] for e in window]
        assert "target" in events
        assert "near" in events

    def test_extract_window_invalid_timestamp(self):
        from log_analyzer import LogAnalyzer
        entries = [{"timestamp": "2026-06-27T10:00:00+00:00", "event": "test"}]
        analyzer = LogAnalyzer()
        window = analyzer._extract_window(entries, "invalid", 5)
        assert len(window) >= 1

    def test_detect_rapid_transitions(self):
        from log_analyzer import LogAnalyzer
        entries = [
            {"timestamp": "2026-06-27T10:00:00+00:00"},
            {"timestamp": "2026-06-27T10:00:02+00:00"},
            {"timestamp": "2026-06-27T10:00:10+00:00"},
        ]
        rapid = LogAnalyzer._detect_rapid_transitions(entries, min_interval_sec=5)
        assert len(rapid) == 1

    def test_detect_rapid_transitions_none(self):
        from log_analyzer import LogAnalyzer
        entries = [
            {"timestamp": "2026-06-27T10:00:00+00:00"},
            {"timestamp": "2026-06-27T10:01:00+00:00"},
        ]
        rapid = LogAnalyzer._detect_rapid_transitions(entries, min_interval_sec=5)
        assert len(rapid) == 0

    def test_parse_analysis_valid(self):
        from log_analyzer import LogAnalyzer
        response = '{"hypotheses": [{"rank": 1, "hypothesis": "test"}], "root_cause_category": "timeout"}'
        result = LogAnalyzer._parse_analysis(response)
        assert result["root_cause_category"] == "timeout"

    def test_parse_analysis_invalid(self):
        from log_analyzer import LogAnalyzer
        result = LogAnalyzer._parse_analysis("not json")
        assert "hypotheses" in result

    def test_load_entries_malformed_lines(self):
        from log_analyzer import LogAnalyzer
        f = tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w")
        f.write('{"valid": true}\n')
        f.write('not json\n')
        f.write('{"also_valid": true}\n')
        f.close()
        try:
            analyzer = LogAnalyzer(audit_log_path=f.name)
            entries = analyzer._load_entries()
            assert len(entries) == 2
        finally:
            os.unlink(f.name)
