"""SkillExecutor — Call opencode skills from agent iteration loop.

Parses agent-registry.md for role→skill mappings.
Executes skills via `opencode run /skill_name args` subprocess.

Usage:
    executor = SkillExecutor(redis_client=redis, contract=contract, audit_logger=audit)
    skills = executor.get_skills_for_role("literature-researcher")
    result = executor.run_skill("research-lit", task, phase=1, agent_role="literature-researcher")
"""

import json
import os
import re
import select
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Optional

REGISTRY_PATH = os.path.expanduser(
    "~/.claude/skills/agent-team/references/agent-registry.md"
)
ROLE_MAP = {
    "research-director": "研究项目总监",
    "academic-editor": "学术编辑",
    "literature-researcher": "文献研究员",
    "methodologist": "方法论研究员",
    "method-reviewer": "方法评审员",
    "experimenter": "实验工程师",
    "scientific-computing-engineer": "科学计算工程师",
    "code-engineer": "代码工程师",
    "paper-writer": "论文写手",
    "visualization-designer": "可视化设计师",
    "academic-reviewer": "学术评审员",
    "citation-auditor": "引用审计员",
}

SKILL_TIMEOUT = 120


class SkillExecutor:
    """Read agent-registry.md and execute skills via subprocess."""

    def __init__(self, redis_client=None, contract=None, audit_logger=None):
        self._role_skills: dict[str, list[str]] = {}
        self._registry_loaded = False
        self.r = redis_client
        self.contract = contract
        self.audit = audit_logger

        if redis_client:
            from skill_contract_config import ContractConfig
            self.contract_config = ContractConfig(redis_client)
        else:
            self.contract_config = None

    def get_skills_for_role(self, role: str) -> list[str]:
        """Get the list of skill commands for a given agent role."""
        self._ensure_loaded()
        cn = ROLE_MAP.get(role, "")
        if cn in self._role_skills:
            return self._role_skills[cn]
        all_skills = set()
        for skills in self._role_skills.values():
            all_skills.update(skills)
        return sorted(all_skills)[:10]

    def run_skill(self, skill_name: str, args: str = "",
                  progress_callback=None, phase: int = -1,
                  agent_role: str = "unknown") -> dict:
        """Execute a skill via `opencode run` with streaming output.

        Supports optional SkillContract protection:
        - Pre-condition: input schema + state isolation check
        - In-flight: entropy monitoring
        - Audit logging (if audit_logger provided)
        """
        import shlex
        safe_args = shlex.quote(args[:300]) if args else ""
        cmd = f"timeout {SKILL_TIMEOUT} opencode run /{skill_name} {safe_args}".strip()
        start = time.time()
        all_lines = []
        proc = None

        # ── Pre-condition (configurable per skill) ──
        if self.contract and self.contract_config and self.contract_config.is_enabled(skill_name):
            pre = self.contract.validate_pre(skill_name, args, phase)
            if not pre["valid"]:
                self._log_contract_violation(skill_name, "pre", pre["issues"])
                if not self.contract_config.is_log_only():
                    return {
                        "status": "error",
                        "output": f"[CONTRACT FAIL] Pre-validation: {pre['issues']}",
                        "elapsed_sec": 0,
                        "contract_violation": True,
                    }

        try:
            proc = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1,
            )

            def _consume_stderr():
                try:
                    for _ in proc.stderr:
                        pass
                except Exception:
                    pass
            stderr_thread = threading.Thread(target=_consume_stderr, daemon=True)
            stderr_thread.start()

            idle_start = time.time()
            while time.time() - start < SKILL_TIMEOUT:
                if proc.stdout.closed:
                    break
                rlist, _, _ = select.select([proc.stdout], [], [], 1.0)
                if rlist:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    stripped = self._strip_chrome(line).strip()
                    if stripped:
                        all_lines.append(stripped)
                        if progress_callback:
                            progress_callback(stripped[:200])
                        # ── In-flight entropy monitoring ──
                        if self.contract and self.contract_config \
                           and self.contract_config.is_enabled(skill_name) \
                           and self.contract_config.is_entropy_monitor_enabled():
                            self.contract.monitor_entropy(stripped)
                            if self.contract.entropy_dropped():
                                self._log_contract_violation(skill_name, "entropy",
                                                             ["输出熵突然下降，可能进入重复/幻觉模式"])
                    idle_start = time.time()
                else:
                    if time.time() - idle_start > 30:
                        partial = "\n".join(all_lines[-20:])
                        stderr_text = ""
                        try:
                            stderr_text = proc.stderr.read(2000) if proc.stderr else ""
                        except Exception:
                            pass
                        state = proc.poll()
                        try:
                            proc.kill()
                            proc.wait(timeout=5)
                        except Exception:
                            pass
                        elapsed = time.time() - start
                        status = "hang"
                        output = (
                            f"[SKILL HANG] {skill_name} 卡住 30s\n"
                            f"命令: {cmd[:300]}\n"
                            f"进程: {'运行中' if state is None else f'已退出({state})'}\n"
                            f"stderr: {stderr_text[:500]}\n"
                            f"最后输出 ({len(partial)}): {partial[:1000]}"
                        )
                        result = {"status": status, "output": output,
                                  "elapsed_sec": round(elapsed, 1)}
                        self._record_audit(skill_name, args, result, start, phase, agent_role)
                        return result

                    poll = proc.poll()
                    if poll is not None:
                        break

            if proc is not None and proc.poll() is None:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass

            elapsed = time.time() - start
            output = "\n".join(all_lines[-50:])
            stderr_out = ""
            try:
                stderr_out = proc.stderr.read()[:2000] if proc.stderr and proc.stderr.readable() else ""
            except Exception:
                pass

            if proc.returncode == 0 and len(output) > 10:
                result = {"status": "ok", "output": output[:5000], "elapsed_sec": round(elapsed, 1)}
            elif proc.returncode == 0:
                result = {"status": "ok", "output": output or "(no output)", "elapsed_sec": round(elapsed, 1)}
            elif elapsed >= SKILL_TIMEOUT:
                result = {"status": "timeout", "output": output or f"timed out ({SKILL_TIMEOUT}s)", "elapsed_sec": round(elapsed, 1)}
            else:
                result = {"status": "error", "output": output or stderr_out, "elapsed_sec": round(elapsed, 1)}

            self._record_audit(skill_name, args, result, start, phase, agent_role)
            return result

        except FileNotFoundError:
            result = {"status": "error", "output": "opencode CLI not found", "elapsed_sec": 0}
            self._record_audit(skill_name, args, result, start, phase, agent_role)
            return result
        except Exception as e:
            result = {"status": "error", "output": str(e)[:1000], "elapsed_sec": round(time.time() - start, 1)}
            self._record_audit(skill_name, args, result, start, phase, agent_role)
            return result
        finally:
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _record_audit(self, skill_name: str, args: str, result: dict,
                      start: float, phase: int, agent_role: str):
        """Record skill execution to audit logger."""
        if not self.audit:
            return
        elapsed_ms = int((time.time() - start) * 1000)
        try:
            self.audit.log_tool_call(
                tool_name=skill_name,
                args={"args": args[:500], "phase": phase, "agent": agent_role},
                result=result.get("output", "")[:500],
                agent=agent_role,
                duration_ms=elapsed_ms,
                approved=(result.get("status") == "ok"),
            )
        except Exception:
            pass

    def _log_contract_violation(self, skill_name: str, stage: str, issues: list):
        """Record contract violation to Redis list for monitoring."""
        if self.r:
            try:
                self.r.lpush("academic:contract:violations", json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "skill": skill_name,
                    "stage": stage,
                    "issues": issues,
                }))
            except Exception:
                pass

    def suggest_skill(self, role: str, phase: int, task: str, llm) -> Optional[str]:
        """Use LLM to select the best skill for the current task."""
        available = self.get_skills_for_role(role)
        if not available:
            return None
        skill_list = "\n".join(f"  {i+1}. /{s}" for i, s in enumerate(available[:15]))
        prompt = (
            f"You are {role} in Phase {phase}. Task: {task[:300]}\n"
            f"Available skills:\n{skill_list}\n"
            "Which single skill is most relevant? Reply with ONLY the skill name."
        )
        try:
            response = llm.complete([
                {"role": "system", "content": "You select the best skill. Output only the skill name."},
                {"role": "user", "content": prompt},
            ], max_tokens=50, temperature=0.1)
            response = response.strip().strip("`").strip("/")
            if response in available:
                return response
        except Exception:
            pass
        return available[0] if available else None

    def _ensure_loaded(self):
        if self._registry_loaded:
            return
        self._role_skills = self._parse_registry()
        self._registry_loaded = True

    def _parse_registry(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        if not os.path.exists(REGISTRY_PATH):
            return result
        with open(REGISTRY_PATH) as f:
            content = f.read()
        sections = re.split(r"^### ", content, flags=re.MULTILINE)
        for section in sections:
            name_match = re.match(r"^([^\n]+)", section)
            if not name_match:
                continue
            name = name_match.group(1).strip().split(" - ")[0].strip()
            skill_match = re.search(
                r"\*\*调用技能\*\*[：:](.*?)(?:\n\n|\n###|\Z)", section, re.DOTALL
            )
            if not skill_match:
                continue
            skills_text = skill_match.group(1)
            skills = re.findall(r"`([^`]+)`", skills_text)
            clean = []
            for s in skills:
                s = s.strip().strip("`").strip()
                if s.startswith("/"):
                    clean.append(s[1:])
                elif s:
                    clean.append(s)
            if clean:
                result[name] = clean
        return result

    @staticmethod
    def _strip_chrome(text: str) -> str:
        """Remove opencode UI chrome from skill output."""
        lines = text.splitlines()
        cleaned = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            s = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', s)
            s = re.sub(r'\x1b\][^\x07\x1b]*(\x07|\x1b\\)', '', s)
            if re.match(r'^>\s+build', s, re.IGNORECASE):
                continue
            if re.match(r'^→\s+Skill', s):
                continue
            if re.match(r'^✱\s+Glob', s):
                continue
            if re.match(r'^\$ ', s):
                continue
            if re.match(r'^ARXIV_FETCHER', s):
                continue
            s = re.sub(r'[▄█▀▄▆▇▉▊▋▌▍▎▏─━│┃┄┅┆┇┈┉┊┋]', '', s)
            s = s.strip()
            if s:
                cleaned.append(s)
        return '\n'.join(cleaned[:100])
