"""Integration tests — real Redis + Phase 0 fast path."""
import pytest, sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REDIS_UP = False
try:
    from redis import Redis
    r = Redis.from_url("redis://localhost:6379", decode_responses=True)
    r.ping()
    REDIS_UP = True
    r.close()
except Exception:
    REDIS_UP = False


@pytest.mark.skipif(not REDIS_UP, reason="Redis required")
class TestIntegration:
    def test_phase_tracker_create(self):
        from academic_loop import AcademicLoop, Phase
        loop = AcademicLoop(redis_url="redis://localhost:6379", project_title="int-test")
        assert loop.tracker.state.get("status") == "idle"
        loop.close()

    def test_phase_tracker_enter_complete(self):
        from academic_loop import AcademicLoop, Phase
        loop = AcademicLoop(redis_url="redis://localhost:6379")
        loop.tracker.phase_enter(Phase.PHASE0)
        assert loop.tracker.state.get("current_phase") == 0
        assert loop.tracker.state.get("status") == "running"
        loop.tracker.phase_complete(Phase.PHASE0)
        assert 0 in loop.tracker.state.get("completed_phases", [])
        loop.close()

    def test_process_incoming_status(self):
        from academic_loop import AcademicLoop
        loop = AcademicLoop(redis_url="redis://localhost:6379")
        result = loop.process_incoming({
            "type": "status_query", "chat_id": "999", "text": "",
        })
        assert result is not None
        assert result.get("type") == "status_response"
        loop.close()

    def test_process_incoming_user_message(self):
        from academic_loop import AcademicLoop
        loop = AcademicLoop(redis_url="redis://localhost:6379")
        result = loop.process_incoming({
            "type": "user_message", "chat_id": "999",
            "text": "测试研究方向",
        })
        assert result is not None
        assert result.get("type") == "pipeline_ack"
        loop.close()

    def test_gate_judge_all_gates(self):
        from gate_judge import GateJudge
        gj = GateJudge()
        for gate_id in range(1, 8):
            result = gj.evaluate(gate_id, f"Gate {gate_id} test transcript")
            assert result.get("verdict") in ("pass", "revise", "fail")

    def test_paper_memory_add_search(self):
        from agent_memory import AgentMemory
        mem = AgentMemory()
        pm = mem.paper
        pm.add_paper(slug="int-test-paper", title="Integration Test Paper",
                     authors=["Tester"], year=2026, venue="TEST",
                     tags=["integration"], content="test", abstract="test abstract")
        results = pm.search_papers(query="integration test", k=5)
        slugs = [r.get("slug") for r in results]
        assert "int-test-paper" in slugs
        pm.delete_paper("int-test-paper")
        mem.r.close()

    def test_skill_exec_resolves_registry(self):
        from skill_executor import SkillExecutor
        ex = SkillExecutor()
        ex._ensure_loaded()
        assert len(ex._role_skills) >= 10

    def test_dual_llm_instantiation(self):
        from llm_client import DualLLM
        llm = DualLLM()
        assert llm.executor.model == "deepseek-v4-flash"
        assert llm.reviewer.model == "glm-5.2"
        assert llm.pro.model == "deepseek-v4-pro"
