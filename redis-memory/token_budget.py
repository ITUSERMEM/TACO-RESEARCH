"""TokenBudget — Three-layer token budget control system.

Shannon-inspired budgets at each level:
  - Call level: max_tokens per LLM call (exists)
  - Session level: total budget per pipeline run (new)
  - Task level: budget per research task across sessions (new)

Exceed budget → warning → degrade (switch to cheaper model) → stop.
"""

import time
from typing import Optional

from redis import Redis

BUDGET_KEY = "budget:session"
TASK_BUDGET_KEY = "budget:task"
SESSION_TOKEN_LIMIT = 500_000   # 500K tokens per pipeline run
TASK_TOKEN_LIMIT = 5_000_000    # 5M tokens per research task
WARNING_PCT = 0.8               # warn at 80%
DEGRADE_PCT = 0.95              # degrade at 95%
HARD_LIMIT_PCT = 1.0            # stop at 100%


class TokenBudget:
    """Three-layer token budget tracker."""

    def __init__(self, redis_url: str = "redis://localhost:6379",
                 session_id: str = "default", task_id: str = "default"):
        self.r = Redis.from_url(redis_url, decode_responses=True)
        self.session_id = session_id
        self.task_id = task_id

    def record(self, tokens: int, model: str = "unknown"):
        """Record token usage at all three levels."""
        now = time.time()

        # Call level: immediate
        self.r.zadd(f"{BUDGET_KEY}:{self.session_id}", {f"{now}:{model}": tokens})

        # Session level: sum
        self.r.hincrby(f"{BUDGET_KEY}:{self.session_id}:total", "tokens", tokens)
        self.r.hincrby(f"{BUDGET_KEY}:{self.session_id}:total", "calls", 1)

        # Task level (cross-session)
        self.r.hincrby(f"{TASK_BUDGET_KEY}:{self.task_id}", "tokens", tokens)
        self.r.hincrby(f"{TASK_BUDGET_KEY}:{self.task_id}", "calls", 1)

        # Cap storage
        for key in [f"{BUDGET_KEY}:{self.session_id}", f"{TASK_BUDGET_KEY}:{self.task_id}"]:
            self.r.expire(key, 86400 * 7)  # 7-day TTL

    def session_usage(self) -> dict:
        """Get session-level token usage."""
        tokens = int(self.r.hget(f"{BUDGET_KEY}:{self.session_id}:total", "tokens") or 0)
        calls = int(self.r.hget(f"{BUDGET_KEY}:{self.session_id}:total", "calls") or 0)
        pct = round(tokens / SESSION_TOKEN_LIMIT * 100, 1) if SESSION_TOKEN_LIMIT else 0
        return {"tokens": tokens, "calls": calls, "pct": pct, "limit": SESSION_TOKEN_LIMIT}

    def task_usage(self) -> dict:
        """Get task-level token usage."""
        tokens = int(self.r.hget(f"{TASK_BUDGET_KEY}:{self.task_id}", "tokens") or 0)
        calls = int(self.r.hget(f"{TASK_BUDGET_KEY}:{self.task_id}", "calls") or 0)
        pct = round(tokens / TASK_TOKEN_LIMIT * 100, 1) if TASK_TOKEN_LIMIT else 0
        return {"tokens": tokens, "calls": calls, "pct": pct, "limit": TASK_TOKEN_LIMIT}

    def check(self) -> dict:
        """Check budget status. Returns action: ok / warn / degrade / stop."""
        session = self.session_usage()
        task = self.task_usage()
        session_pct = session["pct"] / 100
        task_pct = task["pct"] / 100

        max_pct = max(session_pct, task_pct)
        if max_pct >= HARD_LIMIT_PCT:
            action = "stop"
        elif max_pct >= DEGRADE_PCT:
            action = "degrade"
        elif max_pct >= WARNING_PCT:
            action = "warn"
        else:
            action = "ok"

        return {
            "action": action,
            "session": session,
            "task": task,
            "max_pct": round(max_pct * 100, 1),
            "degrade_tier": "small" if action == "degrade" else None,
        }

    def degrade_model(self, current_tier: str) -> str:
        """Degrade to a cheaper model tier when budget is tight."""
        tiers = ["large", "medium", "small"]
        idx = tiers.index(current_tier) if current_tier in tiers else 1
        return tiers[min(idx + 1, len(tiers) - 1)]

    def reset_session(self):
        """Reset session budget counters."""
        for key in self.r.keys(f"{BUDGET_KEY}:{self.session_id}*"):
            self.r.delete(key)

    def close(self):
        self.r.close()
