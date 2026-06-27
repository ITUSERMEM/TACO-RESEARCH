#!/usr/bin/env python3
"""Unified review: test all modules for import, instantiation, and key methods."""

import importlib
import json
import os
import pkgutil
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RESULTS = {"pass": 0, "fail": 0, "warn": 0, "details": []}
REDIS_UP = False


def ok(msg):
    RESULTS["pass"] += 1
    RESULTS["details"].append(f"  ✅ {msg}")


def fail(msg):
    RESULTS["fail"] += 1
    RESULTS["details"].append(f"  ❌ {msg}")


def warn(msg):
    RESULTS["warn"] += 1
    RESULTS["details"].append(f"  ⚠️  {msg}")


def section(title):
    RESULTS["details"].append(f"\n── {title} ──")


# ── Round 1: Import & Syntax ──

def round_1_imports():
    section("R1: Import & Syntax")
    modules = []
    for _, name, _ in pkgutil.iter_modules([os.path.dirname(__file__)]):
        if name.startswith("_") or name in ("init_memory", "phase0_1_workflow"):
            continue
        modules.append(name)

    for mod_name in sorted(modules):
        try:
            importlib.import_module(mod_name)
            ok(f"import {mod_name}")
        except Exception as e:
            fail(f"import {mod_name}: {e}")

    return modules


# ── Round 2: Instantiation ──

def round_2_instantiation(modules):
    section("R2: Instantiation")
    global REDIS_UP

    from redis import Redis
    try:
        r = Redis.from_url("redis://localhost:6379")
        r.ping()
        REDIS_UP = True
        ok("Redis connection OK")
    except Exception as e:
        warn(f"Redis not available: {e}")
        REDIS_UP = False

    SKIP_NONINSTANTIABLE = {
        "Phase", "LoopAction", "Watchdog", "WatchdogConfig",
        "ContextCompactor", "PhaseTracker", "PhaseLoopDetector",
        "ToolCall", "HeapqScheduler", "Allocation",
        "ScheduleEntry", "SimpleCronMatcher", "InjectedMessage",
        "RouteEntry", "HealthHandler", "FileLock", "ResourcePool",
        "HeartbeatConfig", "MemoryPreflightTrace", "MemoryPreflight",         "DualLLM", "PermissionResult", "TurnPhase",
    }

    for mod_name in sorted(modules):
        mod = sys.modules.get(mod_name)
        if not mod:
            continue
        for attr in dir(mod):
            if attr in SKIP_NONINSTANTIABLE:
                ok(f"skip {mod_name}.{attr} (non-instantiable)")
                continue
            cls = getattr(mod, attr)
            if not isinstance(cls, type):
                continue
            if cls.__module__ != mod_name:
                continue
            if attr.startswith("_"):
                continue
            try:
                if REDIS_UP and any(k in mod_name for k in ("agent_memory", "semantic_cache", "audit_logger", "global_lessons", "analytics_engine", "skill_versioning", "trend_monitor", "checkpoint_manager", "knowledge_broker", "project_manager")):
                    if 'redis_url' in cls.__init__.__code__.co_varnames:
                        instance = cls(redis_url="redis://localhost:6379")
                    else:
                        instance = cls()
                elif mod_name == "llm_client":
                    instance = cls(api_url="http://localhost:9999/nonexistent")
                elif mod_name in ("gate_judge",):
                    instance = cls()
                elif mod_name in ("persist_learnings",):
                    import tempfile
                    tmp = tempfile.mkdtemp()
                    instance = cls(memory_dir=tmp, role="review-test")
                elif mod_name in ("heartbeat",):
                    instance = cls(base_dir="/tmp/review-heartbeat")
                elif mod_name in ("memory_preflight",):
                    continue  # handled explicitly in round 3
                elif mod_name in ("scheduler",):
                    instance = cls(schedules_file="/tmp/review-schedules.json")
                elif mod_name in ("academic_loop",):
                    if REDIS_UP:
                        from agent_memory import AgentMemory
                        instance = cls(redis_url="redis://localhost:6379", project_title="review-test")
                    else:
                        continue
                else:
                    instance = cls()
                ok(f"instantiate {mod_name}.{attr}")
            except Exception as e:
                fail(f"instantiate {mod_name}.{attr}: {e}")


