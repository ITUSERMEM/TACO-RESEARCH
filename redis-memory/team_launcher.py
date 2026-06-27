#!/usr/bin/env python3
"""Unified launcher for the Academic Team pipeline.

Starts all P1 modules as background services:
- AcademicLoop (daemon mode, Redis pub/sub listener)
- AcademicScheduler (cron-based recurring tasks)
- Heartbeat (periodic health checks)
- AuditLogger (event recording)
- Health HTTP endpoint (port 9333)

Usage:
    python3 team_launcher.py              # Start all services
    python3 team_launcher.py --status     # Check status
    python3 team_launcher.py --stop       # Stop all services
"""

import argparse
import json
import os
import signal
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm_client import DualLLM
from academic_loop import AcademicLoop, Phase
from scheduler import AcademicScheduler
from heartbeat import Heartbeat, HeartbeatConfig
from audit_logger import AuditLogger
from analytics_engine import AnalyticsEngine
from global_lessons import GlobalLessons
from review_calibration import ReviewCalibrator
from trend_monitor import TrendMonitor
from checkpoint_manager import CheckpointManager
from project_manager import ProjectManager
from pool_scheduler import PoolScheduler
from autonomous_orchestrator import AutonomousOrchestrator
from meta_optimizer import MetaOptimizer


HEALTH_PORT = 9333
PID_FILE = "/tmp/academic-team-launcher.pid"
REDIS_URL = "redis://localhost:6379"


class HealthHandler(BaseHTTPRequestHandler):
    """Minimal health endpoint for the launcher."""

    # Class-level reference set by the launcher
    status_provider: Optional[dict] = None

    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"status": "running"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/status" and self.status_provider:
            status = self.status_provider
            if callable(status):
                status = status()
            body = json.dumps(status, indent=2,
                              default=str, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/metrics":
            body = json.dumps({"analytics": "use /status for details"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


class TeamLauncher:
    """Manages lifecycle of all P1 background modules."""

    def __init__(self, redis_url: str = REDIS_URL, project_title: str = "academic-project"):
        self.redis_url = redis_url
        self.project_title = project_title
        self.services: dict[str, any] = {}
        self._httpd: Optional[HTTPServer] = None
        self._status: dict = {}

    def start(self):
        print("[TeamLauncher] Starting all services...")

        llm = DualLLM()
        self.services["llm"] = llm
        print(f"[TeamLauncher] DualLLM: exec={llm.executor.model}, "
              f"review={llm.reviewer.model}, pro={llm.pro.model}")

        # 1. AuditLogger
        audit = AuditLogger()
        self.services["audit"] = audit
        print(f"[TeamLauncher] AuditLogger -> {audit.log_path}")

        # 2. AcademicScheduler
        scheduler = AcademicScheduler()
        scheduler.start()
        self.services["scheduler"] = scheduler
        print(f"[TeamLauncher] Scheduler: {len(scheduler.all())} tasks")

        # 3. Heartbeat
        heartbeat = Heartbeat()
        heartbeat.register(HeartbeatConfig(
            agent="experimenter", interval_secs=1800))
        heartbeat.register(HeartbeatConfig(
            agent="research-director", interval_secs=7200,
            active_hours_start=8, active_hours_end=23))
        heartbeat.start()
        self.services["heartbeat"] = heartbeat
        print(f"[TeamLauncher] Heartbeat: {len(heartbeat.status())} agents")

        # 4. AcademicLoop (daemon mode)
        loop = AcademicLoop(
            redis_url=self.redis_url,
            project_title=self.project_title,
            daemon_mode=True,
        )
        self.services["loop"] = loop
        loop_thread = threading.Thread(
            target=loop.start_daemon, daemon=True)
        loop_thread.start()
        print(f"[TeamLauncher] AcademicLoop daemon (project={loop.project_id})")

        # 5. P2 modules
        self.services["analytics"] = AnalyticsEngine()
        self.services["lessons"] = GlobalLessons()
        self.services["calibrator"] = ReviewCalibrator()
        self.services["trends"] = TrendMonitor()
        print("[TeamLauncher] P2 modules loaded: Analytics, Lessons, Calibrator, Trends")

        # 6. P3-P5 modules
        self.services["checkpoints"] = CheckpointManager()
        self.services["projects"] = ProjectManager()
        self.services["pool"] = PoolScheduler()
        self.services["orchestrator"] = AutonomousOrchestrator()
        self.services["meta"] = MetaOptimizer()
        print("[TeamLauncher] P3-P5 modules loaded: Checkpoints, Projects, Pool, Orchestrator, Meta")

        # 7. Health HTTP server
        self._start_health_server()

        print(f"[TeamLauncher] All services started")
        self._write_pid()

    def stop(self):
        print("[TeamLauncher] Stopping services...")

        loop = self.services.get("loop")
        if loop:
            loop.stop_daemon()

        scheduler = self.services.get("scheduler")
        if scheduler:
            scheduler.stop()

        heartbeat = self.services.get("heartbeat")
        if heartbeat:
            heartbeat.stop()

        if self._httpd:
            self._httpd.shutdown()

        self._remove_pid()
        print("[TeamLauncher] All services stopped")

    @property
    def status(self) -> dict:
        services = {}
        for name, svc in self.services.items():
            if hasattr(svc, "status"):
                try:
                    services[name] = svc.status()
                except Exception:
                    services[name] = "error"
            else:
                services[name] = "running"
        return {
            "services": services,
            "pid": os.getpid(),
        }

    def _start_health_server(self):
        HealthHandler.status_provider = self.status

        self._httpd = HTTPServer(("127.0.0.1", HEALTH_PORT), HealthHandler)
        thread = threading.Thread(target=self._httpd.serve_forever,
                                  daemon=True)
        thread.start()
        print(f"[TeamLauncher] Health endpoint: http://127.0.0.1:{HEALTH_PORT}/health")

    def _write_pid(self):
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))

    @staticmethod
    def _remove_pid():
        try:
            os.remove(PID_FILE)
        except FileNotFoundError:
            pass

    @staticmethod
    def read_pid() -> Optional[int]:
        try:
            with open(PID_FILE) as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return None


def main():
    parser = argparse.ArgumentParser(description="Academic Team Launcher")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--stop", action="store_true", help="Stop services")
    parser.add_argument("--project", default="academic-project", help="Project title")
    parser.add_argument("--output-dir", "-C", default=".",
                        help="Output directory for projects/ figures/ etc. Default: current dir")
    args = parser.parse_args()

    pid = TeamLauncher.read_pid()

    if args.stop:
        if pid:
            os.kill(pid, signal.SIGTERM)
            print(f"[TeamLauncher] Sent stop signal to PID {pid}")
        else:
            print("[TeamLauncher] Not running")
        return

    if args.status:
        if pid:
            print(f"[TeamLauncher] Running (PID {pid})")
            print(json.dumps({"status": "running"}, indent=2))
        else:
            print("[TeamLauncher] Not running")
        return

    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    os.chdir(output_dir)
    print(f"[TeamLauncher] Output directory: {output_dir}")

    launcher = TeamLauncher(project_title=args.project)

    def _signal_handler(signum, frame):
        launcher.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    try:
        launcher.start()
        signal.pause()
    except KeyboardInterrupt:
        launcher.stop()


if __name__ == "__main__":
    main()
