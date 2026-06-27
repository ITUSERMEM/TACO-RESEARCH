"""Phase 0-5 Academic Team Main Loop.

Kocoro-inspired orchestrator for the 12-agent academic research pipeline.
Manages phase transitions, review gates, context compaction, and
persistent state across the entire research lifecycle.

Usage:
    from academic_loop import AcademicLoop
    loop = AcademicLoop()
    loop.run()  # Execute full Phase 0-5 pipeline
"""

import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from redis import Redis

from agent_memory import AgentMemory
from semantic_cache import SemanticCache
from llm_client import LLMClient, DualLLM
from complexity_router import ComplexityRouter
from cost_ledger import CostLedger
from gate_judge import GateJudge, FUSION_GATES
from hallucination_guard import HallucinationGuard
from heartbeat import Heartbeat, HeartbeatConfig
from loop_detector import PhaseLoopDetector, LoopAction
from model_registry import ModelRegistry
from skill_executor import SkillExecutor
from audit_logger import AuditLogger
from skill_contract import SkillContract
from summarizer import PhaseSummarizer
from token_budget import TokenBudget

ROLE_CN = {
    "research-director": "研究项目总监", "academic-editor": "学术编辑",
    "literature-researcher": "文献研究员", "methodologist": "方法论研究员",
    "method-reviewer": "方法评审员", "experimenter": "实验工程师",
    "scientific-computing-engineer": "科学计算工程师", "code-engineer": "代码工程师",
    "paper-writer": "论文写手", "visualization-designer": "可视化设计师",
    "academic-reviewer": "学术评审员", "citation-auditor": "引用审计员",
}


# ── Phase Definition ─────────────────────────────────────────

class Phase(Enum):
    PHASE0 = 0
    PHASE1 = 1
    PHASE2 = 2
    PHASE3 = 3
    PHASE4 = 4
    PHASE5 = 5


PHASE_NAMES = {
    Phase.PHASE0: "environment-init",
    Phase.PHASE1: "literature-review",
    Phase.PHASE2: "method-design",
    Phase.PHASE3: "experiment",
    Phase.PHASE4: "coding",
    Phase.PHASE5: "paper-writing",
}

PHASE_LABELS = {
    Phase.PHASE0: "环境初始化",
    Phase.PHASE1: "文献调研",
    Phase.PHASE2: "方案设计",
    Phase.PHASE3: "实验验证",
    Phase.PHASE4: "代码实现",
    Phase.PHASE5: "论文撰写",
}

# Each phase's max iterations (like Kocoro's maxIter)
MAX_ITERATIONS = {
    Phase.PHASE0: 1,
    Phase.PHASE1: 5,
    Phase.PHASE2: 3,
    Phase.PHASE3: 8,
    Phase.PHASE4: 5,
    Phase.PHASE5: 5,
}

REVIEW_GATES = {
    Phase.PHASE1: 1,
    Phase.PHASE2: 2,
    Phase.PHASE3: 3,
    Phase.PHASE4: (4, 5),  # Gate 4 (claim) + Gate 5 (citation)
    Phase.PHASE5: (6, 7),  # Gate 6 (final) + Gate 7 (final citation)
}

# ── Agent Tier Mapping ─────────────────────────────────────
# Maps each skill to the appropriate LLM tier based on task complexity.
# executor (flash)  → default execution
# reviewer (glm-5.2) → simple analysis, research, literature
# pro (deepseek-v4-pro) → complex reasoning, writing, proof checking

AGENT_TIER = {
    "research-pipeline": "executor",
    "paper-compile": "executor",
    "git-commit": "executor",
    "research-lit": "reviewer",
    "arxiv": "reviewer",
    "paper-read": "reviewer",
    "literature-review": "reviewer",
    "novelty-check": "reviewer",
    "research-wiki": "executor",
    "semantic-scholar": "reviewer",
    "paper-lookup": "reviewer",
    "idea-creator": "executor",
    "experiment-plan": "executor",
    "formula-derivation": "pro",
    "proof-checker": "pro",
    "proof-writer": "pro",
    "kill-argument": "pro",
    "run-experiment": "executor",
    "experiment-bridge": "executor",
    "analyze-results": "executor",
    "training-check": "executor",
    "experiment-queue": "executor",
    "paper-figure": "executor",
    "figure-spec": "executor",
    "nature-figure": "executor",
    "paper-slides": "executor",
    "scientific-schematics": "executor",
    "paper-write": "pro",
    "nature-writing": "pro",
    "paper-plan": "executor",
    "citation-audit": "pro",
    "paper-claim-audit": "pro",
    "latex-polish": "reviewer",
    "nature-polishing": "reviewer",
}

AGENT_ROLES = [
    "research-director",
    "academic-editor",
    "literature-researcher",
    "methodologist",
    "method-reviewer",
    "experimenter",
    "scientific-computing-engineer",
    "code-engineer",
    "paper-writer",
    "visualization-designer",
    "academic-reviewer",
    "citation-auditor",
]

PHASE_AGENTS = {
    Phase.PHASE0: ["research-director", "academic-editor"],
    Phase.PHASE1: ["research-director", "literature-researcher", "academic-reviewer"],
    Phase.PHASE2: ["methodologist", "method-reviewer", "research-director"],
    Phase.PHASE3: ["experimenter", "scientific-computing-engineer", "academic-reviewer"],
    Phase.PHASE4: ["code-engineer", "visualization-designer", "paper-writer", "academic-reviewer"],
    Phase.PHASE5: ["paper-writer", "visualization-designer", "citation-auditor", "academic-editor"],
}