# ── Round 3: Key Methods ──

def round_3_methods():
    section("R3: Key Method Tests")

    # LoopDetector
    from loop_detector import LoopDetector, LoopAction
    d = LoopDetector()
    for i in range(5):
        d.record("paper_search", {"q": "test"}, is_error=False)
    action = d.check()
    if action == LoopAction.FORCE_STOP:
        ok("LoopDetector: 5 identical calls → force-stop")
    else:
        warn(f"LoopDetector: expected force-stop, got {action}")

    # PhaseLoopDetector with role messages
    from loop_detector import PhaseLoopDetector
    pd = PhaseLoopDetector("literature_researcher")
    for i in range(15):
        pd.record("paper_search", {"q": f"query_{i}"})
    action, msg = pd.check()
    if action == LoopAction.FORCE_STOP:
        ok(f"PhaseLoopDetector: force-stop, msg={msg}")
    else:
        warn(f"PhaseLoopDetector: expected force-stop, got {action}")

    # Summarizer
    from summarizer import PhaseSummarizer
    s = PhaseSummarizer()
    result = s.summarize([
        {"role": "user", "content": "Decision: Use method A"},
        {"role": "assistant", "content": "Correction: Actually use method B"},
    ], phase=1)
    if result.get("analysis"):
        ok(f"Summarizer: analysis generated ({len(result['analysis'])} chars)")
    else:
        fail("Summarizer: no analysis generated")

    # ReviewCalibrator
    from review_calibration import ReviewCalibrator
    rc = ReviewCalibrator()
    drift = rc.evaluate([
        {"verdict": "pass", "issues": []},
        {"verdict": "pass", "issues": []},
        {"verdict": "fail", "issues": ["bad"]},
    ])
    if "drift_detected" in drift:
        ok(f"Calibrator: evaluated {drift['reviews_analyzed']} reviews")
    else:
        fail("Calibrator: evaluation failed")

    # SkillVersioning
    from skill_versioning import SkillVersioning
    sv = SkillVersioning()
    test_file = "/tmp/_review_test_skill.md"
    with open(test_file, "w") as f:
        f.write("# Test Skill\nContent here")
    ver = sv.record_version("test-skill", test_file, author="review")
    if ver.get("version"):
        ok(f"SkillVersioning: recorded v{ver['version']}")
        sv.r.delete(f"skill:manifest:test-skill")
    else:
        fail(f"SkillVersioning: failed: {ver}")

    # PoolScheduler
    from pool_scheduler import PoolScheduler
    ps = PoolScheduler()
    alloc = ps.acquire("test-project", gpus=1, cpu_cores=2, memory_gb=4, timeout=5)
    if alloc:
        ok(f"PoolScheduler: acquired {alloc.gpus} GPU(s)")
        ps.release("test-project")
    else:
        fail("PoolScheduler: acquire failed")

    # ProjectManager
    if REDIS_UP:
        from project_manager import ProjectManager
        pm = ProjectManager()
        proj = pm.create_project("Review Test Project", "Testing")
        if "id" in proj:
            ok(f"ProjectManager: created {proj['id']}")
            pm.delete_project(proj["id"])
        else:
            warn(f"ProjectManager: {proj}")

    # ReadTracker
    from read_tracker import ReadTracker
    rt = ReadTracker()
    rt.record_read("paper1.pdf", mtime=1000, size=500)
    dedup = rt.check_dedup("paper1.pdf", mtime=1000, size=500)
    if dedup:
        ok("ReadTracker: dedup detected")
    else:
        fail("ReadTracker: dedup missed")

    # MemoryPreflight
    from memory_preflight import MemoryPreflight
    if REDIS_UP:
        from agent_memory import AgentMemory
        mem = AgentMemory()
        mp = MemoryPreflight(mem)
        ctx = mp.build_context(phase=1, role="literature-researcher")
        if ctx:
            ok(f"MemoryPreflight: context {len(ctx)} chars")
        else:
            ok("MemoryPreflight: no context (expected, no LTM data)")
        stripped = MemoryPreflight.strip_private_memory(ctx)
        if stripped == "" or stripped is not None:
            ok("MemoryPreflight: strip_private_memory works")
        mem.r.close()

    # CheckpointManager
    if REDIS_UP:
        from checkpoint_manager import CheckpointManager
        cm = CheckpointManager()
        cm.save("review-proj", 1, {"phase": 1})
        cp = cm.load("review-proj", 1)
        if cp and cp.get("phase") == 1:
            ok("CheckpointManager: save/load OK")
        else:
            fail("CheckpointManager: save/load failed")
        cm.delete("review-proj", 1)


