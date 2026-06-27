"""MemoryPreflight — Phase-transition context injection.

Kocoro-inspired MemoryPreflightFunc: injects relevant long-term memories
as <private_memory> blocks before each Phase execution, providing
cross-phase context continuity without polluting the main conversation.

Usage:
    preflight = MemoryPreflight(mem)
    ctx = preflight.build_context(phase=2, role="experimenter")
    # ctx contains "<private_memory>...</private_memory>"
"""

from datetime import datetime, timezone
from typing import Optional

from agent_memory import AgentMemory


PHASE_MEMORY_TOPICS = {
    0: [],
    1: ["project-goal", "initial-direction"],
    2: ["literature-findings", "gap-analysis", "phase-1-summary"],
    3: ["method-design", "ablation-plan", "phase-2-summary"],
    4: ["experiment-results", "failed-experiments", "phase-3-summary"],
    5: ["code-modules", "test-results", "phase-4-summary"],
}

ROLE_MEMORY_TYPES = {
    "research-director": ["decision", "phase-summary", "gate-result"],
    "literature-researcher": ["literature-finding", "search-result"],
    "methodologist": ["method-decision", "architecture-choice"],
    "experimenter": ["experiment-result", "failed-config"],
    "code-engineer": ["module-implemented", "test-result"],
    "paper-writer": ["section-complete", "citation-found"],
    "academic-reviewer": ["review-verdict", "gate-pass", "gate-revise"],
}


class MemoryPreflight:
    """Inject phase-relevant long-term memories as private context blocks.

    Like Kocoro's MemoryPreflightFunc:
    - Fail-silent: returns empty context on error
    - ForceHelper: can force compilation of context even on first call
    - Injected between cache_break and user payload
    - Stripped from summaries before persistence
    """

    MAX_MEMORIES = 10

    def __init__(self, mem: AgentMemory):
        self.mem = mem

    def build_context(
        self,
        phase: int = 0,
        role: str = "default",
        query: str = "",
        force: bool = False,
        max_items: int = MAX_MEMORIES,
    ) -> str:
        """Build <private_memory> block for phase transition.

        Returns empty string if nothing relevant found (fail-silent).
        """
        topics = PHASE_MEMORY_TOPICS.get(phase, [])
        memory_types = ROLE_MEMORY_TYPES.get(role, [])

        memories = []
        seen = set()

        if topics:
            for topic in topics:
                results = self.mem.search_long_term(
                    query="*",
                    topics=[topic],
                    k=max_items,
                )
                for m in results:
                    mid = m.get("id", "")
                    if mid and mid not in seen:
                        seen.add(mid)
                        memories.append(m)

        if memory_types:
            for mt in memory_types:
                results = self.mem.search_long_term(
                    query="*",
                    memory_type=mt,
                    k=max_items,
                )
                for m in results:
                    mid = m.get("id", "")
                    if mid and mid not in seen:
                        seen.add(mid)
                        memories.append(m)

        if query and not memories:
            results = self.mem.search_long_term(query=query, k=3)
            for m in results:
                mid = m.get("id", "")
                if mid and mid not in seen:
                    seen.add(mid)
                    memories.append(m)

        if not memories:
            return ""

        memories = sorted(memories, key=lambda x: x.get("timestamp", 0), reverse=True)[:max_items]

        parts = ["<private_memory>"]
        parts.append(f"<phase>{phase}</phase>")
        parts.append(f"<role>{role}</role>")
        parts.append(f"<generated>{datetime.now(timezone.utc).isoformat()}</generated>")

        for m in memories:
            content = m.get("content", "")
            mtype = m.get("memoryType", "unknown")
            if content:
                content = content[:500]
                parts.append(f"<memory type=\"{mtype}\">{content}</memory>")

        parts.append("</private_memory>")
        return "\n".join(parts)

    @staticmethod
    def strip_private_memory(text: str) -> str:
        """Remove <private_memory> blocks from text (for summaries/saving)."""
        import re
        result = re.sub(r"<private_memory>.*?</private_memory>", "", text, flags=re.DOTALL)
        return result.strip()

    @staticmethod
    def has_private_memory(text: str) -> bool:
        return "<private_memory>" in text


class MemoryPreflightTrace:
    """Audit trace for memory preflight operations.

    Like Kocoro's MemoryPreflightTrace — records statistics without
    exposing actual memory content.
    """

    def __init__(self):
        self.attempted = False
        self.queried = False
        self.results_count = 0
        self.context_returned = False
        self.context_injected = False
        self.error_class: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "attempted": self.attempted,
            "queried": self.queried,
            "results_count": self.results_count,
            "context_returned": self.context_returned,
            "context_injected": self.context_injected,
            "error_class": self.error_class,
        }
