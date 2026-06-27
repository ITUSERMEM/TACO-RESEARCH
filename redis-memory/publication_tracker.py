"""PublicationTracker — Paper outcome tracking.

Tracks papers through the submission pipeline:
- Preprint posted to arXiv
- Submitted to conference/journal
- Decision received
- Acceptance rate statistics
- Outcome → system improvement feedback loop
"""

import json
from datetime import datetime, timezone
from typing import Optional

from redis import Redis

PUB_KEY = "academic:publications"


class PublicationTracker:
    """Track paper lifecycle from draft to publication.

    Each publication record tracks:
    - title, authors, venue
    - submission date, decision date, decision
    - arXiv ID (if posted)
    - acceptance status
    - reviewer feedback (if available)
    """

    STATUSES = ["draft", "submitted", "under_review", "accepted", "rejected", "published"]

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.r = Redis.from_url(redis_url, decode_responses=True)

    def register_paper(self, title: str, authors: list[str],
                       venue: str, project_id: str = "") -> str:
        """Register a new paper in the tracking system."""
        paper_id = f"pub-{int(datetime.now().timestamp())}"
        entry = {
            "id": paper_id,
            "title": title,
            "authors": authors,
            "venue": venue,
            "project_id": project_id,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "history": [{"action": "created", "timestamp": datetime.now(timezone.utc).isoformat()}],
        }
        self.r.hset(PUB_KEY, paper_id, json.dumps(entry, ensure_ascii=False))
        return paper_id

    def update_status(self, paper_id: str, new_status: str,
                      details: Optional[dict] = None):
        """Update the status of a paper."""
        if new_status not in self.STATUSES:
            raise ValueError(f"Invalid status: {new_status}")

        raw = self.r.hget(PUB_KEY, paper_id)
        if not raw:
            return
        paper = json.loads(raw)
        paper["status"] = new_status
        paper["updated_at"] = datetime.now(timezone.utc).isoformat()
        paper["history"].append({
            "action": new_status,
            "timestamp": paper["updated_at"],
            "details": details or {},
        })
        self.r.hset(PUB_KEY, paper_id, json.dumps(paper, ensure_ascii=False))

    def get_paper(self, paper_id: str) -> Optional[dict]:
        raw = self.r.hget(PUB_KEY, paper_id)
        return json.loads(raw) if raw else None

    def list_papers(self, status_filter: Optional[str] = None) -> list[dict]:
        papers = []
        for key in self.r.hkeys(PUB_KEY):
            try:
                p = json.loads(self.r.hget(PUB_KEY, key))
                if status_filter and p.get("status") != status_filter:
                    continue
                papers.append(p)
            except (json.JSONDecodeError, TypeError):
                continue
        return sorted(papers, key=lambda p: p.get("created_at", ""), reverse=True)

    def get_stats(self) -> dict:
        """Get publication statistics."""
        all_papers = self.list_papers()
        accepted = [p for p in all_papers if p["status"] in ("accepted", "published")]
        rejected = [p for p in all_papers if p["status"] == "rejected"]
        submitted = [p for p in all_papers if p["status"]
                     in ("submitted", "under_review")]

        return {
            "total": len(all_papers),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "under_review": len(submitted),
            "acceptance_rate": round(
                len(accepted) / max(len(accepted) + len(rejected), 1) * 100, 1
            ),
        }