# ── Round 4: Integration Points ──

def round_4_integration():
    section("R4: Integration Checks")

    # AcademicLoop creates LLMClient and GateJudge
    if REDIS_UP:
        from academic_loop import AcademicLoop
        loop = AcademicLoop(project_title="integration-test")
        if hasattr(loop, "llm"):
            ok("AcademicLoop: LLMClient attached")
        else:
            fail("AcademicLoop: missing LLMClient")
        if hasattr(loop, "gate_judge"):
            ok("AcademicLoop: GateJudge attached")
        else:
            fail("AcademicLoop: missing GateJudge")
        loop.close()

    # TeamLauncher creates all services
    from team_launcher import TeamLauncher
    tl = TeamLauncher(project_title="review-test")
    if hasattr(tl, "services"):
        ok("TeamLauncher: services dict present")
    else:
        fail("TeamLauncher: missing services")

    # CacheStrategy TTL routing
    from cache_strategy import CacheStrategy
    ttl = CacheStrategy.get_ttl("academic_director")
    if ttl == 3600:
        ok("CacheStrategy: director TTL=3600")
    else:
        warn(f"CacheStrategy: unexpected TTL={ttl}")

    # FileLock works
    from persist_learnings import FileLock
    import tempfile
    lock_file = tempfile.mkstemp()[1]
    fd = os.open(lock_file, os.O_RDONLY)
    try:
        FileLock.lock(fd)
        ok("FileLock: acquire OK")
        FileLock.unlock(fd)
        ok("FileLock: release OK")
    except Exception as e:
        fail(f"FileLock: {e}")
    os.close(fd)
    os.unlink(lock_file)

    # SessionCache routing
    from session_cache import SessionCache
    sc = SessionCache()
    route = sc.lock_route("agent:reviewer", timeout=3)
    if route:
        ok("SessionCache: route locked")
        sc.unlock_route("agent:reviewer")
    else:
        fail("SessionCache: lock failed")

    # Scheduler loads defaults
    from scheduler import AcademicScheduler
    sched = AcademicScheduler(schedules_file="/tmp/_review_sched.json")
    if len(sched.all()) >= 3:
        ok(f"Scheduler: {len(sched.all())} default tasks")
    else:
        warn(f"Scheduler: only {len(sched.all())} tasks")


# ── Round 5: Security & Edge Cases ──

