"""ProjectManager — Multi-project management for the academic team.

Manages multiple AcademicLoop instances as independent projects.
Each project has its own namespace, phase state, and agent memory.

Usage:
    pm = ProjectManager()
    p1 = pm.create_project("Physics-Informed Fault Diagnosis")
    p2 = pm.create_project("Transformer for Time Series")
    pm.list_projects()
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from redis import Redis

PROJECTS_KEY = "academic:projects"
MAX_CONCURRENT_PROJECTS = 5


class ProjectManager:
    """Manage multiple concurrent research projects.

    Each project is isolated via its namespace in Redis.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.r = Redis.from_url(redis_url, decode_responses=True)

    def create_project(self, title: str, description: str = "") -> dict:
        """Create a new research project."""
        active = self.list_projects(status_filter="active")
        if len(active) >= MAX_CONCURRENT_PROJECTS:
            return {"error": f"max {MAX_CONCURRENT_PROJECTS} concurrent projects"}

        project_id = str(uuid.uuid4())[:12]
        project = {
            "id": project_id,
            "title": title,
            "description": description,
            "status": "active",
            "current_phase": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "namespace": f"project:{project_id}",
        }

        self.r.hset(PROJECTS_KEY, project_id, json.dumps(project, ensure_ascii=False))
        return project

    def get_project(self, project_id: str) -> Optional[dict]:
        """Get project details."""
        raw = self.r.hget(PROJECTS_KEY, project_id)
        if not raw:
            return None
        return json.loads(raw)

    def update_project(self, project_id: str, updates: dict):
        """Update project fields."""
        project = self.get_project(project_id)
        if not project:
            return
        project.update(updates)
        project["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.r.hset(PROJECTS_KEY, project_id, json.dumps(project, ensure_ascii=False))

    def archive_project(self, project_id: str):
        """Archive (soft-delete) a project."""
        self.update_project(project_id, {"status": "archived"})

    def delete_project(self, project_id: str):
        """Permanently delete a project."""
        self.r.hdel(PROJECTS_KEY, project_id)

    def list_projects(self, status_filter: Optional[str] = None) -> list[dict]:
        """List all projects, optionally filtered by status."""
        projects = []
        for key in self.r.hkeys(PROJECTS_KEY):
            try:
                p = json.loads(self.r.hget(PROJECTS_KEY, key))
                if status_filter and p.get("status") != status_filter:
                    continue
                projects.append(p)
            except (json.JSONDecodeError, TypeError):
                continue
        return sorted(projects, key=lambda p: p.get("created_at", ""), reverse=True)

    def get_project_stats(self) -> dict:
        """Get aggregate project statistics."""
        all_projects = self.list_projects()
        active = [p for p in all_projects if p.get("status") == "active"]
        return {
            "total": len(all_projects),
            "active": len(active),
            "max_allowed": MAX_CONCURRENT_PROJECTS,
            "archived": len(all_projects) - len(active),
            "phases_distribution": [p.get("current_phase", 0) for p in active],
        }
