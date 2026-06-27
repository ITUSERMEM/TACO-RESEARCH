"""Cache Strategy — 4 breakpoints + TTL routing for LLM prompt caching.

Kocoro-inspired cache strategy:
- 4 cache_control breakpoints for maximum cache hit rate
- TTL routing by academic source type
- Byte-stability enforcement for cross-session cache hits
"""

from typing import Optional

# 4 breakpoints matching Kocoro's anthropic cache strategy
BREAKPOINTS = {
    1: {
        "name": "system_stable",
        "contents": [
            "agent_role_persona",
            "institution_guidelines",
            "core_team_rules",
        ],
        "description": "Cross-session stable persona + tools + rules",
    },
    2: {
        "name": "tools[-1]",
        "contents": [
            "all_tool_schemas",
        ],
        "description": "Last tool definition (caches all tool schemas)",
    },
    3: {
        "name": "user_1.cache_break",
        "contents": [
            "project_specific_context",
            "current_phase_goal",
            "team_composition",
        ],
        "description": "Per-session stable instructions + sticky context",
    },
    4: {
        "name": "rolling[-2]",
        "contents": [
            "per_turn_context",
        ],
        "description": "Per-turn rolling cache point",
    },
}

# TTL routing by academic source type (seconds)
TTL_ROUTING = {
    # Human-interactive sessions: long TTL for cache reuse
    "academic_director": 3600,
    "academic_literature": 3600,
    "academic_paper_writing": 3600,
    "academic_review": 3600,

    # One-shot / automated: short TTL
    "academic_code": 300,
    "academic_experiment": 300,
    "academic_heartbeat": 300,
    "academic_subagent": 300,
    "academic_schedule": 300,
}


class CacheStrategy:
    """Prompt cache strategy for academic multi-agent team."""

    @staticmethod
    def get_ttl(source: str) -> int:
        return TTL_ROUTING.get(source, 600)

    @staticmethod
    def get_breakpoint(level: int) -> Optional[dict]:
        return BREAKPOINTS.get(level)

    @staticmethod
    def build_system_prompt(
        role: str,
        project_context: str = "",
        phase_goal: str = "",
    ) -> str:
        """Build a cache-optimized system prompt with breakpoints.

        Structure:
        [BP#1] Stable persona + tools (hourly refresh)
        [BP#3] Per-session context (hourly refresh)
        [BP#4] Per-turn query
        """
        parts = []

        parts.append(f"You are the {role} in an academic research team.\n")
        parts.append("Follow the established team protocols.\n")

        parts.append("<!-- cache_break -->\n")

        if project_context:
            parts.append(f"Project: {project_context}\n")
        if phase_goal:
            parts.append(f"Current objective: {phase_goal}\n")

        parts.append("<!-- cache_break -->\n")

        return "".join(parts)

    @staticmethod
    def estimate_token_count(text: str) -> int:
        return int(len(text) * 1.3)
