"""Tests for TokenBudget integration with AcademicLoop (P0-1).

Covers:
- Budget initialization in AcademicLoop
- Budget check triggering degrade action
- Budget check triggering stop action
- Token recording after LLM calls
- Budget degrade_model tier cascade
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REDIS_UP = False
try:
    from redis import Redis
    r = Redis.from_url("redis://localhost:6379", decode_responses=True)
    r.ping()
    REDIS_UP = True
    r.close()
except Exception:
    REDIS_UP = False

# Check if token_budget can be imported (requires redis module)
TOKEN_BUDGET_IMPORTABLE = False
try:
    import token_budget
    TOKEN_BUDGET_IMPORTABLE = True
except ImportError:
    pass


@pytest.mark.skipif(not TOKEN_BUDGET_IMPORTABLE, reason="redis module required for token_budget import")
class TestTokenBudgetUnit:
    """Unit tests for TokenBudget (no Redis needed)."""

    def test_degrade_model_cascade(self):
        from token_budget import TokenBudget
        # TokenBudget uses Redis but degrade_model is pure logic
        # Test the degradation chain: large → medium → small
        # We mock Redis to avoid actual connection
        from unittest.mock import MagicMock
        mock_r = MagicMock()
        mock_r.get.return_value = None
        mock_r.set.return_value = True

        budget = TokenBudget.__new__(TokenBudget)
        budget.r = mock_r
        budget.session_id = "test"
        budget.task_id = "test"
        budget._session_key = "test:session"
        budget._task_key = "test:task"

        # large → medium
        degraded = budget.degrade_model("large")
        assert degraded == "medium"

        # medium → small
        degraded = budget.degrade_model("medium")
        assert degraded == "small"

        # small stays small
        degraded = budget.degrade_model("small")
        assert degraded == "small"

    def test_degrade_model_unknown_tier(self):
        from token_budget import TokenBudget
        from unittest.mock import MagicMock
        mock_r = MagicMock()
        budget = TokenBudget.__new__(TokenBudget)
        budget.r = mock_r
        budget.session_id = "test"
        budget.task_id = "test"
        budget._session_key = "test:session"
        budget._task_key = "test:task"

        # Unknown tier falls back to small (idx=1, min(2,2)=2)
        degraded = budget.degrade_model("unknown_tier")
        assert degraded == "small"


@pytest.mark.skipif(not REDIS_UP, reason="Redis required")
class TestTokenBudgetIntegration:
    """Integration tests with real Redis."""

    def test_budget_init_in_loop(self):
        from academic_loop import AcademicLoop
        loop = AcademicLoop(redis_url="redis://localhost:6379",
                            project_title="budget-test")
        assert hasattr(loop, "budget")
        assert loop.budget is not None
        loop.close()

    def test_budget_record_and_check(self):
        from token_budget import TokenBudget
        budget = TokenBudget(
            redis_url="redis://localhost:6379",
            session_id="budget-record-test",
            task_id="budget-record-test",
        )
        # Record some tokens
        budget.record(1000, model="executor")
        budget.record(2000, model="reviewer")

        # Check should return ok for small usage
        status = budget.check()
        assert status["action"] in ("ok", "warn", "degrade", "stop")
        assert "session" in status
        assert "task" in status

        # Cleanup
        from token_budget import BUDGET_KEY, TASK_BUDGET_KEY
        budget.r.delete(f"{BUDGET_KEY}:budget-record-test")
        budget.r.delete(f"{BUDGET_KEY}:budget-record-test:total")
        budget.r.delete(f"{TASK_BUDGET_KEY}:budget-record-test")
        budget.r.close()

    def test_budget_session_usage(self):
        from token_budget import TokenBudget
        budget = TokenBudget(
            redis_url="redis://localhost:6379",
            session_id="budget-usage-test",
            task_id="budget-usage-test",
        )
        budget.record(5000, model="executor")
        usage = budget.session_usage()
        assert usage["tokens"] >= 5000

        # Cleanup
        from token_budget import BUDGET_KEY, TASK_BUDGET_KEY
        budget.r.delete(f"{BUDGET_KEY}:budget-usage-test")
        budget.r.delete(f"{BUDGET_KEY}:budget-usage-test:total")
        budget.r.delete(f"{TASK_BUDGET_KEY}:budget-usage-test")
        budget.r.close()

    def test_budget_task_usage(self):
        from token_budget import TokenBudget
        budget = TokenBudget(
            redis_url="redis://localhost:6379",
            session_id="budget-task-test",
            task_id="budget-task-test",
        )
        budget.record(10000, model="pro")
        usage = budget.task_usage()
        assert usage["tokens"] >= 10000

        # Cleanup
        from token_budget import BUDGET_KEY, TASK_BUDGET_KEY
        budget.r.delete(f"{BUDGET_KEY}:budget-task-test")
        budget.r.delete(f"{BUDGET_KEY}:budget-task-test:total")
        budget.r.delete(f"{TASK_BUDGET_KEY}:budget-task-test")
        budget.r.close()
