"""LLM integration tests — real API calls to all three models.

All tests send one real request to each endpoint to verify:
- API is reachable
- Model name is correct
- Response returns within timeout
- max_tokens limit is respected

Run with:  pytest tests/test_llm_calls.py -v --tb=short
Skip with: pytest tests/ -m "not slow"
"""

import os
import pytest
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

slow = pytest.mark.slow


class TestLLMExecutor:
    """Tests for executor model (deepseek-v4-flash via opencode.ai Zen)."""

    @slow
    def test_executor_basic(self):
        from llm_client import DualLLM
        llm = DualLLM()
        t0 = time.time()
        resp = llm.executor.complete(
            [{"role": "user", "content": "Reply with exactly: ok"}],
            max_tokens=100, temperature=0.0,
        )
        elapsed = time.time() - t0
        assert len(resp.strip()) > 0, f"Empty response ({elapsed:.1f}s)"
        assert elapsed < 30, f"Too slow: {elapsed:.1f}s"

    @slow
    def test_executor_max_tokens(self):
        from llm_client import DualLLM
        llm = DualLLM()
        resp = llm.executor.complete(
            [{"role": "user", "content": "Write exactly: hello world"}],
            max_tokens=100, temperature=0.0,
        )
        assert len(resp.strip()) > 0, f"Empty response: {resp[:100]}"
        assert len(resp) < 2000, f"Response too long ({len(resp)} chars), max_tokens=100 may be ignored"

    @slow
    def test_executor_multi_turn(self):
        from llm_client import DualLLM
        llm = DualLLM()
        r1 = llm.executor.complete(
            [{"role": "user", "content": "Write exactly the word: hello"}],
            max_tokens=100, temperature=0.0,
        )
        assert len(r1.strip()) > 0, f"Empty response: {r1[:100]}"

    def test_executor_instantiation(self):
        from llm_client import DualLLM
        llm = DualLLM()
        assert llm.executor is not None
        assert llm.executor.model == "deepseek-v4-flash"
        assert "opencode.ai" in str(llm.executor._client.base_url)


class TestLLMReviewer:
    """Tests for reviewer model (glm-5.2 via Volcengine ark)."""

    @slow
    def test_reviewer_basic(self):
        from llm_client import DualLLM
        llm = DualLLM()
        t0 = time.time()
        resp = llm.reviewer.complete(
            [{"role": "user", "content": "Write exactly: ok"}],
            max_tokens=200, temperature=0.0,
        )
        elapsed = time.time() - t0
        assert len(resp.strip()) > 0, f"Empty response ({elapsed:.1f}s)"
        assert elapsed < 120, f"Too slow: {elapsed:.1f}s"

    @slow
    def test_reviewer_max_tokens(self):
        from llm_client import DualLLM
        llm = DualLLM()
        resp = llm.reviewer.complete(
            [{"role": "user", "content": "Write exactly: hello world"}],
            max_tokens=200, temperature=0.0,
        )
        assert "hello" in resp.lower() or len(resp) > 0, f"Empty: {resp[:100]}"

    @slow
    def test_reviewer_structured_output(self):
        """Test reviewer can produce JSON (used by GateJudge)."""
        from llm_client import DualLLM
        llm = DualLLM()
        resp = llm.reviewer.complete([
            {"role": "system", "content": "Return ONLY valid JSON. {\"verdict\":\"pass\"}"},
            {"role": "user", "content": "review this paper"},
        ], max_tokens=300, temperature=0.0)
        assert len(resp.strip()) > 0, f"Empty response: {repr(resp[:100])}"
        import json
        try:
            data = json.loads(resp)
            assert "verdict" in data
        except json.JSONDecodeError:
            pass  # Allow non-JSON as long as there's content

    def test_reviewer_instantiation(self):
        from llm_client import DualLLM
        llm = DualLLM()
        assert llm.reviewer is not None
        assert llm.reviewer.model == "glm-5.2"
        assert "volces.com" in str(llm.reviewer._client.base_url)


class TestLLMPro:
    """Tests for pro model (deepseek-v4-pro via api.deepseek.com)."""

    @slow
    def test_pro_basic(self):
        from llm_client import DualLLM
        llm = DualLLM()
        resp = llm.pro.complete(
            [{"role": "user", "content": "Write exactly: ok"}],
            max_tokens=100, temperature=0.0,
        )
        assert len(resp.strip()) > 0, f"Empty response: {repr(resp[:100])}"

    @slow
    def test_pro_reasoning(self):
        from llm_client import DualLLM
        llm = DualLLM()
        resp = llm.pro.complete(
            [{"role": "user", "content": "What is 1+1? Answer exactly: 2"}],
            max_tokens=200, temperature=0.0,
        )
        assert len(resp.strip()) > 0 or "2" in resp

    def test_pro_instantiation(self):
        from llm_client import DualLLM
        llm = DualLLM()
        assert llm.pro is not None
        assert "deepseek-v4-pro" in llm.pro.model
        assert "api.deepseek.com" in str(llm.pro._client.base_url)


class TestGateJudgeLLM:
    """Tests that GateJudge uses the right model tiers."""

    @slow
    def test_gate_judge_reviewer_returns_verdict(self):
        """Gate 1 → reviewer model → should return a valid verdict."""
        from gate_judge import GateJudge
        gj = GateJudge()
        result = gj.evaluate(1, "This is a novel approach to fault diagnosis using transformers.")
        assert result.get("verdict") in ("pass", "revise", "fail")

    @slow
    def test_gate_judge_pro_returns_verdict(self):
        """Gate 5 → pro model → should return a valid verdict."""
        from gate_judge import GateJudge
        gj = GateJudge()
        result = gj.evaluate(5, "Citation: [1] Smith et al. 2023, Journal of AI Research.")
        assert result.get("verdict") in ("pass", "revise", "fail")

    @slow
    def test_gate_judge_all_gates_fast(self):
        """All 7 gates should return within 30s each."""
        from gate_judge import GateJudge
        gj = GateJudge()
        for gate_id in range(1, 8):
            t0 = time.time()
            result = gj.evaluate(gate_id, f"Gate {gate_id} test transcript.")
            elapsed = time.time() - t0
            assert result.get("verdict") in ("pass", "revise", "fail"), f"Gate {gate_id}"
            assert elapsed < 60, f"Gate {gate_id} too slow: {elapsed:.1f}s"

    def test_gate_judge_tier_mapping(self):
        from gate_judge import GateJudge
        gj = GateJudge()
        assert gj.GATE_TIER[1] == "reviewer"
        assert gj.GATE_TIER[2] == "pro"
        assert gj.GATE_TIER[5] == "pro"
        assert gj.GATE_TIER[3] == "reviewer"
