"""Complexity Router — Task complexity analysis and strategy selection.

Shannon-inspired: computes a 0-1 complexity score for each task,
then routes to the appropriate execution strategy:
  < 0.3: Simple    (one LLM call, no tools)
  0.3-0.6: ReAct   (LLM + tool calls)
  > 0.6: Research  (multi-step, multi-agent, deep analysis)
"""

import math
from typing import Optional

from model_registry import ModelRegistry


class ComplexityRouter:
    """Route tasks to execution strategies based on complexity analysis.

    Usage:
        router = ComplexityRouter()
        strategy = router.route("Literature review on transformer fault diagnosis")
        # → {"strategy": "react", "tier": "medium", "max_iterations": 5}
    """

    STRATEGIES = {
        "simple":   {"max_iterations": 1, "description": "Single LLM call, no tools"},
        "react":    {"max_iterations": 5, "description": "LLM + tool calls, loop detection"},
        "research": {"max_iterations": 10, "description": "Multi-agent, deep analysis, review gates"},
    }

    def __init__(self, registry: Optional[ModelRegistry] = None):
        self.registry = registry or ModelRegistry()

    def compute(self, task: str) -> float:
        """Compute complexity score 0-1 for a task string."""
        if not task:
            return 0.0

        score = 0.0
        task_lower = task.lower()

        # Length factor (up to 0.4)
        length_score = min(len(task) / 500, 1.0) * 0.4
        score += length_score

        # Keyword factor (up to 0.3)
        high_complexity = {"experiment", "train", "implement", "analyze",
                          "compare", "evaluate", "optimize", "design",
                          "derive", "prove"}
        medium_complexity = {"review", "search", "summarize", "write",
                            "literature", "method", "propose"}

        words = set(task_lower.split())
        high = len(words & high_complexity)
        med = len(words & medium_complexity)
        keyword_score = min(high * 0.15 + med * 0.08, 0.3)
        score += keyword_score

        # Domain factor (up to 0.3)
        research_domains = {"bearing", "fault", "diagnosis", "vibration",
                           "rotating", "machinery", "mechanical", "signal",
                           "physical", "prior", "llm", "transformer", "attention",
                           "meta-learning", "few-shot", "domain", "generalization",
                           "transfer", "multi-modal", "fusion"}
        domain_overlap = len(words & research_domains)
        domain_score = min(domain_overlap * 0.06, 0.3)
        score += domain_score

        return round(min(score, 1.0), 2)

    def route(self, task: str) -> dict:
        """Determine execution strategy from task complexity."""
        complexity = self.compute(task)

        if complexity < 0.3:
            strategy = "simple"
            tier = "small"
        elif complexity < 0.6:
            strategy = "react"
            tier = "medium"
        else:
            strategy = "research"
            tier = "large"

        config = self.STRATEGIES[strategy]
        return {
            "strategy": strategy,
            "complexity": complexity,
            "tier": tier,
            "max_iterations": config["max_iterations"],
            "description": config["description"],
        }

    def select_agents(self, strategy: str) -> list[str]:
        """Select agent roles based on strategy."""
        if strategy == "simple":
            return ["literature-researcher"]
        elif strategy == "react":
            return ["literature-researcher", "methodologist",
                    "experimenter", "paper-writer"]
        else:
            return ["literature-researcher", "methodologist",
                    "method-reviewer", "experimenter",
                    "academic-reviewer", "paper-writer"]

    def register_preset(self, name: str, strategy_config: dict):
        """Register a named preset strategy."""
        self.STRATEGIES[name] = strategy_config
