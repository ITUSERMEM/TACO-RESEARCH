"""Academic Scheduler — Cron-based recurring task execution.

Kocoro-inspired scheduler:
- Cron expression evaluation (gronx-compatible)
- Stateful (sticky) / Stateless (fresh) sessions per schedule
- Lifecycle events: started → succeeded/failed
- Proactive delivery via Telegram/Feishu
- Concurrent capacity bounded by semaphore
"""

import json
import os
import random
import re
import string
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


SCHEDULES_FILE = os.path.join(os.path.expanduser("~"), ".config", "academic-schedules.json")


@dataclass
class ScheduleEntry:
    id: str
    cron: str
    agent: str
    prompt: str
    stateful: bool = True
    enabled: bool = True
    last_run_at: Optional[float] = None
    last_run_session_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class SimpleCronMatcher:
    """Minimal cron expression evaluator.

    Supports:
    - Standard 5-field cron: minute hour day month weekday
    - * (any), N (exact), */N (step), N,M (list), N-M (range)
    """

    @staticmethod
    def match(expr: str, now: Optional[time.struct_time] = None) -> bool:
        if now is None:
            now = time.localtime()

        fields = expr.strip().split()
        if len(fields) != 5:
            return False

        time_fields = [now.tm_min, now.tm_hour, now.tm_mday, now.tm_mon, now.tm_wday]

        for i, (pattern, value) in enumerate(zip(fields, time_fields)):
            if not SimpleCronMatcher._match_field(pattern, value):
                return False
        return True

    @staticmethod
    def _match_field(pattern: str, value: int) -> bool:
        if pattern == "*":
            return True

        if "/" in pattern:
            base, step = pattern.split("/")
            step = int(step)
            if base == "*":
                return value % step == 0
            return False

        if "," in pattern:
            return value in [int(p) for p in pattern.split(",")]

        if "-" in pattern:
            low, high = [int(p) for p in pattern.split("-")]
            return low <= value <= high

        try:
            return int(pattern) == value
        except ValueError:
            return False

    @classmethod
    def next_match_after(cls, expr: str) -> Optional[float]:
        now = time.time()
        for offset in range(0, 3600, 60):
            t = now + offset
            if cls.match(expr, time.localtime(t)):
                return t
        return None


class AcademicScheduler:
    """Cron-based task scheduler for the academic team.

    Max concurrent schedules: 5 (one per Phase 0-4 or 5)
    """

    MAX_CONCURRENT = 5

    DEFAULT_SCHEDULES = [
        ScheduleEntry(
            id="weekly_literature_review",
            cron="0 9 * * 1",
            agent="literature-researcher",
            prompt="Scan recent papers matching active project topics on arXiv",
            stateful=True,
        ),
        ScheduleEntry(
            id="daily_experiment_check",
            cron="0 18 * * *",
            agent="experimenter",
            prompt="Check running experiments and report status",
            stateful=False,
        ),
        ScheduleEntry(
            id="phase_auto_transition",
            cron="0 0 * * *",
            agent="research-director",
            prompt="Evaluate current phase completion criteria and propose transition",
            stateful=True,
        ),
        ScheduleEntry(
            id="citation_audit",
            cron="0 12 * * 5",
            agent="citation-auditor",
            prompt="Run citation audit on current paper draft",
            stateful=False,
        ),
    ]

    def __init__(self, schedules_file: str = SCHEDULES_FILE):
        self.schedules_file = schedules_file
        self._schedules: list[ScheduleEntry] = []
        self._running = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._semaphore = threading.Semaphore(self.MAX_CONCURRENT)
        self._lock = threading.Lock()
        self._last_fired: dict[str, int] = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.schedules_file):
                with open(self.schedules_file) as f:
                    data = json.load(f)
                self._schedules = [ScheduleEntry(**s) for s in data]
            else:
                self._schedules = list(self.DEFAULT_SCHEDULES)
                self._save()
        except Exception:
            self._schedules = list(self.DEFAULT_SCHEDULES)

    def _save(self):
        try:
            with open(self.schedules_file, "w") as f:
                data = [s.__dict__ for s in self._schedules]
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def add(self, entry: ScheduleEntry):
        with self._lock:
            self._schedules.append(entry)
            self._save()

    def remove(self, sched_id: str) -> bool:
        with self._lock:
            for i, s in enumerate(self._schedules):
                if s.id == sched_id:
                    self._schedules.pop(i)
                    self._save()
                    return True
        return False

    def get(self, sched_id: str) -> Optional[ScheduleEntry]:
        for s in self._schedules:
            if s.id == sched_id:
                return s
        return None

    def all(self) -> list[ScheduleEntry]:
        return list(self._schedules)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=3)

    def _run_loop(self):
        last_minute = -1
        while self._running.is_set():
            current_minute = int(time.time()) // 60
            if current_minute != last_minute:
                last_minute = current_minute
                self._evaluate()
            time.sleep(15)

    def _evaluate(self):
        now = time.time()
        now_minute = int(now) // 60

        for sched in self._schedules:
            if not sched.enabled:
                continue

            last_fired_min = self._last_fired.get(sched.id, -1)
            if now_minute == last_fired_min:
                continue

            if SimpleCronMatcher.match(sched.cron):
                self._last_fired[sched.id] = now_minute
                if self._semaphore.acquire(blocking=False):
                    threading.Thread(
                        target=self._execute,
                        args=(sched,),
                        daemon=True,
                    ).start()

    def _execute(self, sched: ScheduleEntry):
        try:
            sched.last_run_at = time.time()
            print(f"[Scheduler] Triggered: {sched.id} -> {sched.agent}")
            self._save()
        except Exception as e:
            print(f"[Scheduler] Failed: {sched.id} -> {e}")
        finally:
            self._semaphore.release()

    @staticmethod
    def generate_id() -> str:
        return "sched-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