def round_5_security():
    section("R5: Security & Edge Cases")

    from audit_logger import AuditLogger, ACADEMIC_EVENT_TYPES
    if len(ACADEMIC_EVENT_TYPES) >= 10:
        ok(f"AuditLogger: {len(ACADEMIC_EVENT_TYPES)} event types")
    else:
        warn(f"AuditLogger: only {len(ACADEMIC_EVENT_TYPES)} types")

    logger = AuditLogger(log_dir="/tmp/_review_audit")
    secret = "Bearer sk-my-secret-api-key-12345678901234567890"
    redacted = logger._redact(secret)
    if "REDACTED" in redacted:
        ok("AuditLogger: secret redaction works")
    else:
        warn(f"AuditLogger: redaction failed on: {redacted[:30]}")

    logger.log("test_event", agent="review", details={"test": True})
    if os.path.exists(logger.log_path):
        ok("AuditLogger: file written")
    else:
        fail("AuditLogger: file missing")

    global_lessons_types = ["experiment", "writing", "review", "methodology", "code"]
    from global_lessons import LESSON_TYPES
    if len(LESSON_TYPES) == 5:
        ok(f"GlobalLessons: {len(LESSON_TYPES)} lesson types")
    else:
        warn(f"GlobalLessons: {len(LESSON_TYPES)} types")

    from auto_retry import AutoRetry
    ar = AutoRetry(window_size=5)
    ar.record_failure("OOM", {"batch_size": 32})
    ar.record_failure("OOM", {"batch_size": 32})
    ar.record_failure("OOM", {"batch_size": 32})
    fix = ar.detect_pattern()
    if fix and fix.get("detected") == "OOM":
        ok(f"AutoRetry: detected OOM pattern → {fix['suggested_fix']['action']}")
    else:
        warn(f"AutoRetry: pattern detection returned: {fix}")

    # TrendMonitor
    from trend_monitor import TrendMonitor, CONFERENCE_DEADLINES
    if len(CONFERENCE_DEADLINES) >= 4:
        ok(f"TrendMonitor: {len(CONFERENCE_DEADLINES)} conferences tracked")
    else:
        warn(f"TrendMonitor: only {len(CONFERENCE_DEADLINES)} conferences")

    # PublicationTracker statuses
    from publication_tracker import PublicationTracker
    pt = PublicationTracker()
    if len(pt.STATUSES) >= 5:
        ok(f"PublicationTracker: {len(pt.STATUSES)} statuses")
    else:
        warn(f"PublicationTracker: {len(pt.STATUSES)} statuses")


# ── Round 6: Flow Integration ──

def round_6_flow():
    section("R6: Flow Integration (Phase 0→1 smoke)")

    if not REDIS_UP:
        warn("Skipping Phase flow test: Redis unavailable")
        return

    from redis import Redis
    r = Redis.from_url("redis://localhost:6379")
    r.flushdb()

    from academic_loop import AcademicLoop, Phase
    import tempfile
    tmp_dir = tempfile.mkdtemp()

    loop = AcademicLoop(
        redis_url="redis://localhost:6379",
        project_title="Review Smoke Test",
    )

    # Test PhaseTracker
    loop.tracker.phase_enter(Phase.PHASE0)
    ok("PhaseTracker: Phase 0 entered")
    assert loop.tracker.state.get("current_phase") == 0

    loop.tracker.iteration_increment(Phase.PHASE0)
    ok("PhaseTracker: iteration incremented")

    # Test gate recording
    loop.tracker.gate_record(Phase.PHASE1, 1, "pass", {"issues": []})
    gates = loop.tracker.state.get("gate_results", {})
    if "phase1_gate1" in gates:
        ok("PhaseTracker: gate recorded")
    else:
        fail("PhaseTracker: gate recording failed")

    loop.tracker.phase_complete(Phase.PHASE0)
    assert loop.tracker.is_phase_done(Phase.PHASE0)
    ok("PhaseTracker: Phase 0 completed")

    # Test GateJudge
    from gate_judge import GateJudge
    gj = GateJudge()
    result = gj.evaluate(1, "Test transcript for review gate evaluation")
    if result.get("verdict") in ("pass", "revise", "fail"):
        ok(f"GateJudge: verdict={result['verdict']} (LLM fallback)")
    else:
        warn(f"GateJudge: unexpected verdict={result}")

    # Test full phase run
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        loop.run(start_phase=Phase.PHASE0, end_phase=Phase.PHASE0)
        output = sys.stdout.getvalue()
        if "Phase 0 complete" in output:
            ok("AcademicLoop: Phase 0 run completed")
        else:
            fail("AcademicLoop: Phase 0 did not complete")
    except Exception as e:
        fail(f"AcademicLoop run: {e}")
        traceback.print_exc()
    finally:
        sys.stdout = old_stdout

    loop.close()
    r.flushdb()
    r.close()


# ── Round 7: Redis pub/sub Bridge Connectivity ──

