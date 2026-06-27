"""MetaOptimizer — System self-optimization using experiment outcomes.

Kocoro-inspired:
- Analyzes past project outcomes 
- Tunes AcademicLoop parameters (MAX_ITERATIONS, gate thresholds, Watchdog timeouts)
- Recommends skill updates based on usage patterns
- Tracks which configurations lead to paper acceptance
"""

import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from redis import Redis

from analytics_engine import AnalyticsEngine


class MetaOptimizer:
    """Meta-learning loop for the academic team itself.

    Uses past project outcomes to tune system parameters.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.r = Redis.from_url(redis_url, decode_responses=True)
        self.analytics = AnalyticsEngine(redis_url=redis_url)

    def analyze_outcomes(self) -> dict:
        """Analyze outcomes of completed projects."""
        report = self.analytics.generate_report()
        phase_perf = report.get("phase_performance", {})
        gate_results = report.get("gate_results", {})
        return {
            "phase_performance": phase_perf,
            "gate_results": gate_results,
            "recommendations": self._generate_recommendations(phase_perf, gate_results),
        }

    def _generate_recommendations(self, phase_perf: dict, gate_results: dict) -> list[dict]:
        recs = []

        for phase, stats in phase_perf.items():
            pass_rate = stats.get("pass_rate", 1.0)
            if pass_rate < 0.5:
                recs.append({
                    "target": f"{phase}_threshold",
                    "current": "default",
                    "suggested": "reduce difficulty",
                    "reason": f"pass rate {pass_rate}",
                })

        for gate, stats in gate_results.items():
            fail_rate = stats.get("fail", 0) / max(stats.get("total", 1), 1)
            if fail_rate > 0.3:
                recs.append({
                    "target": f"{gate}_criteria",
                    "current": "default",
                    "suggested": "add intermediate gate",
                    "reason": f"fail rate {fail_rate}",
                })

        return recs

    def suggest_parameter_tuning(self) -> dict:
        """Suggest parameter changes based on historical data."""
        report = self.analytics.generate_report()
        phase_perf = report.get("phase_performance", {})

        suggestions = {}

        for phase, stats in phase_perf.items():
            avg_tokens = stats.get("avg_tokens", 0)
            if avg_tokens > 50000:
                suggestions[f"{phase}_max_iterations"] = {
                    "current": "unknown",
                    "suggested": "reduce by 30%",
                    "reason": f"high token usage ({avg_tokens} avg)",
                }

        return suggestions
