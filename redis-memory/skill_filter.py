"""SkillFilter — Kocoro-inspired per-skill tool filtering.

Skills declare `allowed-tools` lists. When a skill is active:
- Only tools in the skill's allowlist can be called
- SkillExempt tools (think, tool_search, use_skill) bypass filter
- No active skill → all tools allowed (normal mode)
"""

from typing import Optional

SKILL_EXEMPT_TOOLS = {"think", "tool_search", "use_skill"}

SKILL_TOOL_ALLOWLISTS: dict[str, set[str]] = {
    "literature-review": {"paper_search", "semantic_scholar", "arxiv", "fetch_paper",
                           "read_file", "search", "list", "open"},
    "experiment-bridge": {"bash", "file_read", "file_write", "read_file", "write_file",
                           "http", "gpustat", "nvidia_smi"},
    "novelty-check": {"paper_search", "semantic_scholar", "arxiv", "read_file"},
    "paper-write": {"read_file", "write_file", "file_write", "bash", "compile"},
    "citation-audit": {"read_file", "search", "open", "http"},
    "code-review": {"read_file", "bash", "grep", "search"},
    "figure-generation": {"bash", "file_write", "read_file"},
    "method-design": {"read_file", "search", "write_file"},
    "data-analysis": {"bash", "read_file", "http", "python3"},
}


class SkillFilter:
    """Filter tool calls based on active skill allowlists.

    Usage:
        filter = SkillFilter(active_skill="literature-review")
        allowed = filter.check("bash")  # False
    """

    def __init__(self, active_skill: Optional[str] = None):
        self.active_skill = active_skill

    def check(self, tool_name: str) -> bool:
        """Check if a tool is allowed by the active skill."""
        if tool_name in SKILL_EXEMPT_TOOLS:
            return True
        if not self.active_skill:
            return True

        allowlist = SKILL_TOOL_ALLOWLISTS.get(self.active_skill)
        if allowlist is None:
            return True

        return tool_name in allowlist

    @staticmethod
    def register_skill_allowlist(skill_name: str, tools: list[str]):
        """Register or update a skill's tool allowlist."""
        SKILL_TOOL_ALLOWLISTS[skill_name] = set(tools)


class UnattendedApproval:
    """Approval rules for unattended (scheduled/heartbeat) runs.

    Like Kocoro's DisallowsUnattendedAutoApproval:
    Some tools always require approval even in unattended mode.
    """

    DISALLOWED_UNATTENDED = {
        "bash", "file_write", "http", "pip_install",
        "npm_install", "git_push", "git_merge", "docker_run",
        "kubectl_apply", "kubectl_delete",
    }

    @classmethod
    def requires_approval(cls, tool_name: str, unattended: bool = True) -> bool:
        if not unattended:
            return False
        return tool_name in cls.DISALLOWED_UNATTENDED

    @classmethod
    def add_restricted(cls, tool_name: str):
        cls.DISALLOWED_UNATTENDED.add(tool_name)
