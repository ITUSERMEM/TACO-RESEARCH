"""AnalyticsEngine — Aggregated performance analytics for the academic team.

Reads from:
- AuditLogger Redis events (audit:events sorted set)
- PhaseTracker Timeseries (ts:academic:phase:*)
- AgentMemory LTM (idx:ltm)
- GlobalLessons (global:lessons)

Produces:
- Phase pass/fail rates
- Average iterations per phase
- Token consumption trends
- Failure mode distribution
- Skill usage frequency
"""

import json
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Optional

from redis import Redis


class AnalyticsEngine:
    """Aggregated analytics dashboard.

    Usage:
        ae = AnalyticsEngine()
        report = ae.generate_report()
        print(json.dumps(report, indent=2))
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.r = Redis.from_url(redis_url, decode_responses=True)

    def generate_report(self) -> dict:
        """Generate comprehensive analytics report."""
        return {
            "phase_performance": self.phase_performance(),
            "gate_results": self.gate_results(),
            "token_usage": self.token_usage(),
            "failure_modes": self.failure_modes(),
            "skill_usage": self.skill_usage(),
            "lesson_distribution": self.lesson_distribution(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def phase_performance(self) -> dict:
        """Phase pass/fail rates and average iterations."""
        phase_stats = defaultdict(lambda: {"total": 0, "pass": 0, "iterations": []})

        events = self._get_audit_events()

        for event in events:
            e = event.get("event", "")
            phase = event.get("phase", -1)
            if phase < 0:
                continue

            phase_stats[phase]["total"] += 1

            if e == "phase_complete":
                phase_stats[phase]["pass"] += 1

            tokens = event.get("total_tokens", 0)
            if tokens:
                if "tokens_per_phase" not in phase_stats[phase]:
                    phase_stats[phase]["tokens_per_phase"] = []
                phase_stats[phase]["tokens_per_phase"].append(tokens)

        result = {}
        for phase, stats in sorted(phase_stats.items()):
            pass_rate = stats["pass"] / max(stats["total"], 1)
            avg_tokens = 0
            tokens_list = stats.get("tokens_per_phase", [])
            if tokens_list:
                avg_tokens = statistics.mean(tokens_list)
            result[f"Phase {phase}"] = {
                "total_runs": stats["total"],
                "pass_count": stats["pass"],
                "pass_rate": round(pass_rate, 2),
                "avg_tokens": int(avg_tokens),
            }
        return result

    def gate_results(self) -> dict:
        """Gate verdict distribution."""
        gates = defaultdict(lambda: Counter())

        events = self._get_audit_events()
        for event in events:
            details = event.get("details", {})
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except json.JSONDecodeError:
                    continue
            if isinstance(details, dict):
                verdict = details.get("verdict", "")
                gate = details.get("gate", "")
                if verdict and gate:
                    gates[gate][verdict] += 1

        result = {}
        for gate, verdicts in sorted(gates.items()):
            total = sum(verdicts.values())
            result[gate] = {
                "total": total,
                "pass": verdicts.get("pass", 0),
                "revise": verdicts.get("revise", 0),
                "fail": verdicts.get("fail", 0),
                "pass_rate": round(verdicts.get("pass", 0) / max(total, 1), 2),
            }
        return result

    def token_usage(self) -> dict:
        """Token consumption trends."""
        tokens_by_model = defaultdict(int)
        tokens_by_agent = defaultdict(int)
        total_tokens = 0
        total_cost = 0.0

        events = self._get_audit_events()
        for event in events:
            tokens = event.get("total_tokens", 0)
            if tokens:
                total_tokens += tokens
                model = event.get("model", "unknown")
                tokens_by_model[model] += tokens
                agent = event.get("agent", "unknown")
                tokens_by_agent[agent] += tokens
            cost = event.get("cost_usd", 0)
            total_cost += cost

        return {
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "by_model": dict(tokens_by_model),
            "by_agent": dict(tokens_by_agent),
            "event_count": len(events),
        }

    def failure_modes(self) -> list[dict]:
        """Most common failure modes."""
        failures = Counter()

        events = self._get_audit_events()
        for event in events:
            e = event.get("event", "")
            if "error" in e or "fail" in e:
                failures[e] += 1

            details = event.get("details", {})
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except json.JSONDecodeError:
                    details = {}
            if isinstance(details, dict):
                for issue in details.get("issues", []):
                    failures[f"issue: {issue[:50]}"] += 1

        return [{"failure": k, "count": v} for k, v in failures.most_common(10)]

    def skill_usage(self) -> list[dict]:
        """Most frequently used skills."""
        skill_counts = Counter()

        events = self._get_audit_events()
        for event in events:
            e = event.get("event", "")
            if e == "tool_call":
                tool = event.get("tool", "")
                if tool:
                    skill_counts[tool] += 1
            agent = event.get("agent", "")
            if agent:
                skill_counts[f"agent:{agent}"] += 1

        return [{"skill": k, "calls": v} for k, v in skill_counts.most_common(15)]

    def lesson_distribution(self) -> dict:
        """Lesson counts by type from GlobalLessons."""
        try:
            counts_raw = self.r.lrange("global:lessons", 0, -1)
            types = Counter()
            for item in counts_raw:
                try:
                    lesson = json.loads(item)
                    lt = lesson.get("type", "unknown")
                    types[lt] += 1
                except json.JSONDecodeError:
                    continue
            return dict(types)
        except Exception:
            return {}

    def _get_audit_events(self, limit: int = 1000) -> list[dict]:
        try:
            raw = self.r.zrevrange("audit:events", 0, limit - 1)
            events = []
            for item in raw:
                try:
                    events.append(json.loads(item))
                except (json.JSONDecodeError, TypeError):
                    continue
            return events
        except Exception:
            return []