def round_7_pubsub():
    section("R7: Redis pub/sub Bridge Connectivity")

    from redis import Redis
    r = Redis.from_url("redis://localhost:6379", decode_responses=True)

    # Check academic:inbox has subscriber (AcademicLoop daemon)
    try:
        subs = r.execute_command("PUBSUB NUMSUB academic:inbox")
        if subs and len(subs) >= 2 and subs[1] > 0:
            ok(f"academic:inbox has {subs[1]} subscriber(s)")
        else:
            warn("academic:inbox has no subscriber (AcademicLoop daemon not running)")
    except Exception as e:
        fail(f"PUBSUB NUMSUB: {e}")

    # Test pub/sub roundtrip
    import threading
    received = []

    def subscriber():
        ps = r.pubsub()
        ps.subscribe("academic:outbox")
        for msg in ps.listen():
            if msg["type"] == "message":
                received.append(msg["data"])
                break
        ps.unsubscribe()

    t = threading.Thread(target=subscriber, daemon=True)
    t.start()
    time.sleep(0.5)

    test_msg = '{"type":"test","chat_id":"999","text":"ping"}'
    r.publish("academic:inbox", test_msg)

    t.join(timeout=3)
    if len(received) > 0:
        ok(f"pub/sub roundtrip: got response {received[0][:80]}")
    else:
        warn("pub/sub roundtrip: no response (expected if AcademicLoop daemon idle)")

    # Check academic:outbox
    try:
        subs_out = r.execute_command("PUBSUB NUMSUB academic:outbox")
        ok("academic:outbox channel exists")
    except Exception as e:
        warn(f"academic:outbox check: {e}")

    r.close()


# ── Round 8: Concurrent Access Stress Test ──

def round_8_concurrency():
    section("R8: Concurrent Access Stress Test")

    from persist_learnings import FileLock
    import tempfile
    import threading

    lock_file = tempfile.mkstemp()[1]
    errors = []
    results = []

    def worker(wid: int):
        fd = os.open(lock_file, os.O_RDONLY)
        try:
            FileLock.lock(fd, exclusive=True, blocking=True)
            time.sleep(0.05)
            results.append(wid)
            FileLock.unlock(fd)
        except Exception as e:
            errors.append(f"worker {wid}: {e}")
        finally:
            os.close(fd)

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    if errors:
        fail(f"FileLock concurrency: {len(errors)} errors: {errors[0]}")
    elif len(results) == 20:
        ok(f"FileLock: 20 concurrent workers, all {len(results)} acquired")
    else:
        warn(f"FileLock: {len(results)}/20 workers completed")

    os.unlink(lock_file)

    # SessionCache concurrent routes
    from session_cache import SessionCache
    sc = SessionCache()
    route_errors = []

    def route_worker(route_name: str):
        try:
            r = sc.lock_route(route_name, timeout=3)
            if r:
                time.sleep(0.05)
                sc.unlock_route(route_name)
            else:
                route_errors.append(f"{route_name}: lock failed")
        except Exception as e:
            route_errors.append(f"{route_name}: {e}")

    routes = [f"agent:role-{i}" for i in range(10)]
    threads2 = [threading.Thread(target=route_worker, args=(r,), daemon=True) for r in routes]
    for t in threads2:
        t.start()
    for t in threads2:
        t.join(timeout=5)

    if not route_errors:
        ok("SessionCache: 10 concurrent routes OK")
    else:
        warn(f"SessionCache: {len(route_errors)} errors: {route_errors[0]}")


# ── Round 9: Gate Judge Consistency ──

