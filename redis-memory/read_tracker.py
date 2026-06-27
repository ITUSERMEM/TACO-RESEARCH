"""ReadTracker — Cross-role task deduplication.

Kocoro-inspired ReadTracker:
- Per-turn + session-scoped dedup keyed by (path, mtime, size, offset, limit)
- Read-before-edit enforcement prevents blind writes
- Cross-role task dedup: literature researcher reads → methodologist skips
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional


class ReadTracker:
    """Track task inputs across multi-agent team to prevent redundant work."""

    def __init__(self):
        self._turn_reads: set[str] = set()
        self._last_reads: dict[str, dict] = {}
        self._cross_role_done: dict[str, set[str]] = defaultdict(set)
        self._turn = 0

    def new_turn(self):
        self._turn += 1
        self._turn_reads.clear()

    def record_read(self, key: str, mtime: Optional[float] = None, size: Optional[int] = None,
                    offset: int = 0, limit: Optional[int] = None):
        self._turn_reads.add(key)
        read_key = f"{key}:{offset}:{limit}"
        self._last_reads[read_key] = {
            "mtime": mtime,
            "size": size,
            "offset": offset,
            "limit": limit,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def check_dedup(self, key: str, offset: int = 0, limit: Optional[int] = None,
                    mtime: Optional[float] = None, size: Optional[int] = None) -> Optional[str]:
        read_key = f"{key}:{offset}:{limit}"
        entry = self._last_reads.get(read_key)
        if entry is None:
            return None

        mtime_match = entry.get("mtime") == mtime
        size_match = entry.get("size") == size
        if mtime is not None and not mtime_match:
            return None
        if size is not None and not size_match:
            return None

        return f"[Unchanged since last read at {entry['timestamp']}]"

    def check_read_before_write(self, path: str) -> Optional[str]:
        if path not in self._turn_reads:
            return f"Write blocked: {path} not read this turn"
        return None

    def mark_role_done(self, role: str, task_sig: str):
        self._cross_role_done[role].add(task_sig)

    def is_role_done(self, role: str, task_sig: str) -> bool:
        return task_sig in self._cross_role_done.get(role, set())

    def get_open_tasks(self, phase_tasks: list[str], role: str) -> list[str]:
        done = self._cross_role_done.get(role, set())
        return [t for t in phase_tasks if t not in done]

    def reset(self):
        self._turn_reads.clear()
        self._last_reads.clear()
        self._cross_role_done.clear()
