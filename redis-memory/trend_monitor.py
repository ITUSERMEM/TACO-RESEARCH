"""TrendMonitor — External signal monitoring for research trend adaptation.

Kocoro-inspired:
- Periodically queries Semantic Scholar / arXiv for trending topics
- Tracks conference deadlines (NeurIPS, ICML, CVPR, etc.)
- Monitors tool/library community popularity
- Produces trend reports for the AcademicLoop to adapt its pipeline
"""

import json
import os
import time
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from redis import Redis

CONFERENCE_DEADLINES = {
    "NeurIPS": {"month": 5, "day": 15, "url": "https://neurips.cc"},
    "ICML": {"month": 1, "day": 28, "url": "https://icml.cc"},
    "CVPR": {"month": 11, "day": 15, "url": "https://cvpr.thecvf.com"},
    "ICLR": {"month": 9, "day": 28, "url": "https://iclr.cc"},
    "AAAI": {"month": 8, "day": 15, "url": "https://aaai.org"},
    "IJCAI": {"month": 1, "day": 15, "url": "https://ijcai.org"},
}

DEFAULT_TOPICS = [
    "few-shot learning",
    "physics-informed neural networks",
    "fault diagnosis",
    "time-frequency analysis",
    "transfer learning",
    "meta-learning",
]


class TrendMonitor:
    """Research trend monitoring and deadline tracking.

    Produces structured reports for the AcademicLoop scheduler.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.r = Redis.from_url(redis_url, decode_responses=True)
        self.topics = DEFAULT_TOPICS

    def check_deadlines(self) -> list[dict]:
        """Check upcoming conference deadlines.

        Returns list of conferences with deadlines within 90 days.
        """
        now = datetime.now()
        upcoming = []

        for conf, info in CONFERENCE_DEADLINES.items():
            deadline = datetime(now.year, info["month"], info["day"])
            if deadline < now:
                deadline = datetime(now.year + 1, info["month"], info["day"])

            days_until = (deadline - now).days
            if 0 <= days_until <= 90:
                upcoming.append({
                    "conference": conf,
                    "days_until": days_until,
                    "deadline": deadline.strftime("%Y-%m-%d"),
                    "url": info["url"],
                    "urgency": "critical" if days_until < 14 else
                               "soon" if days_until < 30 else "upcoming",
                })

        return sorted(upcoming, key=lambda x: x["days_until"])

    def search_semantic_scholar(self, topic: str, limit: int = 5) -> list[dict]:
        """Query Semantic Scholar API for recent papers."""
        url = f"https://api.semanticscholar.org/graph/v1/paper/search"
        params = f"?query={urllib.parse.quote(topic)}&limit={limit}&year=2025-2026"
        try:
            req = urllib.request.Request(url + params,
                                         headers={"User-Agent": "AcademicTeam/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                papers = []
                for p in data.get("data", []):
                    papers.append({
                        "title": p.get("title", ""),
                        "paper_id": p.get("paperId", ""),
                        "url": p.get("url", ""),
                    })
                return papers
        except Exception:
            return []

    def scan_trending_topics(self) -> list[dict]:
        """Scan for trending research topics using Semantic Scholar."""
        results = []
        for topic in self.topics:
            papers = self.search_semantic_scholar(topic, limit=3)
            if papers:
                results.append({"topic": topic, "recent_papers": len(papers)})
            time.sleep(1)
        return results

    def detect_tool_obsolescence(self, tool_name: str) -> Optional[dict]:
        """Check if a tool/library is losing community traction."""
        url = f"https://api.semanticscholar.org/graph/v1/paper/search"
        params = f"?query={urllib.parse.quote(tool_name)}&limit=10&year=2024-2026"
        try:
            req = urllib.request.Request(url + params,
                                         headers={"User-Agent": "AcademicTeam/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                paper_count = len(data.get("data", []))
                return {
                    "tool": tool_name,
                    "papers_last_2_years": paper_count,
                    "trending": paper_count >= 5,
                }
        except Exception:
            return None

    def report(self) -> dict:
        """Generate a full trend report."""
        return {
            "deadlines": self.check_deadlines(),
            "topic_scan": self.scan_trending_topics(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