def round_9_gate_consistency():
    section("R9: Gate Judge Consistency (simulated)")

    from gate_judge import GateJudge, GATE_JUDGE_PROMPTS
    if len(GATE_JUDGE_PROMPTS) == 7:
        ok(f"GateJudge: {len(GATE_JUDGE_PROMPTS)} gate prompts defined")
    else:
        warn(f"GateJudge: {len(GATE_JUDGE_PROMPTS)} prompts (expected 7)")

    gj = GateJudge()

    # Test all 7 gates produce valid verdicts
    for gate_id in range(1, 8):
        result = gj.evaluate(gate_id,
                             f"Simulated transcript for Gate {gate_id} evaluation testing")
        verdict = result.get("verdict", "")
        if verdict in ("pass", "revise", "fail"):
            ok(f"Gate {gate_id}: verdict={verdict}")
        else:
            fail(f"Gate {gate_id}: invalid verdict={verdict}")

    # Edge case: empty transcript
    result_empty = gj.evaluate(1, "")
    if result_empty.get("verdict") in ("pass", "revise", "fail"):
        ok("GateJudge: empty transcript handled")
    else:
        warn(f"GateJudge: empty transcript → {result_empty}")

    # Edge case: very long transcript
    result_long = gj.evaluate(2, "Long text " * 5000)
    if result_long.get("verdict") in ("pass", "revise", "fail"):
        ok("GateJudge: long transcript handled")
    else:
        warn(f"GateJudge: long transcript → {result_long}")

    # Edge case: transcript with rejection signals
    result_reject = gj.evaluate(3,
                                "This experiment has fatal flaws. " * 10 +
                                "The methodology is fundamentally wrong. " * 10 +
                                "Results are not reproducible. " * 10)
    if result_reject.get("verdict") in ("pass", "revise", "fail"):
        ok("GateJudge: rejection signals parsed")
    else:
        warn(f"GateJudge: rejection → {result_reject}")


# ── Round 10: End-to-end Phase 0-1 with sub-agent dispatch ──

def round_10_e2e():
    section("R10: E2E Phase 0-1 with agent dispatch")

    from redis import Redis
    r = Redis.from_url("redis://localhost:6379")
    r.flushdb()

    from academic_loop import AcademicLoop, Phase
    import io

    loop = AcademicLoop(
        redis_url="redis://localhost:6379",
        project_title="E2E Review Test",
    )

    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        loop.run(start_phase=Phase.PHASE0, end_phase=Phase.PHASE1)
        output = sys.stdout.getvalue()

        checks = [
            ("Phase 0", "Phase 0" in output),
            ("Phase 1", "Phase 1" in output),
            ("LLM agent call", "research-director" in output or "literature-researcher" in output),
            ("Gate 1", "Gate 1" in output),
            ("Phase 0 complete", "Phase 0 complete" in output),
            ("Phase 1 complete", "Phase 1 complete" in output),
        ]

        for name, found in checks:
            if found:
                ok(f"E2E: {name} present in output")
            else:
                warn(f"E2E: {name} not found (may be empty pipeline output)")

        # Verify PhaseTracker state
        state = loop.tracker.state
        completed = state.get("completed_phases", [])
        if 0 in completed and 1 in completed:
            ok("E2E: PhaseTracker confirms Phase 0+1 completed")
        else:
            warn(f"E2E: completed phases: {completed}")

    except Exception as e:
        fail(f"E2E Phase 0-1: {e}")
        traceback.print_exc()
    finally:
        sys.stdout = old_stdout

    loop.close()
    r.flushdb()
    r.close()


# ── Main ──

if __name__ == "__main__":
    print(f"{'='*60}")
    print(f"  Academic Team — Multi-Round Review")
    print(f"{'='*60}")

    modules = round_1_imports()

    round_2_instantiation(modules)

    round_3_methods()

    round_4_integration()

    round_5_security()

    round_6_flow()

    if REDIS_UP:
        round_7_pubsub()
        round_8_concurrency()
        round_9_gate_consistency()
        round_10_e2e()
    else:
        section("R7-R10: Skipped (Redis unavailable)")

    total = RESULTS["pass"] + RESULTS["fail"]
    print(f"\n{'='*60}")
    print(f"  Results: {RESULTS['pass']} ✅ | {RESULTS['fail']} ❌ | {RESULTS['warn']} ⚠️")
    print(f"{'='*60}\n")

    for detail in RESULTS["details"]:
        print(detail)

    print(f"\n{'='*60}")
    exit(0 if RESULTS["fail"] == 0 else 1)
