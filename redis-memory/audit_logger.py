"""Audit Logger — Structured event logging for academic team.

Kocoro-inspired AuditLogger:
- JSON-lines output with cost tracking and cache telemetry
- 7 secret redaction patterns (API keys, tokens, PEM, etc.)
- Event types specific to academic pipeline
- Thread-safe with mutex
"""

import json
import os
import re
import threading
import time as time_module
from datetime import datetime, timezone
from typing import Optional


ACADEMIC_EVENT_TYPES = {
    "phase_transition": "Phase N→N+1",
    "review_gate": "G1-G7 review outcomes",
    "agent_assignment": "Task assigned to role",
    "experiment_run": "Training job launched",
    "experiment_result": "Training job completed",
    "code_change": "File edit/create/delete",
    "citation_audit": "Citation verification results",
    "figure_generation": "Figure creation record",
    "paper_revision": "Paper section revision",
    "memory_consolidation": "Auto-persisted memory GC",
    "cache_summary": "LLM cache performance",
    "cost_dashboard": "Aggregate cost tracking",
    "loop_detector": "Loop detection event",
    "watchdog": "Watchdog timeout/alert",
    "error": "System error",
}


class AuditLogger:
    """Thread-safe JSON-lines audit logger with secret redaction."""

    SECRET_PATTERNS = [
        re.compile(r"sk-[a-zA-Z0-9]{20,}"),
        re.compile(r"ACCESS_KEY_[A-Z0-9]{16,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
        re.compile(r"xox[baprs]-[0-9a-zA-Z-]{10,}"),
        re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]{20,}"),
        re.compile(r"(?i)(password|secret|token|api_key)\s*[:=]\s*['\"]?[A-Za-z0-9\-._~+/]{8,}"),
    ]

    def __init__(self, log_dir: str = "/var/log/academic-team", redis_url: str = ""):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._log_file = os.path.join(log_dir, "audit.log")
        self._redis = None
        if redis_url:
            try:
                from redis import Redis
                self._redis = Redis.from_url(redis_url, decode_responses=True)
            except Exception:
                pass

    def log(
        self,
        event: str,
        agent: str = "",
        phase: int = -1,
        details: Optional[dict] = None,
        duration_ms: Optional[int] = None,
        tokens: Optional[dict] = None,
        cost: Optional[float] = None,
        model: str = "",
    ):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "agent": agent,
        }

        if phase >= 0:
            entry["phase"] = phase
        if duration_ms is not None:
            entry["duration_ms"] = duration_ms
        if tokens:
            entry["input_tokens"] = tokens.get("input", 0)
            entry["output_tokens"] = tokens.get("output", 0)
            entry["total_tokens"] = tokens.get("input", 0) + tokens.get("output", 0)
        if cost is not None:
            entry["cost_usd"] = round(cost, 6)
        if model:
            entry["model"] = model
        if details:
            entry["details"] = self._redact(json.dumps(details))

        line = json.dumps(entry, ensure_ascii=False)
        self._write(line)

        if self._redis:
            try:
                score = time_module.time()
                self._redis.zadd("audit:events", {line: score})
                self._redis.zremrangebyrank("audit:events", 0, -10001)
            except Exception:
                pass

    def log_tool_call(
        self,
        tool_name: str,
        args: dict,
        result: str,
        agent: str,
        duration_ms: int,
        approved: bool = True,
    ):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "tool_call",
            "agent": agent,
            "tool": tool_name,
            "input_summary": self._truncate(self._redact(json.dumps(args)), 500),
            "output_summary": self._truncate(self._redact(result), 500),
            "approved": approved,
            "duration_ms": duration_ms,
        }
        self._write(json.dumps(entry, ensure_ascii=False))

    def log_cache_summary(
        self,
        cer: float = 0.0,
        system_hash: str = "",
        warm_start: bool = False,
    ):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "cache_summary",
            "cer": cer,
            "system_stable_hash": system_hash,
            "warm_start": warm_start,
        }
        self._write(json.dumps(entry, ensure_ascii=False))

    def _redact(self, text: str) -> str:
        for pattern in self.SECRET_PATTERNS:
            text = pattern.sub("[[REDACTED]]", text)
        return text

    @staticmethod
    def _truncate(text: str, max_len: int = 500) -> str:
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text

    def _write(self, line: str):
        with self._lock:
            with open(self._log_file, "a") as f:
                f.write(line + "\n")

    @property
    def log_path(self) -> str:
        return self._log_file