# ── Phase Tracker (Kocoro-inspired) ──────────────────────────

class PhaseTracker:
    """Tracks phase lifecycle: Setup → Run(iter) → Done → Review → Transition.

    Mirrors Kocoro's internal phase tracking with Redis persistence.
    """

    STATE_KEY = "academic:phase:state"
    METRIC_PREFIX = "academic:phase:metric"

    def __init__(self, r: Redis, namespace: str = "academic"):
        self.r = r
        self.namespace = namespace
        self._ensure_schema()

    def _ensure_schema(self):
        default = {
            "current_phase": 0,
            "phase_started_at": None,
            "phase_iterations": 0,
            "completed_phases": [],
            "gate_results": {},
            "project_id": None,
            "project_title": None,
            "status": "idle",
        }
        if not self.r.exists(self.STATE_KEY):
            self.r.json().set(self.STATE_KEY, "$", default)

    @property
    def state(self) -> dict:
        return self.r.json().get(self.STATE_KEY) or {}

    def _set(self, path: str, value: Any):
        self._ensure_schema()
        self.r.json().set(self.STATE_KEY, path, value)

    def phase_enter(self, phase: Phase, project_id: Optional[str] = None):
        now = datetime.now(timezone.utc).isoformat()
        self._set("$.current_phase", phase.value)
        self._set("$.phase_started_at", now)
        self._set("$.phase_iterations", 0)
        self._set("$.status", "running")
        if project_id:
            self._set("$.project_id", project_id)
        self._record_metric(f"phase.{phase.value}.enter", 0.0)

    def iteration_increment(self, phase: Phase):
        iters = (self.state.get("phase_iterations") or 0) + 1
        self._set("$.phase_iterations", iters)
        self._record_metric(f"phase.{phase.value}.iter.{iters}", time.time())
        return iters

    def phase_complete(self, phase: Phase):
        completed = self.state.get("completed_phases") or []
        if phase.value not in completed:
            completed.append(phase.value)
        self._set("$.completed_phases", completed)
        self._set("$.status", "idle")
        self._record_metric(f"phase.{phase.value}.complete", time.time())

    def gate_record(self, phase: Phase, gate_id: int, verdict: str, details: Optional[dict] = None):
        gates = self.state.get("gate_results") or {}
        key = f"phase{phase.value}_gate{gate_id}"
        gates[key] = {
            "verdict": verdict,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }
        self._set("$.gate_results", gates)
        self._record_metric(f"gate.{phase.value}.{gate_id}.{verdict}", time.time())

    def is_phase_done(self, phase: Phase) -> bool:
        return phase.value in (self.state.get("completed_phases") or [])

    def can_transition(self, current: Phase, target: Phase) -> bool:
        return self.is_phase_done(current) and target.value == current.value + 1

    def _record_metric(self, name: str, value: float):
        key = f"{self.METRIC_PREFIX}:{name}"
        try:
            if not self.r.exists(key):
                self.r.execute_command(f"TS.CREATE {key} DUPLICATE_POLICY LAST")
            self.r.execute_command(f"TS.ADD {key} * {value}")
        except Exception:
            pass


# ── Context Compaction (Kocoro-inspired) ─────────────────────

class ContextCompactor:
    """Three-level context compaction: proactive → preflight → reactive.

    Like Kocoro's context management:
    - 90% threshold: proactive compaction with PersistLearnings
    - 95% threshold: preflight emergency compaction
    - Error-triggered: reactive compaction + retry
    """

    def __init__(self, mem: AgentMemory, token_budget: int = 128_000):
        self.mem = mem
        self.token_budget = token_budget
        self.max_summary_failures = 3
        self.summary_failures = 0
        self.backoff_iters = 5
        self.compaction_count = 0

    def should_compact(self, estimated_tokens: int, context_window: int) -> bool:
        ratio = estimated_tokens / context_window
        if ratio >= 0.95:
            return True  # preflight emergency
        if ratio >= 0.90:
            return True  # proactive
        return False

    def compact(self, session_id: str, messages: list[dict]) -> list[dict]:
        """Two-phase compaction: persist → summarize → shape."""
        try:
            learnings = self._extract_learnings(messages)
            if learnings:
                self.mem.create_long_term_memory(
                    content=json.dumps(learnings, ensure_ascii=False),
                    topics=["compaction", f"session-{session_id[:12]}"],
                    owner_id="context-compactor",
                    memory_type="compaction-summary",
                )
            summary = self._generate_summary(messages)
            shaped = self._shape_history(messages, summary)
            self.compaction_count += 1
            self.summary_failures = 0
            return shaped
        except Exception:
            self.summary_failures += 1
            return messages

    def _extract_learnings(self, messages: list[dict]) -> Optional[list[str]]:
        learnings = []
        for msg in messages[-50:]:
            content = msg.get("content", "")
            if isinstance(content, str):
                content = content[:1000]
            else:
                continue
            if len(learnings) > 20:
                break
            learnings.append(content)
        return learnings if learnings else None

    def _generate_summary(self, messages: list[dict]) -> str:
        phase_info = ""
        for msg in messages[:5]:
            c = msg.get("content", "")
            if isinstance(c, str) and "Phase" in c:
                phase_info = c[:200]
                break

        return (
            f"## Session Summary (compact #{self.compaction_count})\n\n"
            f"Messages: {len(messages)}\n"
            f"Context: {phase_info}\n"
            f"Compacted at: {datetime.now(timezone.utc).isoformat()}\n"
        )

    def _shape_history(self, messages: list[dict], summary: str) -> list[dict]:
        if len(messages) <= 10:
            return messages

        system_block = [m for m in messages if m.get("role") == "system"]
        first_block = messages[:3]
        last_block = messages[-5:]
        summary_msg = {
            "role": "assistant",
            "content": f"[Context compaction: earlier history summarized below]\n\n{summary}",
        }
        shaped = system_block + first_block + [summary_msg] + last_block
        return shaped


