"""GlobalLessons — Cross-project knowledge transfer.

Kocoro-inspired global knowledge store:
- All Phase-completed lessons written to Redis global key
- New projects auto-inject relevant lessons
- Lessons categorized by type: experiment, writing, review, methodology
"""

import json
import time
from datetime import datetime, timezone
from typing import Optional

from redis import Redis

GLOBAL_KEY = "global:lessons"

LESSON_TYPES = {
    "experiment": "Experiment-related lessons (failed configs, GPU tips, data issues)",
    "writing": "Paper writing lessons (style, structure, reviewer feedback)",
    "review": "Review feedback lessons (common reviewer concerns, rebuttal strategies)",
    "methodology": "Methodology lessons (what worked, what didn't, design pitfalls)",
    "code": "Code engineering lessons (library issues, reproducibility tips)",
}


class GlobalLessons:
    """Cross-project lesson accumulation and retrieval.

    Each lesson has:
    - type (experiment/writing/review/methodology/code)
    - content (the lesson text)
    - project_id (source project)
    - timestamp
    - tags (for retrieval)
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.r = Redis.from_url(redis_url, decode_responses=True)

    def add_lesson(
        self,
        lesson_type: str,
        content: str,
        project_id: str = "",
        tags: Optional[list[str]] = None,
    ):
        """Store a lesson in the global knowledge base."""
        if lesson_type not in LESSON_TYPES:
            raise ValueError(f"Invalid lesson type: {lesson_type}. Use: {list(LESSON_TYPES.keys())}")

        entry = {
            "type": lesson_type,
            "content": content[:2000],
            "project_id": project_id,
            "tags": tags or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.r.rpush(GLOBAL_KEY, json.dumps(entry, ensure_ascii=False))

        # Keep only the latest 500 lessons
        length = self.r.llen(GLOBAL_KEY)
        if length > 500:
            self.r.ltrim(GLOBAL_KEY, length - 500, -1)

    def get_lessons(
        self,
        lesson_type: Optional[str] = None,
        tags: Optional[list[str]] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Retrieve lessons, optionally filtered by type and tags."""
        all_lessons = []
        for item in self.r.lrange(GLOBAL_KEY, 0, -1):
            try:
                lesson = json.loads(item)
                all_lessons.append(lesson)
            except json.JSONDecodeError:
                continue

        filtered = []
        for lesson in all_lessons:
            if lesson_type and lesson.get("type") != lesson_type:
                continue
            if tags:
                lesson_tags = set(lesson.get("tags", []))
                if not lesson_tags.intersection(tags):
                    continue
            filtered.append(lesson)

        return filtered[-limit:]

    def get_by_project(self, project_id: str, limit: int = 20) -> list[dict]:
        """Get lessons from a specific project."""
        all_lessons = []
        for item in self.r.lrange(GLOBAL_KEY, 0, -1):
            try:
                lesson = json.loads(item)
                all_lessons.append(lesson)
            except json.JSONDecodeError:
                continue
        project_lessons = [l for l in all_lessons if l.get("project_id") == project_id]
        return project_lessons[-limit:]

    def count(self) -> dict[str, int]:
        """Count lessons by type."""
        counts = {t: 0 for t in LESSON_TYPES}
        for item in self.r.lrange(GLOBAL_KEY, 0, -1):
            try:
                lesson = json.loads(item)
                lt = lesson.get("type")
                if lt in counts:
                    counts[lt] += 1
            except json.JSONDecodeError:
                continue
        counts["total"] = sum(counts.values())
        return counts

    def inject_for_project(self, project_id: str, phases: list[int]) -> str:
        """Build context block from relevant lessons for a new project."""
        relevant = []
        for lesson_type in LESSON_TYPES:
            lessons = self.get_lessons(lesson_type=lesson_type, limit=5)
            for l in lessons:
                relevant.append(f"[{l['type']}] {l['content'][:200]}")

        if not relevant:
            return ""

        parts = ["<global_lessons>"]
        parts.append(f"project: {project_id}")
        for r in relevant:
            parts.append(r)
        parts.append("</global_lessons>")
        return "\n".join(parts)

    def close(self):
        self.r.close()
