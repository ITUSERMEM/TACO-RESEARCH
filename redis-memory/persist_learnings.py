"""PersistLearnings + BoundedAppend + ConsolidateMemory.

Kocoro-inspired memory pipeline that extracts durable knowledge from
Phase conversations, appends to role-specific MEMORY.md files, and
periodically consolidates to prevent unbounded growth.

Usage:
    pl = PersistLearnings(memory_dir="/tmp/academic_memory", role="experimenter")
    pl.extract_and_persist(messages)
    pl.consolidate_if_needed()
"""

import hashlib
import json
import os
import time
import fcntl
from datetime import datetime, timezone
from typing import Optional


MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".cache", "academic-memory")


class FileLock:
    """Cross-platform advisory file lock (flock on Linux/macOS)."""

    @staticmethod
    def lock(fd, exclusive: bool = True, blocking: bool = True):
        flags = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        if not blocking:
            flags |= fcntl.LOCK_NB
        while True:
            try:
                fcntl.flock(fd, flags)
                return
            except InterruptedError:
                continue

    @staticmethod
    def unlock(fd):
        fcntl.flock(fd, fcntl.LOCK_UN)

    @staticmethod
    def try_lock(fd, exclusive: bool = True) -> bool:
        flags = fcntl.LOCK_EX | fcntl.LOCK_NB if exclusive else fcntl.LOCK_SH | fcntl.LOCK_NB
        try:
            fcntl.flock(fd, flags)
            return True
        except BlockingIOError:
            return False


