"""9-Path Loop Detector for Academic Team.

Kocoro-inspired sliding-window loop detection with Nudge → ForceStop escalation.
Monitors tool/agent call patterns across the 7 review gates and Phase iterations.

Usage:
    detector = LoopDetector(history_size=20)
    detector.record("literature_researcher", "paper_search", args_hash="abc")
    action = detector.check()  # LoopContinue / LoopNudge / LoopForceStop
"""

import hashlib
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LoopAction(Enum):
    CONTINUE = "continue"
    NUDGE = "nudge"
    FORCE_STOP = "force-stop"


NUDGE_ESCALATION_LIMIT = 3
NUDGE_WINDOW_ITERS = 10


@dataclass
class ToolCall:
    name: str
    args_hash: str
    timestamp: float
    is_error: bool
    topic: str = ""
    result_summary: str = ""


# Kocoro's classification maps
READ_VERBS = {"search", "get", "list", "read", "find", "lookup", "query", "check"}
WRITE_VERBS = {"create", "update", "delete", "edit", "write", "save", "set", "add"}
DUP_EXEMPT_TOOLS = {"use_skill"}
REPEATABLE_GUI_TOOLS = {"screenshot", "computer", "accessibility", "browser"}
SEMI_REPEATABLE_PROD_TOOLS = {"bash"}
BATCH_TOLERANT_TOOLS = {"http", "read_file", "search_tool"}

# Topic families for FamilyNoProgress detector
TOPIC_FAMILIES = {
    "literature": {"search", "paper_search", "fetch_paper", "read_paper", "semantic_scholar", "arxiv"},
    "experiment": {"train", "eval", "inference", "run_experiment", "grid_search"},
    "code": {"edit_file", "write_file", "read_file", "run_tests", "compile"},
    "writing": {"write_section", "edit_section", "format_citation", "compile_pdf"},
    "review": {"review_gate", "novelty_check", "citation_audit", "experiment_audit"},
}


