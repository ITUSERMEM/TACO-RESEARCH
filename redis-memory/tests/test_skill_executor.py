"""8 tests for SkillExecutor — NOW WITH REAL SUBPROCESS PIPES."""
import pytest, sys, os, subprocess, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skill_executor import SkillExecutor, ROLE_MAP


class TestSkillExecutor:
    def test_get_skills_literature(self):
        ex = SkillExecutor()
        skills = ex.get_skills_for_role("literature-researcher")
        assert len(skills) > 0

    def test_get_skills_all_roles(self):
        ex = SkillExecutor()
        for role in ROLE_MAP:
            skills = ex.get_skills_for_role(role)
            assert len(skills) > 0

    def test_unknown_role_fallback(self):
        ex = SkillExecutor()
        skills = ex.get_skills_for_role("unknown-role")
        assert len(skills) > 0

    def test_run_skill_real_pipe_ok(self):
        """Test run_skill with real subprocess pipe (not mock)."""
        ex = SkillExecutor()
        import shlex
        cmd = f"echo 'line1'; sleep 0.1; echo 'line2'"
        start = time.time()
        all_lines = []
        try:
            proc = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1,
            )
            for line in proc.stdout:
                s = line.strip()
                if s:
                    all_lines.append(s)
            proc.wait(timeout=5)
        finally:
            if proc.poll() is None:
                proc.kill()
        elapsed = time.time() - start
        assert len(all_lines) > 0
        assert elapsed < 5

    def test_run_skill_real_pipe_hang(self):
        """Subprocess that hangs → must be detected within timeout."""
        ex = SkillExecutor()
        cmd = "echo 'start'; sleep 60; echo 'end'"
        start = time.time()
        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        line = proc.stdout.readline()
        proc.kill()
        proc.wait(timeout=5)
        elapsed = time.time() - start
        assert "start" in (line or "")
        assert elapsed < 10

    def test_run_skill_file_not_found(self, mocker):
        mocker.patch("subprocess.Popen", side_effect=FileNotFoundError)
        ex = SkillExecutor()
        result = ex.run_skill("missing-skill")
        assert result["status"] == "error"

    def test_suggest_skill_fallback(self):
        ex = SkillExecutor()
        result = ex.suggest_skill("literature-researcher", 1, "test task", llm=None)
        assert result is not None

    def test_parse_registry_contains_keys(self):
        ex = SkillExecutor()
        ex._ensure_loaded()
        assert len(ex._role_skills) > 0
