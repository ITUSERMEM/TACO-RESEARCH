"""HallucinationGuard — Kocoro-inspired 3-layer hallucination detection.

Detects LLM fabrications:
- Layer 1: Fabricated tool call XML in text output
- Layer 2: Unverified claims of tool execution
- Layer 3: Claims of success after tool was denied

Each layer injects <system-reminder> corrections.
Max 2 nudges → force-stop after turn 3.
"""

import re
from typing import Optional

MAX_NUDGES = 2


class HallucinationGuard:
    """Three-layer hallucination detection for LLM agent output.

    Usage:
        guard = HallucinationGuard()
        nudge = guard.check(response_text, denied_tools)
        if nudge:
            messages.append({"role": "system", "content": nudge})
    """

    def __init__(self):
        self.nudge_count = 0
        self.nudges_this_turn = 0

    def new_turn(self):
        self.nudges_this_turn = 0

    def check(self, text: str, denied_tools: Optional[list[str]] = None,
              executed_tools: Optional[list[str]] = None, turn: int = 1) -> Optional[str]:
        """Check LLM output for hallucination patterns.

        Returns system-reminder nudge text if detected, None otherwise.
        """
        if self.nudge_count >= MAX_NUDGES and turn >= 3:
            return None  # already warned enough

        # ── Layer 1: Fabricated tool call XML ──
        if self._detect_fabricated_tool_xml(text):
            self.nudge_count += 1
            self.nudges_this_turn += 1
            return (
                "<system-reminder>STOP. You just attempted to fabricate tool call results. "
                "Do NOT invent tool outputs. If you need information, use a real tool call. "
                "If you already have the information, just state it without pretending to use a tool.</system-reminder>"
            )

        # ── Layer 2: Unverified claims ──
        if self._detect_unverified_claim(text, executed_tools):
            self.nudge_count += 1
            self.nudges_this_turn += 1
            return (
                "<system-reminder>You appear to claim you executed an action "
                "without providing a corresponding tool call. Please use actual tool calls "
                "to perform actions, or simply state your knowledge without fabrication.</system-reminder>"
            )

        # ── Layer 3: Success after denial ──
        if denied_tools and self._detect_success_after_denial(text, denied_tools):
            self.nudge_count += 1
            self.nudges_this_turn += 1
            return (
                "<system-reminder>You just claimed success for an action "
                f"that was denied ({denied_tools[0]}). Do not fabricate results. "
                "If a tool is denied, acknowledge the denial and suggest an alternative approach.</system-reminder>"
            )

        return None

    def needs_force_stop(self, turn: int) -> bool:
        """Check if repeated hallucination should force-stop."""
        return self.nudge_count >= MAX_NUDGES and turn >= 3

    # ── Layer 1: Fabricated XML ──

    @staticmethod
    def _detect_fabricated_tool_xml(text: str) -> bool:
        patterns = [
            r"<tool_exec[^>]*>",
            r"<tool_result[^>]*>",
            r"<function[^>]*>.*?</function>",
            r"I called (the )?\w+ (tool|function|command)",
            r"I (ran|executed|called|invoked) .*? and (got|received|the result)",
            r"Using the \w+ tool[,:]",
        ]
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                return True
        return False

    # ── Layer 2: Unverified claims ──

    @staticmethod
    def _detect_unverified_claim(text: str, executed: Optional[list[str]] = None) -> bool:
        claim_patterns = [
            r"I (searched|looked up|found|read|checked|verified|confirmed|reviewed|analyzed|downloaded)",
            r"I (opened|navigated|visited|accessed|browsed)",
            r"I (compiled|built|ran|executed) (the )?(code|script|program|test)",
            r"The (file|document|paper|code) (shows|contains|indicates|says)",
        ]
        for p in claim_patterns:
            if re.search(p, text, re.IGNORECASE):
                if not executed:
                    return True
                for exe in executed:
                    if exe.lower() in text.lower():
                        break
                else:
                    return True
        return False

    # ── Layer 3: Success after denial ──

    @staticmethod
    def _detect_success_after_denial(text: str, denied_tools: list[str]) -> bool:
        for tool in denied_tools:
            success_patterns = [
                rf"I .*(succeeded|completed|finished|done).*{re.escape(tool)}",
                rf"(the )?{re.escape(tool)} (succeeded|completed|returned|result)",
                rf"(successfully|finished) (using|running|executing) {re.escape(tool)}",
            ]
            for p in success_patterns:
                if re.search(p, text, re.IGNORECASE):
                    return True
        return False
