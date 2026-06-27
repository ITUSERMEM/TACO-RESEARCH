"""CheckpointManager — Multi-day experiment checkpointing.

Kocoro-inspired checkpoint system:
- Serializes PhaseTracker state + session messages to Redis
- Supports --resume from interrupted phase
- GPU state persistence for experiment recovery
"""

import json
import time
from datetime import datetime, timezone
from typing import Optional

from redis import Redis

CHECKPOINT_PREFIX = "checkpoint:"


class CheckpointManager:
    """Phase-level checkpointing for long-running experiments.

    Each checkpoint stores:
    - PhaseTracker state (JSON)
    - Session messages (last N)
    - GPU state (if available)
    - Timestamp
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.r = Redis.from_url(redis_url, decode_responses=True)

    def save(self, project_id: str, phase: int, tracker_state: dict,
             messages: Optional[list[dict]] = None, gpu_state: Optional[dict] = None):
        """Save a checkpoint."""
        key = f"{CHECKPOINT_PREFIX}{project_id}:phase{phase}"
        checkpoint = {
            "project_id": project_id,
            "phase": phase,
            "tracker": tracker_state,
            "messages": (messages or [])[-20:],
            "gpu": gpu_state or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.r.json().set(key, "$", checkpoint)
        self.r.expire(key, 86400 * 30)  # 30 day TTL

    def load(self, project_id: str, phase: int) -> Optional[dict]:
        """Load a checkpoint."""
        key = f"{CHECKPOINT_PREFIX}{project_id}:phase{phase}"
        data = self.r.json().get(key)
        return data

    def list_checkpoints(self, project_id: str) -> list[dict]:
        """List all checkpoints for a project."""
        keys = self.r.keys(f"{CHECKPOINT_PREFIX}{project_id}:*")
        checkpoints = []
        for key in sorted(keys):
            data = self.r.json().get(key)
            if data:
                checkpoints.append({
                    "phase": data.get("phase"),
                    "timestamp": data.get("timestamp"),
                    "message_count": len(data.get("messages", [])),
                })
        return checkpoints

    def delete(self, project_id: str, phase: int):
        """Delete a checkpoint."""
        key = f"{CHECKPOINT_PREFIX}{project_id}:phase{phase}"
        self.r.delete(key)

    def latest(self, project_id: str) -> Optional[dict]:
        """Find the latest checkpoint for a project."""
        checkpoints = self.list_checkpoints(project_id)
        if not checkpoints:
            return None
        latest = max(checkpoints, key=lambda c: c.get("timestamp", ""))
        return self.load(project_id, latest["phase"])

    def resume_from(self, project_id: str) -> Optional[dict]:
        """Get data needed to resume a project."""
        cp = self.latest(project_id)
        if not cp:
            return None
        return {
            "project_id": cp.get("project_id"),
            "phase": cp.get("phase"),
            "tracker": cp.get("tracker"),
            "messages": cp.get("messages", []),
            "checkpoint_time": cp.get("timestamp"),
        }

    def save_gpu_state(self, project_id: str, gpu_info: dict):
        """Save GPU state separately (smaller, more frequent updates)."""
        key = f"{CHECKPOINT_PREFIX}{project_id}:gpu"
        self.r.json().set(key, "$", {
            "gpu": gpu_info,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.r.expire(key, 3600)
