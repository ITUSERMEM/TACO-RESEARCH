"""SessionCache — Per-route mutex with inject/recall for multi-agent coordination.

Kocoro-inspired SessionCache:
- Per-route entry mutex for exclusive agent run access
- injectCh: buffered channel for mid-run follow-ups
- Retracted/Committed injects ledger to prevent duplicates
- DrainSurvivorsOrCloseInject for race-free teardown
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class InjectedMessage:
    id: str
    content: str
    timestamp: float
    retracted: bool = False
    committed: bool = False


@dataclass
class RouteEntry:
    key: str
    mu: threading.Lock = field(default_factory=threading.Lock)
    inject_ch: list[InjectedMessage] = field(default_factory=list)
    cancel_flag: threading.Event = field(default_factory=threading.Event)
    active: bool = False
    started_at: Optional[float] = None
    draining: bool = False


class SessionCache:
    """Per-route locking and inject/recall system.

    Route key scheme for academic team:
    - agent:<role_name>  — individual agent sessions
    - team:<team_id>     — team coordination
    - phase:<phase_num>  — phase-specific
    - paper:<paper_id>   — paper-specific
    """

    def __init__(self, inject_ledger_ttl_secs: int = 1800, inject_ledger_cap: int = 100):
        self._routes: dict[str, RouteEntry] = {}
        self._lock = threading.Lock()
        self._retracted: dict[str, set[str]] = defaultdict(set)
        self._committed: dict[str, set[str]] = defaultdict(set)
        self._inject_ledger_ttl = inject_ledger_ttl_secs
        self._inject_ledger_cap = inject_ledger_cap

    def get_or_create_route(self, key: str) -> RouteEntry:
        with self._lock:
            if key not in self._routes:
                self._routes[key] = RouteEntry(key=key)
            return self._routes[key]

    def lock_route(self, key: str, timeout: float = 30.0) -> Optional[RouteEntry]:
        entry = self.get_or_create_route(key)
        acquired = entry.mu.acquire(timeout=timeout)
        if not acquired:
            return None

        if entry.cancel_flag.is_set():
            entry.cancel_flag.clear()
            entry.inject_ch.clear()
            entry.draining = False

        entry.active = True
        entry.started_at = time.time()
        return entry

    def try_lock_route(self, key: str) -> Optional[RouteEntry]:
        entry = self.get_or_create_route(key)
        acquired = entry.mu.acquire(blocking=False)
        if not acquired:
            return None
        entry.active = True
        entry.started_at = time.time()
        return entry

    def unlock_route(self, key: str):
        with self._lock:
            entry = self._routes.get(key)
            if entry:
                entry.active = False
                entry.draining = False
                entry.mu.release()

    def inject(self, key: str, content: str) -> InjectedMessage:
        entry = self.get_or_create_route(key)
        msg = InjectedMessage(
            id=f"inj-{len(entry.inject_ch)}-{int(time.time() * 1000)}",
            content=content,
            timestamp=time.time(),
        )
        entry.inject_ch.append(msg)
        return msg

    def drain_injects(self, key: str) -> list[InjectedMessage]:
        entry = self.get_or_create_route(key)
        survivors = []

        for msg in entry.inject_ch[:]:
            if msg.id in self._retracted.get(key, set()):
                entry.inject_ch.remove(msg)
                continue
            if msg.id not in self._committed.get(key, set()):
                survivors.append(msg)
                self._committed[key].add(msg.id)

        return survivors

    def retract_inject(self, key: str, msg_id: str):
        with self._lock:
            self._retracted[key].add(msg_id)
            if len(self._retracted[key]) > self._inject_ledger_cap:
                self._prune_ledger(self._retracted[key])

    def cancel_route(self, key: str):
        entry = self._routes.get(key)
        if entry:
            entry.cancel_flag.set()
            entry.inject_ch.clear()

    def is_active(self, key: str) -> bool:
        entry = self._routes.get(key)
        return entry is not None and entry.active

    def _prune_ledger(self, ledger: set):
        while len(ledger) > self._inject_ledger_cap:
            ledger.pop()

    def close_all(self, timeout: float = 5.0):
        deadline = time.time() + timeout
        for key, entry in list(self._routes.items()):
            entry.cancel_flag.set()
            entry.inject_ch.clear()
            if entry.active:
                wait = max(0, deadline - time.time())
                if wait > 0:
                    time.sleep(min(wait, 1.0))

    def stats(self) -> dict:
        active_routes = sum(1 for r in self._routes.values() if r.active)
        total_injects = sum(len(r.inject_ch) for r in self._routes.values())
        return {
            "total_routes": len(self._routes),
            "active_routes": active_routes,
            "total_injects": total_injects,
            "retracted_count": sum(len(v) for v in self._retracted.values()),
            "committed_count": sum(len(v) for v in self._committed.values()),
        }
