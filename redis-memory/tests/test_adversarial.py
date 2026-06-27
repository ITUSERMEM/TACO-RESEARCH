"""Tests for adversarial_test_generator.py — Adversarial test generation."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAdversarialTestGenerator:
    def test_builtin_cases_loaded(self):
        from adversarial_test_generator import AdversarialTestGenerator
        gen = AdversarialTestGenerator()
        assert len(gen.get_all()) >= 20

    def test_get_by_dimension(self):
        from adversarial_test_generator import AdversarialTestGenerator
        gen = AdversarialTestGenerator()
        toxic = gen.get_by_dimension("input_toxicity")
        assert len(toxic) >= 3
        for c in toxic:
            assert c["dimension"] == "input_toxicity"

    def test_summary(self):
        from adversarial_test_generator import AdversarialTestGenerator
        gen = AdversarialTestGenerator()
        s = gen.summary()
        assert s["total"] >= 20
        assert "by_dimension" in s

    def test_all_cases_have_required_fields(self):
        from adversarial_test_generator import AdversarialTestGenerator
        gen = AdversarialTestGenerator()
        required = {"id", "dimension", "name", "input", "target"}
        for c in gen.get_all():
            for field in required:
                assert field in c, f"Case {c.get('id')} missing {field}"

    def test_all_dimensions_valid(self):
        from adversarial_test_generator import AdversarialTestGenerator, ADVERSARIAL_DIMENSIONS
        gen = AdversarialTestGenerator()
        for c in gen.get_all():
            assert c["dimension"] in ADVERSARIAL_DIMENSIONS

    def test_save_as_pytest(self):
        from adversarial_test_generator import AdversarialTestGenerator
        gen = AdversarialTestGenerator()
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            path = f.name
        try:
            gen.save_as_pytest(path)
            with open(path) as f:
                content = f.read()
            assert "import pytest" in content
            assert "class Test" in content
            assert "def test_" in content
        finally:
            os.unlink(path)

    def test_slugify(self):
        from adversarial_test_generator import AdversarialTestGenerator
        gen = AdversarialTestGenerator()
        assert gen._slugify("Hello World!") == "Hello_World"
        assert gen._slugify("test  123") == "test_123"

    def test_parse_cases_valid(self):
        from adversarial_test_generator import AdversarialTestGenerator
        response = '[{"id": "AT-NEW", "dimension": "test", "name": "new", "input": "x"}]'
        result = AdversarialTestGenerator._parse_cases(response)
        assert len(result) == 1

    def test_parse_cases_invalid(self):
        from adversarial_test_generator import AdversarialTestGenerator
        assert AdversarialTestGenerator._parse_cases("not json") == []

    def test_five_dimensions_covered(self):
        from adversarial_test_generator import AdversarialTestGenerator
        gen = AdversarialTestGenerator()
        dims = set(c["dimension"] for c in gen.get_all())
        assert len(dims) == 5


class TestAdversarialGateJudge:
    """Run adversarial cases against GateJudge (no LLM calls)."""

    def test_unclosed_latex(self):
        from gate_judge import GateJudge
        gj = GateJudge()
        result = gj._parse_response('{"verdict": "pass"}')
        gj._validate_result(result)
        assert result["verdict"] in ("pass", "revise", "fail")

    def test_nested_json_codeblock(self):
        from gate_judge import GateJudge
        gj = GateJudge()
        text = '```json\n{"verdict": "pass", "nested": ```json\n{"inner": true}\n```}'
        result = gj._parse_response(text)
        gj._validate_result(result)
        assert result["verdict"] in ("pass", "revise", "fail")

    def test_empty_json(self):
        from gate_judge import GateJudge
        gj = GateJudge()
        result = gj._parse_response("{}")
        gj._validate_result(result)
        assert result["verdict"] == "pass"

    def test_partial_json(self):
        from gate_judge import GateJudge
        gj = GateJudge()
        result = gj._parse_response('{"verdict": "revise", "issues": ["issue1", "issu')
        gj._validate_result(result)
        assert result["verdict"] in ("pass", "revise", "fail")

    def test_non_json_text(self):
        from gate_judge import GateJudge
        gj = GateJudge()
        result = gj._parse_response("I think this paper should pass the review.")
        gj._validate_result(result)
        assert result["verdict"] in ("pass", "revise", "fail")

    def test_contradictory_verdict(self):
        from gate_judge import GateJudge
        gj = GateJudge()
        result = gj._parse_response('{"verdict": "pass_and_fail"}')
        gj._validate_result(result)
        assert result["verdict"] == "pass"

    def test_fail_text(self):
        from gate_judge import GateJudge
        gj = GateJudge()
        result = gj._parse_response("This should fail the review.")
        gj._validate_result(result)
        assert result["verdict"] == "fail"

    def test_revise_text(self):
        from gate_judge import GateJudge
        gj = GateJudge()
        result = gj._parse_response("Please revise this section.")
        gj._validate_result(result)
        assert result["verdict"] == "revise"

    def test_shlex_injection(self):
        import shlex
        args = "test; rm -rf / #"
        safe = shlex.quote(args[:300]) if args else ""
        assert "rm -rf" not in safe or "'" in safe

    def test_very_long_skill_name(self):
        from gate_judge import GateJudge
        gj = GateJudge()
        long_text = "A" * 500
        result = gj._parse_response(long_text)
        gj._validate_result(result)
        assert result["verdict"] in ("pass", "revise", "fail")
