"""Initialize Redis memory layer for academic agent team.

Run once at environment setup (Phase 0).
Validates Redis Stack modules, creates indices, runs smoke test.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from redis import Redis
from agent_memory import AgentMemory
from semantic_cache import SemanticCache


PASS = 0
FAIL = 0


def ok(msg: str):
    global PASS
    PASS += 1
    print(f"  [PASS] {msg}")


def fail(msg: str):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}")


def check_redis_stack():
    r = Redis.from_url("redis://localhost:6379")
    raw = r.execute_command("MODULE LIST")
    modules = set()
    for entry in raw:
        name = entry.get(b"name", entry.get("name"))
        if isinstance(name, bytes):
            name = name.decode()
        modules.add(name)
    required = {"search", "ReJSON", "bf", "timeseries"}
    missing = required - modules
    if missing:
        print(f"ERROR: Missing Redis Stack modules: {missing}")
        sys.exit(1)
    print(f"OK - Redis Stack: {', '.join(sorted(modules))}")
    r.close()


def test_indices():
    mem = AgentMemory()
    cache = SemanticCache()
    mem.r.close()
    cache.r.close()
    ok("Indices created (idx:ltm, idx:session, idx:cache)")


def test_session(mem: AgentMemory):
    eid = mem.add_session_event("smoke-session", {"role": "user", "content": "hello"})
    assert eid
    msgs = mem.get_session_memory("smoke-session")
    assert len(msgs) >= 1 and msgs[0]["content"] == "hello"
    ok(f"Session roundtrip: {len(msgs)} msg(s)")


def test_ltm(mem: AgentMemory):
    mid = mem.create_long_term_memory(
        content="Transformer uses self-attention mechanism",
        topics=["deep-learning", "nlp"],
        owner_id="system",
        memory_type="knowledge",
    )
    assert mid
    ok(f"LTM create: {mid[:12]}")

    results = mem.search_long_term(query="*", topics=["deep-learning"])
    assert len(results) >= 1
    found = any(mid in (r.get("id") or "") for r in results)
    assert found, "LTM record not found"
    ok(f"LTM search by topic: {len(results)} result(s)")


def test_record_review(mem: AgentMemory):
    mid = mem.record_review(
        phase=3, phase_name="experiment",
        reviewer="academic-reviewer", verdict="pass",
        target="experiment-results",
        details={"issues": [], "recommendations": ["add ablation"]},
    )
    assert mid

    results = mem.search_long_term(query="*", topics=["review-audit"], k=5)
    found = any(mid in (r.get("id") or "") for r in results)
    assert found, "review not found"
    ok(f"Review record: {mid[:12]}")


def test_semantic_cache():
    sc = SemanticCache(similarity_threshold=0.5)
    sc.set("What is accuracy?", "95% accuracy")
    r = sc.search("How accurate?")
    assert r is not None
    ok(f"Cache HIT: {r['response']}")
    r2 = sc.search("weather today")
    assert r2 is None
    ok("Cache MISS")
    sc.r.close()


def test_paper_memory(mem: AgentMemory):
    pm = mem.paper
    pm.add_paper(
        slug="test_paper",
        title="Test Paper for Init",
        authors=["Test Author"],
        year=2026,
        content="This is a test paper for initialization.",
        abstract="Test abstract for initialization verification.",
    )
    cnt = pm.count()
    assert cnt >= 1
    ok(f"PaperMemory: {cnt} paper(s)")

    r = pm.search_papers(query="test paper initialization", hybrid=True, k=5)
    assert len(r) >= 1
    ok(f"Paper search (hybrid): {len(r)} result(s)")

    pm.delete_paper("test_paper")
    pm.r.close()


def test_timeseries(mem: AgentMemory):
    mem.record_event("test_metric", 1.0)
    time.sleep(0.01)
    mem.record_event("test_metric", 2.0)
    ts = mem.get_timeseries("test_metric")
    assert len(ts) == 2
    ok(f"Timeseries: {len(ts)} points")


if __name__ == "__main__":
    print("=== Redis Memory Layer Init ===\n")

    check_redis_stack()
    test_indices()

    mem = AgentMemory()
    test_session(mem)
    test_ltm(mem)
    test_record_review(mem)
    test_timeseries(mem)

    test_semantic_cache()
    test_paper_memory(mem)

    mem.r.close()

    total = PASS + FAIL
    print(f"\n=== Results: {PASS}/{total} passed", end="")
    if FAIL > 0:
        print(f", {FAIL} failed ===")
        sys.exit(1)
    else:
        print(" ===")
