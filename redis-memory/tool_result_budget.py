"""ToolResultBudget — Kocoro-inspired tool result budget and spill to disk.

Prevents large tool results from blowing the LLM context window:
- Single result >50K chars → spill to disk, replace with preview + path
- Aggregate cap 200K chars → largest results spilled first until under limit
- Replacement state persisted across turns for prompt cache stability
- Cleanup on session end

Usage:
    budget = ToolResultBudget(session_id="exp-1")
    results = budget.apply_all(tool_results)
"""

import hashlib
import json
import os
import tempfile
import time
from typing import Optional

SPILL_DIR = os.path.join(tempfile.gettempdir(), "academic-tool-spills")
SPILL_THRESHOLD = 50_000  # chars — single result spills if larger
AGGREGATE_CAP = 200_000  # chars — total across all results
MIN_AGGREGATE_SPILL = 5_000  # chars — smaller than this won't be considered for aggregate spill
PREVIEW_CHARS = 2_000  # chars of content to keep in preview


class ToolResultBudget:
    """Apply per-result and aggregate budget to tool results.

    Like Kocoro's spill.go + toolresult_budget.go:
    - oversize results are written to SPILL_DIR with content hash filename
    - preview replaces full content in the context
    - replacement state is cached per session for cross-turn stability
    """

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self._replacements: dict[str, str] = {}  # call_id → replacement_text
        os.makedirs(SPILL_DIR, exist_ok=True)

    def apply_all(self, results: list[dict]) -> list[dict]:
        """Apply budget to all tool results. Returns processed results list."""
        processed = []
        for r in results:
            r = self._apply_per_result(r)
            processed.append(r)
        processed = self._apply_aggregate_cap(processed)
        return processed

    def _apply_per_result(self, result: dict) -> dict:
        """Spill individual results exceeding SPILL_THRESHOLD."""
        content = result.get("content", "")
        if not isinstance(content, str) or len(content) <= SPILL_THRESHOLD:
            return result

        call_id = result.get("call_id", f"call-{int(time.time()*1000)}")
        preview = content[:PREVIEW_CHARS]
        spill_path = self._write_spill(call_id, content)

        replacement = (
            f"[Tool result spilled to disk: {spill_path} "
            f"({len(content)} chars)]\n\n"
            f"Preview (first {PREVIEW_CHARS} chars):\n{preview}"
        )
        self._replacements[call_id] = replacement
        result["content"] = replacement
        return result

    def _apply_aggregate_cap(self, results: list[dict]) -> list[dict]:
        """Reduce total chars across all results to AGGREGATE_CAP."""
        total = sum(len(r.get("content", "")) for r in results)
        if total <= AGGREGATE_CAP:
            return results

        spillable = [r for r in results if len(r.get("content", "")) >= MIN_AGGREGATE_SPILL]
        spillable.sort(key=lambda r: len(r.get("content", "")), reverse=True)

        for r in spillable:
            if total <= AGGREGATE_CAP:
                break
            content = r.get("content", "")
            call_id = r.get("call_id", f"agg-{int(time.time()*1000)}")
            preview = content[:PREVIEW_CHARS]
            spill_path = self._write_spill(call_id, content)

            replaced = (
                f"[Aggregate spill: {spill_path} "
                f"({len(content)} chars)]\n\n"
                f"Preview:\n{preview}"
            )
            total = total - len(content) + len(replaced)
            self._replacements[call_id] = replaced
            r["content"] = replaced

        return results

    def get_replacement(self, call_id: str) -> Optional[str]:
        """Get cached replacement text for a call_id (cross-turn cache stability)."""
        return self._replacements.get(call_id)

    def _write_spill(self, call_id: str, content: str) -> str:
        """Write spilled content to disk with content-hash filename."""
        h = hashlib.sha256(content.encode()).hexdigest()[:16]
        filename = f"{self.session_id}_{call_id}_{h}.txt"
        path = os.path.join(SPILL_DIR, filename)
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(content)
        return path

    def cleanup(self):
        """Remove all spill files for this session."""
        prefix = f"{self.session_id}_"
        for fname in os.listdir(SPILL_DIR):
            if fname.startswith(prefix):
                try:
                    os.remove(os.path.join(SPILL_DIR, fname))
                except OSError:
                    pass
        self._replacements.clear()

    @staticmethod
    def cleanup_all():
        """Remove ALL spill files (call on shutdown)."""
        if os.path.exists(SPILL_DIR):
            for fname in os.listdir(SPILL_DIR):
                try:
                    os.remove(os.path.join(SPILL_DIR, fname))
                except OSError:
                    pass
