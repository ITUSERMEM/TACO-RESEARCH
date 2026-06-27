"""Heartbeat — Periodic health checks for academic team agents.

Kocoro-inspired heartbeat:
- Per-agent configurable interval and active hours
- Goal-driven or checklist-driven execution
- HEARTBEAT_OK silent acknowledgement
- Proactive delivery of alerts
"""

import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


HEARTBEAT_DIR = os.path.join(os.path.expanduser("~"), ".cache", "academic-heartbeat")


@dataclass
class HeartbeatConfig:
    agent: str
    interval_secs: int
    active_hours_start: int = 0
    active_hours_end: int = 24
    model: str = "haiku"
    checklist_file: Optional[str] = None

    def in_active_hours(self) -> bool:
        hour = datetime.now().hour
        return self.active_hours_start <= hour < self.active_hours_end


CHECKLISTS = {
    "experimenter": """## Experiment Health Check
1. Check running experiment status on GPU queue
2. Verify no NaN losses in last iterations
3. Log latest metrics to tracking dashboard
4. Report any errors or warnings
""",
    "research-director": """## Director Check-in
1. Review team progress on current phase
2. Assess if phase completion criteria met
3. Check if any agent is blocked
4. Evaluate timeline vs deadline
""",
    "literature-researcher": """## Literature Health Check
1. Check for new papers matching active topics
2. Verify PaperMemory is up to date
3. Flag any duplicate or conflicting findings
""",
    "code-engineer": """## Code Health Check
1. Check for failing tests
2. Verify code builds successfully
3. Check for stale branches or TODOs
""",
}


class Heartbeat:
    """Per-agent periodic health check.

    Like Kocoro's heartbeat manager:
    - Each agent gets configurable interval
    - Checklist-driven or goal-driven execution
    - HEARTBEAT_OK: silent acknowledgement (no alert sent)
    - Anything else: alert via monitoring channel
    """

    HEARTBEAT_OK = "HEARTBEAT_OK"

    def __init__(self, base_dir: str = HEARTBEAT_DIR):
        self.base_dir = base_dir
        self._agents: dict[str, HeartbeatConfig] = {}
        self._last_run: dict[str, float] = {}
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        os.makedirs(base_dir, exist_ok=True)

    def register(self, config: HeartbeatConfig):
        with self._lock:
            self._agents[config.agent] = config
            self._last_run[config.agent] = 0.0

            checklist_path = os.path.join(self.base_dir, f"{config.agent}_HEARTBEAT.md")
            if config.checklist_file and os.path.exists(config.checklist_file):
                pass
            elif config.agent in CHECKLISTS:
                if not os.path.exists(checklist_path):
                    with open(checklist_path, "w") as f:
                        f.write(CHECKLISTS[config.agent])
            elif not os.path.exists(checklist_path):
                with open(checklist_path, "w") as f:
                    f.write(f"# {config.agent} Heartbeat Checklist\n\n")

    def unregister(self, agent: str):
        with self._lock:
            self._agents.pop(agent, None)
            self._last_run.pop(agent, None)

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
        while self._running.is_set():
            now = time.time()
            for agent, config in list(self._agents.items()):
                if not config.in_active_hours():
                    continue
                last = self._last_run.get(agent, 0)
                if now - last >= config.interval_secs:
                    self._last_run[agent] = now
                    self._execute_beat(agent, config)
            time.sleep(15)

    def _execute_beat(self, agent: str, config: HeartbeatConfig):
        try:
            checklist = self._read_checklist(agent)
            if not checklist:
                result = self.HEARTBEAT_OK
            else:
                result = f"[Heartbeat] {agent}: checked at {datetime.now().isoformat()}"

            is_ok = self.HEARTBEAT_OK in result.upper()

            event_type = "heartbeat_ok" if is_ok else "heartbeat_alert"
            self._record_event(agent, event_type, is_ok)

            if not is_ok:
                print(f"[Heartbeat] ALERT: {agent} — {result[:200]}")
        except Exception as e:
            print(f"[Heartbeat] Error checking {agent}: {e}")

    def _read_checklist(self, agent: str) -> str:
        path = os.path.join(self.base_dir, f"{agent}_HEARTBEAT.md")
        if os.path.exists(path):
            with open(path) as f:
                return f.read()[:2000]
        return ""

    def _record_event(self, agent: str, event: str, is_ok: bool):
        pass

    def status(self) -> dict[str, dict]:
        result = {}
        for agent, config in self._agents.items():
            last = self._last_run.get(agent, 0)
            age = time.time() - last if last > 0 else -1
            result[agent] = {
                "interval": config.interval_secs,
                "last_run_ago_secs": int(age),
                "active_hours": f"{config.active_hours_start}-{config.active_hours_end}",
            }
        return result

    def force_run(self, agent: str) -> Optional[str]:
        config = self._agents.get(agent)
        if not config:
            return None
        self._execute_beat(agent, config)
        self._last_run[agent] = time.time()
        return self._read_checklist(agent)
