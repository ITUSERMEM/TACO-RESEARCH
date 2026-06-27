"""ReviewFeedbackAnalyzer — Community interaction and reviewer feedback integration.

Analyzes peer reviewer comments from paper submissions and feeds
insights back into the system:
- Common reviewer concerns → update review calibration
- Reviewer style preferences → adjust paper writing style
- Rejection reasons → prioritize future research directions
"""

import json
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from redis import Redis


REVIEW_KEY = "feedback:reviews"


class ReviewFeedbackAnalyzer:
    """Analyze peer reviewer feedback to improve the system.

    Each review record contains:
    - venue: target journal/conference
    - decision: accept / minor / major / reject
    - reviewer_comments: parsed comments
    - action_items: what the system should learn
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.r = Redis.from_url(redis_url, decode_responses=True)

    def record_review(self, venue: str, decision: str,
                      reviewer_comments: list[str],
                      paper_id: str = "") -> str:
        """Record peer reviewer feedback."""
        review_id = f"rev-{int(time.time())}"
        entry = {
            "id": review_id,
            "venue": venue,
            "decision": decision,
            "comments": reviewer_comments,
            "paper_id": paper_id or review_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.r.rpush(REVIEW_KEY, json.dumps(entry, ensure_ascii=False))
        self.r.ltrim(REVIEW_KEY, 0, 99)
        return review_id

    def analyze_common_issues(self) -> list[dict]:
        """Find most common reviewer concerns across all submissions."""
        issue_counter = Counter()
        total_reviews = 0

        for item in self.r.lrange(REVIEW_KEY, 0, -1):
            try:
                review = json.loads(item)
                total_reviews += 1
                for comment in review.get("comments", []):
                    topic = self._classify_comment(comment)
                    issue_counter[topic] += 1
            except (json.JSONDecodeError, TypeError):
                continue

        return [
            {"issue": issue, "count": count,
             "percentage": round(count / max(total_reviews, 1) * 100, 1)}
            for issue, count in issue_counter.most_common(10)
        ]

    def get_venue_specific_issues(self, venue: str) -> list[str]:
        """Get common issues specific to a venue."""
        issues = []
        for item in self.r.lrange(REVIEW_KEY, 0, -1):
            try:
                review = json.loads(item)
                if review.get("venue", "").lower() == venue.lower():
                    for comment in review.get("comments", []):
                        issues.append(comment)
            except json.JSONDecodeError:
                continue
        return issues[:20]

    def get_rejection_reasons(self) -> list[dict]:
        """Analyze reasons for rejection decisions."""
        rejections = []
        for item in self.r.lrange(REVIEW_KEY, 0, -1):
            try:
                review = json.loads(item)
                if review.get("decision") == "reject":
                    rejections.append({
                        "venue": review.get("venue"),
                        "comments": review.get("comments", []),
                        "timestamp": review.get("timestamp"),
                    })
            except json.JSONDecodeError:
                continue
        return rejections

    @staticmethod
    def _classify_comment(comment: str) -> str:
        comment_lower = comment.lower()
        if "novelty" in comment_lower or "original" in comment_lower:
            return "novelty"
        if "experiment" in comment_lower or "evaluation" in comment_lower:
            return "experiments"
        if "writing" in comment_lower or "clarity" in comment_lower:
            return "writing_quality"
        if "citation" in comment_lower or "related work" in comment_lower:
            return "citations"
        if "theory" in comment_lower or "proof" in comment_lower:
            return "theoretical_rigor"
        if "baseline" in comment_lower or "comparison" in comment_lower:
            return "baselines"
        return "other"
