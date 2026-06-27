"""AutonomousOrchestrator — Fully autonomous research lifecycle.

Triggers the full Phase 0-5 pipeline automatically:
1. Trend detection → idea discovery (Phase 0)
2. Literature review (Phase 1)
3. Method design (Phase 2)
4. Experimentation (Phase 3)
5. Paper writing (Phase 4-5)
6. Auto-compile and submit

Runs as a background daemon with configurable schedule.
"""

import json
import time
from datetime import datetime, timezone
from typing import Optional

from redis import Redis

from academic_loop import AcademicLoop, Phase
from trend_monitor import TrendMonitor


class AutonomousOrchestrator:
    """Fully autonomous research lifecycle manager.

    Listens to TrendMonitor for new research opportunities and
    automatically triggers the AcademicLoop pipeline.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379",
                 namespace: str = "autonomous"):
        self.r = Redis.from_url(redis_url, decode_responses=True)
        self.namespace = namespace
        self.trends = TrendMonitor(redis_url=redis_url)
        self.active_projects: dict[str, AcademicLoop] = {}

    def scan_and_launch(self) -> Optional[str]:
        """Scan trends and launch a new project if a gap is found."""
        trend_report = self.trends.report()
        if not trend_report.get("topic_scan"):
            return None

        # Pick the most promising topic
        topics = trend_report["topic_scan"]
        if not topics:
            return None

        topic = topics[0]["topic"]
        return self.launch_project(f"Auto-generated: {topic}")

    def launch_project(self, title: str) -> str:
        """Launch a full autonomous research project."""
        project_id = f"auto-{int(time.time())}"
        loop = AcademicLoop(
            redis_url=self.r.connection_pool.connection_kwargs.get("host", "localhost") + ":6379",
            namespace=f"{self.namespace}:{project_id}",
            project_title=title,
        )
        self.active_projects[project_id] = loop

        import threading
        thread = threading.Thread(
            target=loop.run,
            args=(Phase.PHASE0, Phase.PHASE5),
            daemon=True,
        )
        thread.start()
        return project_id

    def status(self) -> dict:
        return {
            "active_projects": list(self.active_projects.keys()),
            "trend_topics": self.trends.report().get("topic_scan", []),
        }