# ── Watchdog (Kocoro-inspired) ───────────────────────────────

@dataclass
class WatchdogConfig:
    soft_timeout: float = 90.0
    hard_timeout: float = 540.0
    stream_idle_timeout: float = 90.0
    tick_interval: float = 1.0

    @classmethod
    def for_phase(cls, phase: Phase) -> "WatchdogConfig":
        if phase in (Phase.PHASE0, Phase.PHASE1):
            return cls(soft_timeout=120.0, hard_timeout=600.0)
        if phase == Phase.PHASE3:
            return cls(soft_timeout=300.0, hard_timeout=1800.0)
        return cls()


class Watchdog:
    """Phase-level watchdog timer with soft/hard timeout escalation.

    Like Kocoro's idle timeout: soft triggers warning, hard force-stops.
    """

    def __init__(self, config: WatchdogConfig):
        self.config = config
        self.last_activity: float = time.time()
        self.start_time: float = time.time()
        self.soft_warning: bool = False

    def pet(self):
        self.last_activity = time.time()

    def check(self) -> Optional[str]:
        elapsed = time.time() - self.start_time
        idle = time.time() - self.last_activity

        if elapsed >= self.config.hard_timeout:
            return "force-stop"
        if idle >= self.config.stream_idle_timeout:
            return "force-stop"
        if elapsed >= self.config.soft_timeout and not self.soft_warning:
            self.soft_warning = True
            return "soft-warning"
        if idle >= self.config.soft_timeout * 0.5:
            return None  # still OK but close to warning
        return None

    def reset(self):
        self.last_activity = time.time()
        self.start_time = time.time()
        self.soft_warning = False


# ── Main Loop ────────────────────────────────────────────────

