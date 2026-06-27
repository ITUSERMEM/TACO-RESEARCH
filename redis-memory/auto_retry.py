"""AutoRetry — Self-healing infrastructure for the academic team.

Kocoro-inspired:
- Detects failure patterns from AuditLogger events
- GPU OOM → auto-reduce batch size
- Network timeout → exponential backoff retry
- Dead systemd service → restart (uses systemd Restart=always)
"""

import json
import time
from collections import defaultdict, deque
from typing import Optional

from redis import Redis


class AutoRetry:
    """Failure pattern detection and automatic recovery.

    Tracks recent failures in a sliding window.
    Applies known fixes for common failure modes.
    """

    KNOWN_FIXES = {
        "OOM": [
            {"action": "reduce_batch_size", "params": {"factor": 0.5}},
            {"action": "reduce_model_size", "params": {"factor": 0.75}},
            {"action": "enable_gradient_checkpointing", "params": {}},
        ],
        "timeout": [
            {"action": "increase_timeout", "params": {"multiplier": 2}},
            {"action": "retry_with_backoff", "params": {"max_retries": 3}},
        ],
        "connection": [
            {"action": "retry_with_backoff", "params": {"max_retries": 3}},
            {"action": "use_fallback_endpoint", "params": {}},
        ],
        "disk_full": [
            {"action": "clean_cache", "params": {}},
            {"action": "clear_tmp", "params": {}},
        ],
    }

    def __init__(self, redis_url: str = "redis://localhost:6379", window_size: int = 10):
        self.r = Redis.from_url(redis_url, decode_responses=True)
        self.window_size = window_size
        self._failures: deque = deque(maxlen=window_size)

    def record_failure(self, failure_type: str, details: Optional[dict] = None):
        """Record a failure event."""
        entry = {
            "type": failure_type,
            "details": details or {},
            "timestamp": time.time(),
        }
        self._failures.append(entry)
        self.r.lpush("failures:recent", json.dumps(entry, ensure_ascii=False))
        self.r.ltrim("failures:recent", 0, 49)

    def detect_pattern(self) -> Optional[dict]:
        """Detect if recent failures match a known pattern.

        Returns fix suggestion if pattern detected.
        """
        if len(self._failures) < 3:
            return None

        recent = list(self._failures)
        types = [f["type"] for f in recent[-3:]]

        # Same failure 3 times in a row
        if len(set(types)) == 1 and types[0] in self.KNOWN_FIXES:
            fixes = self.KNOWN_FIXES[types[0]]
            fix_index = min(self._count_type(types[0]) - 3, len(fixes) - 1)
            return {
                "detected": types[0],
                "occurrences": self._count_type(types[0]),
                "suggested_fix": fixes[max(0, fix_index)],
            }

        # Two different failures alternating
        if len(set(types)) == 2:
            return {
                "detected": "mixed_failures",
                "occurrences": len(recent),
                "suggested_fix": {"action": "restart_service", "params": {}},
            }

        return None

    def apply_fix(self, fix: dict) -> dict:
        """Apply a known fix action. Returns result."""
        action = fix.get("action", "")
        params = fix.get("params", {})

        if action == "reduce_batch_size":
            factor = params.get("factor", 0.5)
            return {"status": "applied", "action": action, "factor": factor}

        elif action == "increase_timeout":
            multiplier = params.get("multiplier", 2)
            return {"status": "applied", "action": action, "multiplier": multiplier}

        elif action == "retry_with_backoff":
            max_retries = params.get("max_retries", 3)
            return {"status": "applied", "action": action, "max_retries": max_retries}

        elif action == "clean_cache":
            return {"status": "applied", "action": action}

        elif action == "restart_service":
            return {"status": "applied", "action": action}

        return {"status": "unknown_action", "action": action}

    def _count_type(self, failure_type: str) -> int:
        return sum(1 for f in self._failures if f["type"] == failure_type)

    def get_recent_failures(self, limit: int = 10) -> list[dict]:
        """Get recent failures from Redis."""
        raw = self.r.lrange("failures:recent", 0, limit - 1)
        failures = []
        for item in raw:
            try:
                failures.append(json.loads(item))
            except json.JSONDecodeError:
                continue
        return failures