class PersistLearnings:
    """Extract durable knowledge from conversation and persist to MEMORY.md.

    Kocoro's two-phase pipeline:
    Phase 1: Compile conversation transcript (capped at 540K chars)
    Phase 2: Extract learnings with small model → append to MEMORY.md
    """

    MAX_MEMORY_LINES = 150
    GC_THRESHOLD = 12
    GC_COOLDOWN_SECS = 7 * 24 * 3600  # 7 days
    SUMMARY_CAP_CHARS = 540_000

    def __init__(self, memory_dir: str = MEMORY_DIR, role: str = "default", llm=None):
        self.memory_dir = os.path.join(memory_dir, role)
        self.role = role
        self.memory_path = os.path.join(self.memory_dir, "MEMORY.md")
        self.lock_path = os.path.join(self.memory_dir, "MEMORY.md.lock")
        self.llm = llm
        os.makedirs(self.memory_dir, exist_ok=True)
        self._ensure_memory_file()

    def _ensure_memory_file(self):
        if not os.path.exists(self.memory_path):
            with open(self.memory_path, "w") as f:
                f.write(f"# {self.role} Memory\n\n")
                f.write(f"Auto-persisted knowledge for {self.role} role.\n")
                f.write(f"Created: {datetime.now(timezone.utc).isoformat()}\n\n")

    def read_memory(self) -> str:
        with open(self.memory_path) as f:
            return f.read()

    def extract_and_persist(
        self,
        messages: list[dict],
        source: str = "conversation",
    ) -> int:
        """Extract learnings from messages and append to MEMORY.md.

        Returns number of lines appended.
        """
        learnings = self._extract_learnings(messages)
        if not learnings:
            return 0

        lines = []
        header = f"\n## Auto-persisted ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}) [{source}]\n"
        lines.append(header)
        for item in learnings:
            lines.append(f"- {item}")

        appended = self._bounded_append(lines)
        return appended

    def _extract_learnings(self, messages: list[dict]) -> list[str]:
        learnings: list[str] = []
        seen = set()

        existing = self.read_memory()
        existing_lower = existing.lower()

        if self.llm:  # reviewer-tier LLM (glm-5.2) for cheap extraction
            transcript = []
            for msg in messages[-10:]:
                content = msg.get("content", "")
                if isinstance(content, str) and len(content) > 20:
                    transcript.append(f"[{msg.get('role', '?')}]: {content[:500]}")
            if transcript:
                prompt = (
                    "Extract key facts worth remembering from this conversation. "
                    "Return as a numbered list, one fact per line, max 150 chars each.\n"
                    f"<conversation>\n{chr(10).join(transcript)}\n</conversation>"
                )
                response = self.llm.complete([
                    {"role": "system", "content": "Extract durable knowledge only. Skip transient chat."},
                    {"role": "user", "content": prompt},
                ], max_tokens=800, temperature=0.2)
                for line in response.split("\n"):
                    line = line.strip().lstrip("1234567890.)- ")
                    if line and len(line) > 10 and line != "NONE":
                        sig = hashlib.md5(line.encode()).hexdigest()[:16]
                        if sig not in seen and sig not in existing_lower:
                            seen.add(sig)
                            learnings.append(line[:150])
                return learnings

        for msg in messages[-20:]:
            content = msg.get("content", "")
            if not isinstance(content, str) or len(content) < 20:
                continue
            content = content[:2000]
            if any(t in content.lower() for t in {"=== start ===", "heartbeat_ok", "---"}):
                continue
            sig = hashlib.md5(content.encode()).hexdigest()[:16]
            if sig in seen:
                continue
            seen.add(sig)
            if sig not in existing_lower:
                summary = self._summarize_fact(content)
                if summary and summary != "NONE":
                    learnings.append(summary[:150])

        return learnings

    @staticmethod
    def _summarize_fact(content: str) -> Optional[str]:
        if len(content) > 500:
            content = content[:500] + "..."

        content_lower = content.lower()
        if any(t in content_lower for t in {"step 1", "first,", "second,", "finally,"}):
            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if line and len(line) < 200:
                    return line
            return content[:150]

        important_markers = ["key finding:", "conclusion:", "important:",
                             "note:", "remember:", "decision:"]
        for marker in important_markers:
            if marker in content_lower:
                idx = content_lower.index(marker)
                return content[idx:idx + 150]

        return content[:150]

    def _bounded_append(self, new_lines: list[str]) -> int:
        """Atomically append lines to MEMORY.md, respecting max line limit."""
        if not os.path.exists(self.lock_path):
            with open(self.lock_path, "w") as _f:
                _f.write("")
        fd = os.open(self.lock_path, os.O_RDONLY)
        try:
            FileLock.lock(fd, exclusive=True, blocking=True)
            with open(self.memory_path) as f:
                current_lines = f.readlines()

            total_lines = len(current_lines) + len(new_lines)

            if total_lines <= self.MAX_MEMORY_LINES:
                with open(self.memory_path, "a") as f:
                    for line in new_lines:
                        f.write(line + "\n")
                return len(new_lines)

            overflow = total_lines - self.MAX_MEMORY_LINES
            detail = self._write_detail_file(current_lines, new_lines, overflow)
            kept_new = new_lines[:len(new_lines) - overflow] if overflow < len(new_lines) else []

            with open(self.memory_path, "w") as f:
                for line in current_lines:
                    f.write(line)
                if kept_new:
                    for line in kept_new:
                        f.write(line + "\n")
                f.write(f"\n*See `{detail}` for overflow details*\n")
            return len(kept_new)
        finally:
            try:
                FileLock.unlock(fd)
            except Exception:
                pass
            os.close(fd)

    def _write_detail_file(
        self,
        existing: list[str],
        new_lines: list[str],
        overflow_count: int,
    ) -> str:
        ts = datetime.now().strftime("%Y-%m-%d")
        rand = hashlib.md5(os.urandom(8)).hexdigest()[:6]
        filename = f"auto-{ts}-{rand}.md"
        path = os.path.join(self.memory_dir, filename)

        overflow_lines = new_lines[-overflow_count:] if overflow_count <= len(new_lines) else new_lines
        with open(path, "w") as f:
            f.write(f"# Overflow from {ts}\n\n")
            for line in overflow_lines:
                f.write(line + "\n")

        return filename

    # ── ConsolidateMemory ────────────────────────────────────

    def consolidate_if_needed(self) -> bool:
        """Run GC if threshold met and cooldown has passed.

        Returns True if consolidation was performed.
        """
        detail_files = sorted([
            f for f in os.listdir(self.memory_dir)
            if f.startswith("auto-") and f.endswith(".md")
        ])

        if len(detail_files) < self.GC_THRESHOLD:
            return False

        gc_marker = os.path.join(self.memory_dir, ".memory_gc")
        if os.path.exists(gc_marker):
            mtime = os.path.getmtime(gc_marker)
            if time.time() - mtime < self.GC_COOLDOWN_SECS:
                return False

        self._consolidate(detail_files)
        with open(gc_marker, "w") as f:
            f.write(datetime.now(timezone.utc).isoformat())
        return True

    def _consolidate(self, detail_files: list[str]):
        """Merge all auto-*.md files into MEMORY.md."""
        all_lines: list[str] = []
        for filename in detail_files:
            path = os.path.join(self.memory_dir, filename)
            with open(path) as f:
                content = f.read().strip()
                if content and not content.startswith("# Overflow"):
                    for line in content.split("\n"):
                        line = line.strip()
                        if line and not line.startswith("#") and line not in all_lines:
                            all_lines.append(line)

        if not os.path.exists(self.lock_path):
            with open(self.lock_path, "w") as _f:
                _f.write("")
        fd = os.open(self.lock_path, os.O_RDONLY)
        try:
            FileLock.lock(fd, exclusive=True, blocking=True)
            consolidated = "\n".join(all_lines)

            with open(self.memory_path, "a") as f:
                f.write(f"\n## Consolidated ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n")
                f.write(consolidated + "\n")

            for filename in detail_files:
                os.remove(os.path.join(self.memory_dir, filename))

            print(f"[Consolidate] Merged {len(detail_files)} files, {len(all_lines)} lines")
        finally:
            try:
                FileLock.unlock(fd)
            except Exception:
                pass
            os.close(fd)

    def get_line_count(self) -> int:
        with open(self.memory_path) as f:
            return len(f.readlines())

    def clear(self):
        if os.path.exists(self.memory_path):
            os.remove(self.memory_path)
        self._ensure_memory_file()
        for f in os.listdir(self.memory_dir):
            if f.startswith("auto-") and f.endswith(".md"):
                os.remove(os.path.join(self.memory_dir, f))


# ── Quick Test ───────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        pl = PersistLearnings(memory_dir=tmp, role="test")

        msgs = [
            {"role": "assistant", "content": "Key finding: The transformer outperforms CNN by 5%."},
            {"role": "assistant", "content": "Decision: Use AdamW optimizer with lr=3e-4."},
            {"role": "assistant", "content": "This is a trivial update message === START ==="},
        ]
        n = pl.extract_and_persist(msgs, source="test")
        print(f"Appended: {n} lines")
        print(pl.read_memory()[:200])
        print(f"Lines: {pl.get_line_count()}")