class AcademicLoop:
    """Phase 0-5 orchestrator for the 12-agent academic research team.

    Integrates:
    - AgentMemory (LTM + Session + Timeseries)
    - PhaseTracker (state persistence)
    - ContextCompactor (token budget management)
    - Watchdog (timeout enforcement)
    - 7 review gates (quality control)
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        namespace: str = "academic",
        project_title: Optional[str] = None,
        output_dir: Optional[str] = None,
        daemon_mode: bool = False,
    ):
        self.output_dir = os.path.abspath(output_dir or os.getcwd())
        self.r = Redis.from_url(redis_url, decode_responses=True)
        self.mem = AgentMemory(redis_url=redis_url, namespace=namespace)
        self.cache = SemanticCache(similarity_threshold=0.5)
        self.tracker = PhaseTracker(self.r, namespace=namespace)
        self.compactor = ContextCompactor(self.mem)
        self.llm = DualLLM(cache=self.cache)
        self.gate_judge = GateJudge(
            reviewer_llm=self.llm.reviewer,
            pro_llm=self.llm.pro,
        )
        # P2: HallucinationGuard — 3-layer hallucination detection
        self.hallucination_guard = HallucinationGuard()
        # P3: ComplexityRouter + ModelRegistry — dynamic iteration + degrade
        self.router = ComplexityRouter()
        self.model_registry = ModelRegistry()
        # P4: PhaseSummarizer — structured phase summaries
        self.summarizer = PhaseSummarizer(llm=self.llm.reviewer)
        # P6: Heartbeat — per-agent periodic health checks
        self.heartbeat = Heartbeat()
        self.audit = AuditLogger(
            log_dir="/var/log/academic-team",
            redis_url=redis_url,
        )
        self.contract = SkillContract(
            executor_llm=self.llm.executor,
            reviewer_llm=self.llm.reviewer,
            redis_client=self.r,
        )
        self.skill_executor = SkillExecutor(
            redis_client=self.r,
            contract=self.contract,
            audit_logger=self.audit,
        )
        self.namespace = namespace
        self.project_id = str(uuid.uuid4())[:12]
        self.project_dir = os.path.join(self.output_dir, "projects", self.project_id)
        self.daemon_mode = daemon_mode
        self._running = False
        self._progress_channel = "academic:progress"
        self._chat_id = ""
        self._outbox_channel = "academic:outbox"

        if project_title:
            self.tracker._set("$.project_title", project_title)

        # P0-1: TokenBudget for pipeline-level token enforcement
        self.budget = TokenBudget(
            redis_url=redis_url,
            session_id=self.project_id,
            task_id=self.project_id,
        )
        # P0-2: CostLedger for append-only cost tracking with snapshotMax
        self.cost_ledger = CostLedger(self.r)

        self._phase_results: dict[int, dict] = {}
        self._create_project_structure()

    def _create_project_structure(self):
        """Create project output directory structure for file artifacts."""
        subdirs = ["paper", "figures", "data", "idea-stage", "refine-logs", "review-stage"]
        for sub in subdirs:
            os.makedirs(os.path.join(self.project_dir, sub), exist_ok=True)
        print(f"[AcademicLoop] Project directory: {self.project_dir}")

    @property
    def current_phase(self) -> Phase:
        return Phase(self.tracker.state.get("current_phase", 0))

    # ── Run ─────────────────────────────────────────────────

    def run(self, start_phase: Phase = Phase.PHASE0, end_phase: Phase = Phase.PHASE5):
        """Execute the full Phase 0-5 pipeline."""
        print(f"[AcademicLoop] Starting project {self.project_id}")
        print(f"[AcademicLoop] Pipeline: {PHASE_LABELS[start_phase]} → {PHASE_LABELS[end_phase]}")
        print()

        # P6: Start heartbeat agents for all phase agents
        all_agents = set()
        for p in Phase:
            all_agents.update(PHASE_AGENTS.get(p, []))
        for agent in all_agents:
            cfg = HeartbeatConfig(agent=agent, interval_secs=120)
            self.heartbeat.register(cfg)
        self.heartbeat.start()
        print(f"[AcademicLoop] Heartbeat started for {len(all_agents)} agents")

        for phase in Phase:
            if phase.value < start_phase.value:
                continue
            if phase.value > end_phase.value:
                break

            self._execute_phase(phase)

        self.heartbeat.stop()
        print(f"[AcademicLoop] Heartbeat stopped")
        print(f"\n[AcademicLoop] Pipeline complete")
        print(f"[AcademicLoop] Completed phases: {self.tracker.state.get('completed_phases')}")

    # ── Phase Execution ──────────────────────────────────────

    def _execute_phase(self, phase: Phase):
        label = PHASE_LABELS[phase]
        print(f"{'='*60}")
        print(f"  Phase {phase.value}: {label}")
        print(f"{'='*60}")

        self.tracker.phase_enter(phase, project_id=self.project_id)
        if self.audit:
            self.audit.log(
                event="phase_transition",
                phase=phase.value,
                details={
                    "phase_name": PHASE_NAMES[phase],
                    "phase_label": label,
                    "project_id": self.project_id,
                },
            )
        watchdog = Watchdog(WatchdogConfig.for_phase(phase))
        session_id = f"phase{phase.value}-{self.project_id}"

        max_iters = MAX_ITERATIONS[phase]
        agents = PHASE_AGENTS[phase]
        print(f"  Agents: {', '.join(agents)}")
        # P3: Dynamically adjust iterations based on task complexity
        task_text = self.tracker.state.get("project_title", "") or ""
        complexity = self.router.compute(task_text)
        if complexity < 0.3:
            max_iters = max(max_iters // 2, 1)
        elif complexity > 0.7:
            max_iters = max_iters * 2
        self._emit_progress(phase.value, "phase_planned",
                            f"Complexity: {complexity:.2f} → max_iters: {max_iters}")
        print(f"  Complexity: {complexity:.2f} → max_iters: {max_iters}")
        print()

        self._emit_progress(phase.value, "phase_start", f"Phase {phase.value}: {label}",
                            int((phase.value / 5) * 100))

        messages: list[dict] = [{
            "role": "system",
            "content": self._build_phase_prompt(phase, agents),
        }]

        for iteration in range(1, max_iters + 1):
            watchdog.pet()
            iters = self.tracker.iteration_increment(phase)
            self._emit_progress(phase.value, "agent_iter",
                                f"Agent {iteration}/{max_iters}: {agents[(iteration-1) % len(agents)]}",
                                int(((phase.value + iteration/max_iters) / 5) * 100))

            # Check watchdog
            watch_status = watchdog.check()
            if watch_status == "force-stop":
                print(f"  ⏹️ Watchdog force-stop at iter {iteration}")
                self.mem.record_event("watchdog_force_stop", time.time(),
                                      {"phase": str(phase.value), "iter": str(iteration)})
                break
            if watch_status == "soft-warning":
                print(f"  ⚠️ Watchdog soft warning at iter {iteration}")
                self.mem.record_event("watchdog_soft_warning", time.time(),
                                      {"phase": str(phase.value), "iter": str(iteration)})

            # Context compaction check
            estimated_tokens = sum(len(str(m.get("content", ""))) * 2 for m in messages)
            if self.compactor.should_compact(estimated_tokens, 128_000):
                pre_count = len(messages)
                messages = self.compactor.compact(session_id, messages)
                post_count = len(messages)
                self.mem.record_event("compaction", time.time(),
                                      {"phase": str(phase.value),
                                       "pre": str(pre_count), "post": str(post_count)})
                print(f"  📦 Context compacted: {pre_count}→{post_count} msgs")

            # Record iteration to session
            self.mem.add_session_event(session_id, {
                "role": "assistant",
                "content": f"[Phase {phase.value}] Iteration {iteration}/{max_iters}",
                "actor": "system",
                "phase": phase.value,
                "iteration": iteration,
            })

            self._execute_agent_iteration(phase, iteration, agents, messages, session_id)

        print()

        # Run review gates for this phase
        phase_result = self._run_review_gates(phase, session_id, messages)
        self._phase_results[phase.value] = phase_result

        # Persist learnings before phase transition
        self._persist_learnings(phase, session_id, messages)

        # Collect file artifacts generated during this phase
        artifacts = self._collect_phase_artifacts(phase)

        # Mark phase complete
        self.tracker.phase_complete(phase)
        self.mem.record_event("phase_complete", time.time(),
                              {"phase": str(phase.value), "project": self.project_id})
        self._emit_progress(phase.value, "phase_complete",
                            f"✅ Phase {phase.value} complete",
                            int(((phase.value + 1) / 5) * 100))
        print(f"  ✅ Phase {phase.value} complete")
        print()

    # ── Review Gates ─────────────────────────────────────────

    def _run_review_gates(self, phase: Phase, session_id: str, messages: list[dict]) -> dict:
        gates = REVIEW_GATES.get(phase)
        if gates is None:
            return {"status": "no-gate", "gates": []}

        if isinstance(gates, int):
            gates = (gates,)

        results = []
        overall = "pass"

        for gate_id in gates:
            verdict, details = self._evaluate_gate(gate_id, phase, session_id, messages)
            self.tracker.gate_record(phase, gate_id, verdict, details)
            self.mem.record_review(
                phase=phase.value,
                phase_name=PHASE_NAMES[phase],
                reviewer=self._gate_reviewer(gate_id),
                verdict=verdict,
                target=f"gate-{gate_id}",
                details=details,
            )
            results.append({"gate": gate_id, "verdict": verdict, "details": details})
            print(f"  Gate {gate_id}: {verdict.upper()}")
            self._emit_progress(phase.value, f"gate_{verdict}",
                                f"Gate {gate_id}: {verdict.upper()} — {self._gate_reviewer(gate_id)}",
                                int(((phase.value + 0.8) / 5) * 100))
            if verdict == "fail":
                overall = "fail"
            elif verdict == "revise" and overall != "fail":
                overall = "revise"

        return {"status": overall, "gates": results}

    def _evaluate_gate(
        self, gate_id: int, phase: Phase, session_id: str, messages: list[dict]
    ) -> tuple[str, dict]:
        transcript = self._build_gate_transcript(messages)
        result = self.gate_judge.evaluate(gate_id, transcript)
        verdict = result.get("verdict", "pass")
        details = {
            "issues": result.get("issues", []),
            "recommendations": result.get("recommendations", []),
        }
        return verdict, details

    @staticmethod
    def _build_gate_transcript(messages: list[dict]) -> str:
        parts = []
        for msg in messages[-20:]:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(f"[{role}]: {content[:1000]}")
        return "\n".join(parts)

    def _execute_agent_iteration(
        self, phase: Phase, iteration: int, agents: list[str],
        messages: list[dict], session_id: str,
    ):
        """Execute one iteration: pick agent → select skill → execute → feed back."""
        role = agents[(iteration - 1) % len(agents)]
        role_cn = ROLE_CN.get(role, role)

        loop_detector = PhaseLoopDetector(role)
        phase_label = PHASE_LABELS[phase]
        pct_base = int((phase.value / 5) * 100)
        task = self._build_agent_task(phase, iteration, messages)

        # Step 0: Agent activated
        self._emit_progress(phase.value, "agent_start",
                            f"👤 {role_cn} 启动 ({iteration}/{MAX_ITERATIONS[phase]})",
                            pct_base)
        print(f"  [{iteration}] 👤 {role_cn} starting...")

        # Step 1: LLM selects a skill
        self._emit_progress(phase.value, "agent_skill_select",
                            f"⚙️ {role_cn} → 正在选择 skill...",
                            pct_base + 5)
        available = self.skill_executor.get_skills_for_role(role)
        if available:
            chosen_skill = self.skill_executor.suggest_skill(role, phase.value, task, self.llm.reviewer)
        else:
            chosen_skill = None

        # Step 2: Execute the selected skill with live progress
        skill_output = ""
        if chosen_skill:
            self._emit_progress(phase.value, "agent_skill_run",
                                f"⚙️ {role_cn} → /{chosen_skill} 执行中...",
                                pct_base + 15)
            print(f"  [{iteration}] ⚙️ {role_cn} → /{chosen_skill}")

            line_count = [0]

            def _on_skill_line(line):
                line_count[0] += 1
                if line_count[0] <= 5:
                    self._emit_progress(phase.value, "agent_skill_output",
                                        f"📄 {role_cn}: {line}", pct_base + 20)

            skill_result = self.skill_executor.run_skill(
                chosen_skill, task[:200], progress_callback=_on_skill_line,
                phase=phase.value, agent_role=role,
                scan_dir=self.project_dir,
            )

            skill_output = skill_result.get("output", "")
            status = skill_result.get("status", "ok")
            elapsed = skill_result.get("elapsed_sec", 0)
            output_preview = skill_output[:200].replace("\n", " ")
            status_icon = "✅" if status == "ok" else "🔴" if status == "hang" else "⚠️" if status == "timeout" else "❌"

            self._emit_progress(phase.value, f"agent_skill_{status}",
                                f"{status_icon} {role_cn} → /{chosen_skill} [{status}] ({elapsed}s)\n"
                                f"   {output_preview}",
                                pct_base + 30)
            print(f"  [{iteration}] {status_icon} /{chosen_skill} [{status}] {elapsed}s")
        else:
            self._emit_progress(phase.value, "agent_skip_skill",
                                f"💬 {role_cn} → 直接推理（无匹配 skill）",
                                pct_base + 20)

        # Step 3: LLM produces response with skill output as context
        self._emit_progress(phase.value, "agent_reasoning",
                            f"🧠 {role_cn} → 正在整合结果生成回答...",
                            pct_base + 40)

        context_messages = [{"role": "system", "content": self._build_agent_prompt(role, phase, messages)}]
        if skill_output and len(skill_output) > 20:
            context_messages.append({
                "role": "system",
                "content": f"[Skill /{chosen_skill} result]\n{skill_output[:3000]}",
            })
        context_messages += messages[-3:]

        tier_name = AGENT_TIER.get(chosen_skill or "", "executor")
        agent_llm = {
            "executor": self.llm.executor,
            "reviewer": self.llm.reviewer,
            "pro": self.llm.pro,
        }[tier_name]

        # P3: Check budget before LLM call — degrade or stop if needed
        budget_status = self.budget.check()
        if budget_status["action"] == "stop":
            self._emit_progress(phase.value, "budget_stop",
                                f"🛑 Budget exhausted ({budget_status['max_pct']}%)")
            response = "[Budget stop: token limit exceeded]"
            messages.append({"role": "assistant", "content": response})
            return
        if budget_status["action"] == "degrade":
            degraded_tier = budget_status["degrade_tier"]
            current_tier = tier_name
            tier_name = self.budget.degrade_model(current_tier)
            self._emit_progress(phase.value, "budget_degrade",
                                f"⚠️ Budget {budget_status['max_pct']}% → degrade {current_tier}→{tier_name}")
            self.mem.record_event("budget_degrade", time.time(),
                                  {"from": str(current_tier), "to": str(tier_name)})

        response = agent_llm.complete(context_messages, max_tokens=4096, temperature=0.3)
        messages.append({"role": "assistant", "content": response})

        # P0-1: Record token usage in TokenBudget
        tokens_used = getattr(agent_llm, 'last_total_tokens', 0) or 0
        if tokens_used > 0:
            self.budget.record(tokens_used, model=tier_name)

        # P2-2: Record cost in CostLedger
        cost_usd = getattr(agent_llm, 'last_cost', 0.0) or 0.0
        input_tokens = getattr(agent_llm, 'last_input_tokens', 0) or 0
        output_tokens = getattr(agent_llm, 'last_output_tokens', 0) or 0
        if cost_usd > 0 or tokens_used > 0:
            self.cost_ledger.record_run(
                project_id=self.project_id,
                session_id=session_id,
                model=tier_name,
                role="agent",
                delta={
                    "cost_usd": cost_usd,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cached_tokens": 0,
                    "total_tokens": tokens_used,
                },
            )

        # Step 4: Complete
        response_preview = response[:80].replace("\n", " ")

        # P2: HallucinationGuard check
        hallucination_nudge = self.hallucination_guard.check(response)
        if hallucination_nudge:
            messages.append({"role": "system", "content": hallucination_nudge})
            self._emit_progress(phase.value, "hallucination_nudge",
                                f"⚠️ Hallucination detected → nudge injected",
                                pct_base + 50)

        self._emit_progress(phase.value, "agent_done",
                            f"✅ {role_cn} 完成\n   {response_preview}",
                            pct_base + 60)

        # Loop detection
        loop_action, loop_msg = loop_detector.check()
        if loop_action == LoopAction.FORCE_STOP:
            messages.append({
                "role": "system",
                "content": f"[Loop detected: {loop_msg or 'force stop'}]",
            })

        self.mem.add_session_event(session_id, {
            "role": "assistant",
            "content": f"[Phase {phase.value}] Iter {iteration}: {role} — {response[:200]}",
            "actor": role,
            "phase": phase.value,
            "iteration": iteration,
        })
        print(f"  [{iteration}] ✅ {role_cn}: done")

    def _build_agent_task(self, phase: Phase, iteration: int, messages: list[dict]) -> str:
        """Extract the current task description from conversation context."""
        phase_label = PHASE_LABELS[phase]
        for msg in reversed(messages[-5:]):
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > 30:
                return f"Phase {phase.value} ({phase_label}): {content[:200]}"
        return f"Execute Phase {phase.value} ({phase_label}), iteration {iteration}"

    def _build_agent_prompt(self, role: str, phase: Phase, messages: list[dict]) -> str:
        phase_label = PHASE_LABELS[phase]
        return (
            f"You are the **{role}** in an academic research team.\n"
            f"Current Phase: {phase.value} — {phase_label}\n"
            f"Project: {self.tracker.state.get('project_title', 'Untitled')}\n"
            f"Project output path: {self.project_dir}\n"
            f"  - Paper files → {self.project_dir}/paper/\n"
            f"  - Figure files → {self.project_dir}/figures/\n"
            f"  - Data files → {self.project_dir}/data/\n"
            f"  - Sketches/ideas → {self.project_dir}/idea-stage/\n"
            f"  - Review logs → {self.project_dir}/review-stage/\n\n"
            f"When generating files, write them to the appropriate subdirectory above.\n\n"
            f"Conversation history ({len(messages)} messages):\n"
            f"Respond with your contribution to this phase."
        )

    @staticmethod
    def _gate_reviewer(gate_id: int) -> str:
        mapping = {1: "academic-reviewer", 2: "method-reviewer", 3: "academic-reviewer",
                   4: "academic-reviewer", 5: "citation-auditor", 6: "academic-editor",
                   7: "citation-auditor"}
        return mapping.get(gate_id, "unknown")

    # ── Helpers ──────────────────────────────────────────────

    def _build_phase_prompt(self, phase: Phase, agents: list[str]) -> str:
        return (
            f"## Phase {phase.value}: {PHASE_LABELS[phase]}\n\n"
            f"Active agents: {', '.join(agents)}\n"
            f"Max iterations: {MAX_ITERATIONS[phase]}\n"
            f"Project: {self.tracker.state.get('project_title', 'Untitled')}\n"
            f"Project ID: {self.project_id}\n"
            f"Project output path: {self.project_dir}\n"
        )

    def _persist_learnings(self, phase: Phase, session_id: str, messages: list[dict]):
        # P4: Generate structured summary via Summarizer
        summary_result = {}
        try:
            summary_result = self.summarizer.summarize(messages, phase=phase.value)
        except Exception as e:
            print(f"  ⚠️ Summarizer failed: {e}")

        if summary_result:
            summary_key = f"academic:phase:summary:{self.project_id}:{phase.value}"
            try:
                self.r.json().set(summary_key, "$", {
                    "project_id": self.project_id,
                    "phase": phase.value,
                    "phase_label": PHASE_LABELS[phase],
                    "analysis": summary_result.get("analysis", ""),
                    "summary": summary_result.get("summary", ""),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                print(f"  ⚠️ Failed to store summary: {e}")

        content = (
            f"Phase {phase.value} ({PHASE_LABELS[phase]}) completed.\n"
            f"Agents: {', '.join(PHASE_AGENTS[phase])}\n"
            f"Iterations run: {self.tracker.state.get('phase_iterations', 0)}\n"
            f"Gates: {self.tracker.state.get('gate_results', {})}\n"
            f"Messages in session: {len(messages)}\n"
        )
        if summary_result:
            content += f"\nSummary: {summary_result.get('summary', '')[:500]}\n"
        self.mem.create_long_term_memory(
            content=content,
            topics=["phase-complete", f"phase-{phase.value}", self.project_id],
            owner_id="academic-loop",
            memory_type=f"phase-{phase.value}-summary",
            metadata={
                "phase": phase.value,
                "project_id": self.project_id,
                "session_id": session_id,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "has_summary": bool(summary_result),
            },
        )

    def _collect_phase_artifacts(self, phase: Phase) -> list[dict]:
        """Scan project directory for generated files and log them."""
        artifacts = []
        for root, _dirs, files in os.walk(self.project_dir):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), self.project_dir)
                fpath = os.path.join(root, f)
                size = os.path.getsize(fpath)
                artifacts.append({"path": rel, "size": size})
        if artifacts:
            print(f"  📁 Phase {phase.value} artifacts ({len(artifacts)} files):")
            for a in artifacts:
                print(f"     {a['path']} ({a['size']}B)")
            self._emit_progress(phase.value, "phase_artifacts",
                                f"📁 Phase {phase.value}: {len(artifacts)} files generated",
                                int(((phase.value + 1) / 5) * 100))
        return artifacts

    def status(self) -> dict:
        return {
            "project_id": self.project_id,
            "current_phase": self.current_phase.value,
            "state": self.tracker.state,
            "phase_results": list(self._phase_results.keys()),
        }

    # ── Progress Publishing ─────────────────────────────────

    def _emit_progress(self, phase: int, status: str, detail: str,
                       progress_pct: int = 0):
        """Publish pipeline progress to progress channel."""
        try:
            msg = json.dumps({
                "type": "progress",
                "chat_id": self._chat_id,
                "phase": phase,
                "phase_label": PHASE_LABELS.get(Phase(phase), f"Phase {phase}"),
                "status": status,
                "detail": detail,
                "progress_pct": progress_pct,
                "project_id": self.project_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self.r.publish(self._progress_channel, msg)
        except Exception:
            pass

    def progress_callback(self, phase_val: int, status: str, detail: str, pct: int = 0):
        self._emit_progress(phase_val, status, detail, pct)

    # ── Daemon Mode ──────────────────────────────────────────

    def _check_is_running(self) -> bool:
        """Check if pipeline is running, treating stale state (>30min) as idle."""
        state = self.tracker.state
        if state.get("status") != "running":
            return False
        started = state.get("phase_started_at")
        if started:
            import datetime as _dt
            try:
                started_dt = _dt.datetime.fromisoformat(started)
                age = (_dt.datetime.now(_dt.timezone.utc) - started_dt).total_seconds()
            except Exception:
                age = 0
            if age > 1800:
                self.tracker._set("$.status", "idle")
                return False
        return True

    def _clear_stale_state(self, force: bool = False):
        """Reset PhaseTracker if it shows stale running state.

        Args:
            force: If True, always clear regardless of age (used on daemon boot).
        """
        try:
            state = self.tracker.state
            if state.get("status") == "running":
                started = state.get("phase_started_at")
                age = 0
                stale = force
                if started and not force:
                    import datetime as _dt
                    try:
                        started_dt = _dt.datetime.fromisoformat(started)
                        age = (_dt.datetime.now(_dt.timezone.utc) - started_dt).total_seconds()
                        if age > 120:
                            stale = True
                    except Exception:
                        stale = True
                elif not started:
                    stale = True
                if stale:
                    self.tracker._set("$.status", "idle")
                    self.tracker._set("$.completed_phases", [])
                    self.tracker._set("$.current_phase", 0)
                    self.tracker._set("$.phase_iterations", 0)
                    print(f"[AcademicLoop:daemon] Cleared stale pipeline state"
                          f" (age={int(age)}s, force={force})")
        except Exception:
            pass

    def start_daemon(self, inbox_channel: str = "academic:inbox",
                     outbox_channel: str = "academic:outbox"):
        """Run in daemon mode, listening for incoming messages via Redis pub/sub."""
        self._clear_stale_state(force=True)
        self._running = True
        pubsub = self.r.pubsub()
        pubsub.subscribe(inbox_channel)
        print(f"[AcademicLoop:daemon] Listening on {inbox_channel}")

        for message in pubsub.listen():
            if not self._running:
                break
            if message["type"] != "message":
                continue

            try:
                data = json.loads(message["data"])
                result = self.process_incoming(data)
                if result and outbox_channel:
                    self.r.publish(outbox_channel, json.dumps(result))
            except Exception as e:
                print(f"[AcademicLoop:daemon] Error: {e}")

        pubsub.unsubscribe()
        print("[AcademicLoop:daemon] Stopped")

    def stop_daemon(self):
        self._running = False

    def _run_pipeline_thread(self, text: str, chat_id: str):
        """Start Phase 0-5 pipeline in a background thread."""
        self.tracker._set("$.project_title", text[:200])
        self.mem.create_long_term_memory(
            content=f"Research direction: {text}",
            topics=["research-direction", "user-input", self.project_id],
            owner_id="telegram-user", memory_type="research-direction",
        )
        self._emit_progress(0, "pipeline_start", "🚀 Pipeline starting...", 0)

        import threading as _t
        loop_ref = self

        def _run_pipeline():
            import io as _io
            old_stdout = sys.stdout
            sys.stdout = _io.StringIO()
            try:
                loop_ref.run(start_phase=Phase.PHASE0, end_phase=Phase.PHASE5)
                state = loop_ref.tracker.state
                completed = state.get("completed_phases", [])
                gates = state.get("gate_results", {})
                result = {
                    "type": "pipeline_result",
                    "chat_id": chat_id,
                    "text": (
                        f"✅ Pipeline complete\n"
                        f"Completed phases: {completed}\n"
                        f"Gates passed: {len(gates)}\n"
                        f"Use /status for details."
                    ),
                    "data": {"completed_phases": completed,
                             "gate_results": gates,
                             "project_id": loop_ref.project_id},
                }
                if loop_ref._outbox_channel:
                    loop_ref.r.publish(loop_ref._outbox_channel, json.dumps(result))
            except Exception as e:
                loop_ref._emit_progress(0, "pipeline_error", f"Pipeline error: {e}", 0)
            finally:
                sys.stdout = old_stdout

        _t.Thread(target=_run_pipeline, daemon=True).start()

    def process_incoming(self, data: dict) -> Optional[dict]:
        """Process an incoming message with command routing.

        Commands:
          /status         → return current PhaseTracker status
          /results        → return last pipeline results
          /stop           → stop running pipeline
          /research <q>   → start pipeline (only if idle)
          plain text when idle    → start pipeline
          plain text when running →提示 pipeline 已运行
        """
        msg_type = data.get("type", "user_message")
        text = (data.get("text", "") or "").strip()
        chat_id = data.get("chat_id", "")
        self._chat_id = chat_id

        # status_query from bridge /status command
        if msg_type == "status_query":
            return {"type": "status_response", "chat_id": chat_id, "data": self.status()}

        if msg_type != "user_message" or not text:
            return None

        is_running = self._check_is_running()

        # ── Command routing ──
        if text == "/status":
            state = self.tracker.state
            return {
                "type": "pipeline_result",
                "chat_id": chat_id,
                "text": (
                    f"📊 **当前状态**\n"
                    f"项目: {state.get('project_title','')[:60] or '无'}\n"
                    f"当前 Phase: {state.get('current_phase', 0)}/5\n"
                    f"已完成: {state.get('completed_phases', [])}\n"
                    f"管线状态: {state.get('status', 'idle')}\n"
                    f"Gate 结果: {state.get('gate_results', {})}"
                ),
            }

        if text == "/results":
            last_results = self._phase_results
            if not last_results:
                return {"type": "pipeline_result", "chat_id": chat_id,
                        "text": "暂无管线结果"}
            return {"type": "pipeline_result", "chat_id": chat_id,
                    "text": f"📊 上次管线结果\n已完成 Phase: {list(last_results.keys())}"}

        if text == "/stop":
            if not is_running:
                return {"type": "pipeline_result", "chat_id": chat_id,
                        "text": "管线未在运行"}
            self._emit_progress(0, "pipeline_error", "⏹️ Pipeline stopped by user", 0)
            self.tracker._set("$.status", "idle")
            return {"type": "pipeline_result", "chat_id": chat_id,
                    "text": "⏹️ 管线已停止"}

        # If pipeline is already running, don't start a new one
        if is_running:
            return {
                "type": "pipeline_ack",
                "chat_id": chat_id,
                "text": (
                    f"⚠️ 管线正在运行中（Phase {self.tracker.state.get('current_phase', '?')}）\n"
                    f"输入 /status 查看进度\n"
                    f"输入 /stop 停止当前管线\n"
                    f"完成后可发新消息启动新管线"
                ),
            }

        # Start pipeline
        self._run_pipeline_thread(text, chat_id)
        return {"type": "pipeline_ack", "chat_id": chat_id,
                "text": "🚀 管线已启动，进度将实时推送"}

    def close(self):
        self._running = False
        self.mem.r.close()
        self.cache.r.close()
        self.r.close()


# ── Quick Test ───────────────────────────────────────────────

if __name__ == "__main__":
    loop = AcademicLoop(project_title="物理感知少样本故障诊断")
    loop.run(start_phase=Phase.PHASE0, end_phase=Phase.PHASE1)
    print()
    import json
    print(json.dumps(loop.status(), indent=2, ensure_ascii=False, default=str))
    loop.close()