class LoopDetector:
    """Sliding-window loop detector with 9 detection paths.

    Kocoro thresholds (v2):
    Path 0a: EmptyThinkForceStop — 2 consecutive empty thinks
    Path 0 : ToolModeSwitch — 1 occurrence
    Path 0b: SuccessAfterError — 1 occurrence
    Path 1a: ConsecutiveDuplicate — nudge=3, force=4
    Path 1b: ExactDuplicate — nudge=5, force=10
    Path 2 : SameToolError — nudge=6, force=12
    Path 3 : FamilyNoProgress — nudge=5/8/12
    Path 4 : SearchEscalation — nudge=7, force=12
    Path 5 : NoProgress — nudge=12/16, force=24/32
    """

    def __init__(self, history_size: int = 20):
        self.history: list[ToolCall] = []
        self.history_size = history_size
        self.nudge_count = 0
        self.last_nudge_iter = 0
        self.iteration = 0
        self._last_empty_think = False

    def record(
        self,
        tool_name: str,
        args: Optional[dict] = None,
        is_error: bool = False,
        topic: str = "",
        result_summary: str = "",
    ):
        args_hash = ""
        if args:
            raw = json.dumps(args, sort_keys=True)
            args_hash = hashlib.md5(raw.encode()).hexdigest()[:16]

        self.history.append(ToolCall(
            name=tool_name,
            args_hash=args_hash,
            timestamp=time.time(),
            is_error=is_error,
            topic=topic,
            result_summary=result_summary,
        ))
        if len(self.history) > self.history_size:
            self.history.pop(0)

    def check(self, tool_name: str = "") -> LoopAction:
        if not self.history:
            return LoopAction.CONTINUE

        self.iteration += 1
        recent = self.history[-self.history_size:]

        # ── Path 0a: EmptyThink (tool_name empty = empty think) ──
        if not tool_name or tool_name == "think":
            if self._last_empty_think:
                return LoopAction.FORCE_STOP
            self._last_empty_think = True
        else:
            self._last_empty_think = False

        # ── Path 0: ToolModeSwitch ──
        if len(recent) >= 2:
            prev, curr = recent[-2], recent[-1]
            if self._is_visual(curr.name) and self._is_gui_adjacent(prev.name) and not prev.is_error:
                return self._nudge_or_stop(0)

        # ── Path 0b: SuccessAfterError ──
        if len(recent) >= 3 and self._is_visual(recent[-1].name):
            for call in recent[-4:-1]:
                if call.is_error:
                    return self._nudge_or_stop(0)

        # ── Path 1a: ConsecutiveDuplicate ──
        if len(recent) >= 2:
            dup_count = 0
            all_errors = True
            for call in reversed(recent):
                if call.name == recent[-1].name and call.args_hash == recent[-1].args_hash:
                    dup_count += 1
                    if not call.is_error:
                        all_errors = False
                else:
                    break
            threshold_nudge = 6 if all_errors else 3
            threshold_force = 7 if all_errors else 4
            if dup_count >= threshold_force:
                return LoopAction.FORCE_STOP
            if dup_count >= threshold_nudge:
                return LoopAction.NUDGE

        # ── Path 1a-pre: ValidationError ──
        if len(recent) >= 3:
            last_three = recent[-3:]
            if all(c.is_error and c.name == last_three[0].name and c.args_hash == last_three[0].args_hash
                   for c in last_three):
                return LoopAction.FORCE_STOP

        # ── Path 1b: ExactDuplicate (spread across window) ──
        if len(recent) >= 3:
            counts = defaultdict(int)
            for call in recent:
                key = f"{call.name}:{call.args_hash}"
                counts[key] += 1
            max_dup = max(counts.values()) if counts else 0
            if max_dup >= 10:
                return LoopAction.FORCE_STOP
            if max_dup >= 5:
                return LoopAction.NUDGE

        # ── Path 2: SameToolError ──
        error_counts = defaultdict(int)
        for call in recent:
            if call.is_error:
                error_counts[call.name] += 1
        for tool, count in error_counts.items():
            if count >= 12:
                return LoopAction.FORCE_STOP
            if count >= 6:
                return LoopAction.NUDGE

        # ── Path 3: FamilyNoProgress ──
        topic_calls = self._classify_topic_family(recent)
        for family, count in topic_calls.items():
            if count >= 12:
                return LoopAction.FORCE_STOP
            if count >= 8:
                return self._nudge_or_stop(3)
            if count >= 5:
                return LoopAction.NUDGE

        # ── Path 4: SearchEscalation ──
        search_count = sum(1 for c in recent if self._is_search(c.name) and self._is_non_actionable(c))
        if search_count >= 12:
            return LoopAction.FORCE_STOP
        if search_count >= 7:
            return LoopAction.NUDGE

        # ── Path 5: NoProgress ──
        tool_counts = defaultdict(int)
        unique_hashes = defaultdict(set)
        for call in recent:
            if call.name in DUP_EXEMPT_TOOLS:
                continue
            if call.name in BATCH_TOLERANT_TOOLS:
                unique_hashes[call.name].add(call.args_hash)
                if len(unique_hashes[call.name]) >= len(recent) * 0.5:
                    continue  # legitimate enumeration
            tool_counts[call.name] += 1

        for tool, count in tool_counts.items():
            threshold = 32 if tool in SEMI_REPEATABLE_PROD_TOOLS else 24
            nudge_threshold = 16 if tool in SEMI_REPEATABLE_PROD_TOOLS else 12
            if count >= threshold:
                return LoopAction.FORCE_STOP
            if count >= nudge_threshold:
                return LoopAction.NUDGE

        return LoopAction.CONTINUE

    # ── Internal Methods ──

    def _nudge_or_stop(self, path_id: int) -> LoopAction:
        if self.nudge_count >= NUDGE_ESCALATION_LIMIT:
            return LoopAction.FORCE_STOP
        self.nudge_count += 1
        return LoopAction.NUDGE

    @staticmethod
    def _is_visual(tool: str) -> bool:
        return tool in {"screenshot", "computer"} or "vision" in tool.lower()

    @staticmethod
    def _is_gui_adjacent(tool: str) -> bool:
        return tool in {"applescript", "browser", "accessibility", "ui", "click", "type"}

    @staticmethod
    def _is_search(tool: str) -> bool:
        search_terms = {"search", "find", "lookup", "query", "fetch", "retrieve"}
        return tool.lower() in search_terms or any(t in tool.lower() for t in search_terms)

    @staticmethod
    def _is_non_actionable(call: ToolCall) -> bool:
        return bool(call.is_error) or len(call.result_summary) < 20

    @staticmethod
    def _classify_topic_family(history: list[ToolCall]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for call in history:
            for family, tools in TOPIC_FAMILIES.items():
                if call.name in tools:
                    counts[family] = counts.get(family, 0) + 1
                    break
            else:
                counts["other"] = counts.get("other", 0) + 1
        return counts


# ── Phase-Specific Loop Detector ─────────────────────────────

class PhaseLoopDetector:
    """Loop detector integrated with Phase 0-5 pipeline.

    Each Phase has role-specific NoProgress thresholds derived
    from Kocoro's per-role configuration pattern.
    """

    ROLE_NO_PROGRESS = {
        "literature_researcher": {"nudge": 15, "force": 25},
        "methodologist": {"nudge": 10, "force": 18},
        "experimenter": {"nudge": 8, "force": 14},
        "scientific_computing_engineer": {"nudge": 12, "force": 20},
        "code_engineer": {"nudge": 20, "force": 35},
        "paper_writer": {"nudge": 10, "force": 16},
        "visualization_designer": {"nudge": 6, "force": 10},
    }

    NUDGE_MESSAGES: dict[str, dict[int, str]] = {
        "literature_researcher": {
            LoopAction.NUDGE.value: "You've searched the same topic repeatedly. Synthesize existing findings before continuing.",
            LoopAction.FORCE_STOP.value: "Search loop detected. Escalating to Director for scope redefinition.",
        },
        "experimenter": {
            LoopAction.NUDGE.value: "Multiple experiment configs failed. Consider simplifying the approach or checking GPU health.",
            LoopAction.FORCE_STOP.value: "Experiment failure loop detected. Escalating to Director for method revision.",
        },
        "code_engineer": {
            LoopAction.NUDGE.value: "Repeated tool calls without progress. Step back and plan the implementation.",
            LoopAction.FORCE_STOP.value: "Code edit loop detected. Escalating for architecture review.",
        },
    }

    def __init__(self, role: str):
        self.role = role
        self.detector = LoopDetector(history_size=20)
        self.thresholds = self.ROLE_NO_PROGRESS.get(role, {"nudge": 12, "force": 24})

    def record(self, tool: str, args: Optional[dict] = None, is_error: bool = False):
        self.detector.record(tool, args=args, is_error=is_error)

    def check(self, tool: str = "") -> tuple[LoopAction, Optional[str]]:
        action = self.detector.check(tool)
        msg = None
        if action in (LoopAction.NUDGE, LoopAction.FORCE_STOP):
            msgs_for_role = self.NUDGE_MESSAGES.get(self.role, {})
            msg = msgs_for_role.get(action.value)
        return action, msg

    @property
    def nudge_count(self) -> int:
        return self.detector.nudge_count


# ── Quick Test ───────────────────────────────────────────────

if __name__ == "__main__":
    d = LoopDetector()

    for i in range(5):
        for call in [("paper_search", {"q": "physics"}), ("paper_search", {"q": "physics"}),
                     ("paper_search", {"q": "physics"})]:
            d.record(call[0], call[1])

    action = d.check()
    print(f"After 15 identical calls: {action.value}")

    d2 = LoopDetector()
    for i in range(3):
        d2.record("train", {"cfg": f"cfg_{i}"}, is_error=True)
    action2 = d2.check()
    print(f"After 3 training errors: {action2.value}")

    pd = PhaseLoopDetector("literature_researcher")
    for i in range(20):
        pd.record("paper_search", {"q": f"query_{i}"})
    action3, msg = pd.check()
    print(f"PhaseLoopDetector: {action3.value}, msg={msg}")
