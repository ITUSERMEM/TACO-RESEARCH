"""8 tests for SessionCache (route mutex + inject/recall)."""
import pytest, sys, os, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from session_cache import SessionCache


class TestSessionCache:
    def test_lock_unlock_route(self):
        sc = SessionCache()
        route = sc.lock_route("agent:test", timeout=3)
        assert route is not None
        sc.unlock_route("agent:test")
        assert sc.is_active("agent:test") is False

    def test_try_lock_busy(self):
        sc = SessionCache()
        r1 = sc.try_lock_route("agent:busy")
        assert r1 is not None
        r2 = sc.try_lock_route("agent:busy")
        assert r2 is None
        sc.unlock_route("agent:busy")

    def test_inject_and_drain(self):
        sc = SessionCache()
        sc.lock_route("agent:inj")
        msg = sc.inject("agent:inj", "stop experiment")
        assert msg.id is not None
        drained = sc.drain_injects("agent:inj")
        assert len(drained) == 1
        assert drained[0].content == "stop experiment"
        sc.unlock_route("agent:inj")

    def test_retract_inject(self):
        sc = SessionCache()
        sc.lock_route("agent:ret")
        msg = sc.inject("agent:ret", "cancel")
        sc.retract_inject("agent:ret", msg.id)
        drained = sc.drain_injects("agent:ret")
        assert len(drained) == 0
        sc.unlock_route("agent:ret")

    def test_cancel_route(self):
        sc = SessionCache()
        route = sc.lock_route("agent:cancel")
        sc.cancel_route("agent:cancel")
        sc.unlock_route("agent:cancel")

    def test_stats(self):
        sc = SessionCache()
        sc.lock_route("agent:stats")
        stats = sc.stats()
        assert stats["total_routes"] >= 1
        sc.unlock_route("agent:stats")

    def test_concurrent_routes(self):
        sc = SessionCache()
        routes = ["agent:a", "agent:b", "agent:c"]
        for r in routes:
            assert sc.lock_route(r, timeout=3) is not None
        for r in routes:
            sc.unlock_route(r)

    def test_close_all(self):
        sc = SessionCache()
        sc.lock_route("agent:close")
        sc.close_all(timeout=1)
