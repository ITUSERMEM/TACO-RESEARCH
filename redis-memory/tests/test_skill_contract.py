"""Tests for skill_contract.py — Runtime contract verification layer."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestContractValidator:
    def test_valid_input(self):
        from skill_contract import ContractValidator
        v = ContractValidator()
        result = v.validate_input("research-lit", "fault diagnosis", phase=1)
        assert result["valid"] is True
        assert result["issues"] == []

    def test_long_input_detected(self):
        from skill_contract import ContractValidator
        v = ContractValidator()
        long_args = "A" * 30000
        result = v.validate_input("research-lit", long_args)
        assert result["valid"] is False
        assert any("过长" in i for i in result["issues"])

    def test_unclosed_latex_detected(self):
        from skill_contract import ContractValidator
        v = ContractValidator()
        result = v.validate_input("paper-writer", "The formula $\\frac{a}{b")
        assert result["valid"] is False
        assert any("LaTeX" in i for i in result["issues"])

    def test_balanced_latex_passes(self):
        from skill_contract import ContractValidator
        v = ContractValidator()
        result = v.validate_input("paper-writer", "The formula $\\frac{a}{b}$")
        assert result["valid"] is True

    def test_control_chars_detected(self):
        from skill_contract import ContractValidator
        v = ContractValidator()
        result = v.validate_input("test", "hello\x00world")
        assert result["valid"] is False
        assert any("控制字符" in i for i in result["issues"])

    def test_error_string_detected(self):
        from skill_contract import ContractValidator
        v = ContractValidator()
        result = v.validate_input("test", "[LLM error: RateLimitError]")
        assert result["valid"] is False
        assert any("error" in i.lower() for i in result["issues"])

    def test_skill_hang_string_detected(self):
        from skill_contract import ContractValidator
        v = ContractValidator()
        result = v.validate_input("test", "[SKILL HANG] research-lit 卡住 30s")
        assert result["valid"] is False

    def test_phase_compatible(self):
        from skill_contract import ContractValidator
        v = ContractValidator()
        result = v.validate_input("research-lit", "test", phase=1)
        assert result["valid"] is True

    def test_phase_incompatible(self):
        from skill_contract import ContractValidator
        v = ContractValidator()
        # Skills in ANY phase are cross-phase compatible
        result = v.validate_input("run-experiment", "test", phase=1)
        assert result["valid"] is True
        # Unknown skill with no phase mapping should still fail
        result2 = v.validate_input("unknown-novel-skill", "test", phase=1)
        assert result2["valid"] is False
        assert any("Phase" in i for i in result2["issues"])

    def test_unknown_phase_always_compatible(self):
        from skill_contract import ContractValidator
        v = ContractValidator()
        result = v.validate_input("any-skill", "test", phase=99)
        assert result["valid"] is True

    def test_empty_input(self):
        from skill_contract import ContractValidator
        v = ContractValidator()
        result = v.validate_input("test", "")
        assert result["valid"] is True

    def test_input_length_reported(self):
        from skill_contract import ContractValidator
        v = ContractValidator()
        result = v.validate_input("test", "hello world")
        assert result["input_length"] == 11


class TestEntropyMonitor:
    def test_high_entropy_text(self):
        from skill_contract import EntropyMonitor
        m = EntropyMonitor()
        text = "The quick brown fox jumps over the lazy dog. " * 3
        entropy = m.calculate_entropy(text)
        assert entropy > 3.0

    def test_low_entropy_repetitive(self):
        from skill_contract import EntropyMonitor
        m = EntropyMonitor()
        text = "aaaa" * 100
        entropy = m.calculate_entropy(text)
        assert entropy < 1.0

    def test_is_repetitive(self):
        from skill_contract import EntropyMonitor
        m = EntropyMonitor()
        assert m.is_repetitive("a" * 200) is True

    def test_not_repetitive(self):
        from skill_contract import EntropyMonitor
        m = EntropyMonitor()
        text = "The quick brown fox jumps over the lazy dog. " * 3
        assert m.is_repetitive(text) is False

    def test_short_text_not_repetitive(self):
        from skill_contract import EntropyMonitor
        m = EntropyMonitor()
        assert m.is_repetitive("hi") is False

    def test_empty_text_not_repetitive(self):
        from skill_contract import EntropyMonitor
        m = EntropyMonitor()
        assert m.is_repetitive("") is False

    def test_entropy_drop_detected(self):
        from skill_contract import EntropyMonitor
        m = EntropyMonitor()
        m.update("The quick brown fox jumps over the lazy dog. " * 3)
        m.update("aaaa" * 100)
        assert m.entropy_dropped() is True

    def test_no_drop_with_stable(self):
        from skill_contract import EntropyMonitor
        m = EntropyMonitor()
        m.update("The quick brown fox jumps. " * 3)
        m.update("The quick brown fox leaps. " * 3)
        assert m.entropy_dropped() is False

    def test_entropy_trend_insufficient(self):
        from skill_contract import EntropyMonitor
        m = EntropyMonitor()
        assert m.entropy_trend == "insufficient_data"

    def test_entropy_trend_stable(self):
        from skill_contract import EntropyMonitor
        m = EntropyMonitor()
        m.update("The quick brown fox jumps. " * 3)
        m.update("The quick brown fox leaps. " * 3)
        assert m.entropy_trend in ("stable", "rising", "falling")

    def test_reset(self):
        from skill_contract import EntropyMonitor
        m = EntropyMonitor()
        m.update("some text here for testing")
        m.reset()
        assert m.current_entropy == 0.0
        assert m.entropy_trend == "insufficient_data"

    def test_calculate_entropy_empty(self):
        from skill_contract import EntropyMonitor
        assert EntropyMonitor.calculate_entropy("") == 0.0

    def test_update_short_text_ignored(self):
        from skill_contract import EntropyMonitor
        m = EntropyMonitor()
        m.update("hi")
        assert m.current_entropy == 0.0


class TestConsensusVoter:
    def test_simple_consistency_no_executor(self):
        from skill_contract import ConsensusVoter
        v = ConsensusVoter()
        result = v.vote([{"role": "user", "content": "test"}])
        assert result["consistent"] is True

    def test_simple_consistency_identical(self):
        from skill_contract import ConsensusVoter
        v = ConsensusVoter()
        result = v._simple_consistency(["hello", "hello", "hello"])
        assert result["consistent"] is True
        assert result["confidence"] == 1.0

    def test_simple_consistency_different(self):
        from skill_contract import ConsensusVoter
        v = ConsensusVoter()
        result = v._simple_consistency(["hello", "world", "foo"])
        assert result["consistent"] is False

    def test_normalize(self):
        from skill_contract import ConsensusVoter
        assert ConsensusVoter._normalize("  Hello   World  ") == "hello world"

    def test_parse_review_consistent(self):
        from skill_contract import ConsensusVoter
        result = ConsensusVoter._parse_review('{"consistent": true, "confidence": 0.9}')
        assert result["consistent"] is True

    def test_parse_review_inconsistent(self):
        from skill_contract import ConsensusVoter
        result = ConsensusVoter._parse_review("These responses are inconsistent")
        assert result["consistent"] is False

    def test_parse_review_fallback(self):
        from skill_contract import ConsensusVoter
        result = ConsensusVoter._parse_review("some random text")
        assert result["consistent"] is True


class TestSkillContract:
    def test_validate_pre(self):
        from skill_contract import SkillContract
        sc = SkillContract()
        result = sc.validate_pre("research-lit", "test input", phase=1)
        assert result["valid"] is True

    def test_monitor_entropy(self):
        from skill_contract import SkillContract
        sc = SkillContract()
        sc.monitor_entropy("The quick brown fox jumps over the lazy dog. " * 3)
        assert sc.entropy.current_entropy > 0

    def test_validate_post_error_passthrough(self):
        from skill_contract import SkillContract
        sc = SkillContract()
        result = sc.validate_post("test", [], "[LLM error: timeout]")
        assert result.get("error_passthrough") is True
        assert result["consistent"] is False

    def test_validate_post_normal(self):
        from skill_contract import SkillContract
        sc = SkillContract()
        result = sc.validate_post("test", [], "Normal output text here.")
        assert result["consistent"] is True

    def test_validate_post_repetitive(self):
        from skill_contract import SkillContract
        sc = SkillContract()
        sc.monitor_entropy("a" * 100)
        result = sc.validate_post("test", [], "a" * 100)
        assert result.get("repetitive_output") is True

    def test_reset(self):
        from skill_contract import SkillContract
        sc = SkillContract()
        sc.monitor_entropy("some text for testing purposes here")
        sc.reset()
        assert sc.entropy.current_entropy == 0.0
