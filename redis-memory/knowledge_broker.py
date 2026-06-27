"""KnowledgeBroker — Cross-project knowledge sharing.

Bridges GlobalLessons with specific project needs:
- When Project B starts, auto-injects relevant lessons from Project A
- Uses semantic similarity via Redis search
- Prevents redundant lessons across projects
"""

import json
from typing import Optional

from redis import Redis
from global_lessons import GlobalLessons


class KnowledgeBroker:
    """Cross-project knowledge sharing agent.

    Routes lessons from completed projects to new projects
    based on topic overlap and lesson type.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.r = Redis.from_url(redis_url, decode_responses=True)
        self.lessons = GlobalLessons(redis_url=redis_url)

    def inject_for_new_project(self, project_title: str, project_id: str,
                                topics: Optional[list[str]] = None) -> str:
        """Build context block for a new project from accumulated wisdom."""
        lessons_text = self.lessons.inject_for_project(
            project_id=project_id, phases=[0, 1, 2, 3, 4, 5]
        )
        if not lessons_text:
            return ""
        return (
            f"<cross_project_knowledge>\n"
            f"Lessons from {self.lessons.count().get('total', 0)} previous projects:\n"
            f"{lessons_text}\n"
            f"</cross_project_knowledge>"
        )

    def share_finding(self, project_id: str, finding: str,
                       lesson_type: str = "experiment",
                       tags: Optional[list[str]] = None):
        """Share a finding from one project to all others."""
        self.lessons.add_lesson(
            lesson_type=lesson_type,
            content=finding,
            project_id=project_id,
            tags=tags,
        )

    def get_relevant(self, query: str, limit: int = 5) -> list[dict]:
        """Get relevant lessons using basic keyword matching."""
        query_lower = query.lower()
        keywords = query_lower.split()

        all_lessons = []
        for item in self.r.lrange("global:lessons", 0, -1):
            try:
                all_lessons.append(json.loads(item))
            except json.JSONDecodeError:
                continue

        scored = []
        for lesson in all_lessons:
            content = lesson.get("content", "").lower()
            score = sum(1 for k in keywords if k in content)
            if score > 0:
                scored.append((score, lesson))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:limit]]
