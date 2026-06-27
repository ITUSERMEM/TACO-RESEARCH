"""SkillDiscovery — Kocoro-inspired automatic skill recommendation.

Uses a lightweight phrase-based pre-filter + optional small LLM call
to match user intent with available skills.

Pre-filter scoring:
- Anchor words (skill name match) = 100 points
- Domain nouns (research keywords) = 60 points
- Action verbs = 25 points
- Veto words = -60 points
"""

import re
import time
from typing import Optional

SKILL_REGISTRY = [
    {
        "name": "literature-review",
        "description": "Search and analyze academic papers, find related work",
        "keywords": ["paper", "literature", "survey", "related work", "research gap"],
        "agents": ["literature-researcher"],
    },
    {
        "name": "experiment-bridge",
        "description": "Deploy and run ML experiments on GPU",
        "keywords": ["experiment", "train", "GPU", "run model", "evaluate"],
        "agents": ["experimenter"],
    },
    {
        "name": "novelty-check",
        "description": "Check research idea novelty against existing literature",
        "keywords": ["novelty", "new idea", "original", "contribution"],
        "agents": ["academic-reviewer"],
    },
    {
        "name": "paper-write",
        "description": "Draft LaTeX paper sections from outlines",
        "keywords": ["write paper", "draft", "LaTeX", "section", "manuscript"],
        "agents": ["paper-writer"],
    },
    {
        "name": "citation-audit",
        "description": "Verify bibliography entries and citation context",
        "keywords": ["citation", "reference", "bibtex", "bibliography"],
        "agents": ["citation-auditor"],
    },
    {
        "name": "code-review",
        "description": "Review code for bugs and style issues",
        "keywords": ["code review", "bug", "refactor", "test", "debug"],
        "agents": ["code-engineer"],
    },
    {
        "name": "figure-generation",
        "description": "Generate publication-quality figures",
        "keywords": ["figure", "plot", "chart", "visualization", "diagram"],
        "agents": ["visualization-designer"],
    },
]


class SkillDiscovery:
    """Match user intent to available skills.

    Two-stage matching:
    1. Phrase-based pre-filter (fast, no LLM needed)
    2. Optional small LLM confirmation (if pre-filter ambiguous)
    """

    def __init__(self, registry: Optional[list[dict]] = None):
        self.registry = registry or SKILL_REGISTRY

    def match(self, text: str, llm=None) -> list[dict]:
        """Find skills matching user intent.

        Args:
            text: user message text
            llm: optional LLMClient for deep matching

        Returns:
            list of matched skill dicts with score
        """
        text_lower = text.lower()

        scored = []
        for skill in self.registry:
            score = self._score(text_lower, skill)
            if score > 0:
                scored.append({**skill, "score": score})

        scored.sort(key=lambda s: s["score"], reverse=True)

        if scored and scored[0]["score"] >= 60:
            return scored[:3]

        if llm and text:
            try:
                matched = self._llm_match(text, llm)
                if matched:
                    for m in matched:
                        if not any(s["name"] == m["name"] for s in scored):
                            scored.append(m)
            except Exception:
                pass

        return scored[:3]

    def _score(self, text_lower: str, skill: dict) -> int:
        score = 0

        # Anchor: skill name in text
        if skill["name"].lower() in text_lower:
            score += 100

        # Keywords
        for kw in skill.get("keywords", []):
            if kw.lower() in text_lower:
                score += 60

        # Agent names
        for agent in skill.get("agents", []):
            if agent.replace("-", " ") in text_lower:
                score += 25

        # Veto: if text mentions a totally different domain
        veto_words = ["unrelated", "different topic", "not about"]
        for v in veto_words:
            if v in text_lower:
                score -= 60

        return max(score, 0)

    def _llm_match(self, text: str, llm) -> list[dict]:
        skill_names = ", ".join(s["name"] for s in self.registry)
        prompt = (
            f"User message: {text[:500]}\n"
            f"Available skills: {skill_names}\n"
            "Return the names of the 1-3 most relevant skills, comma-separated, no explanation."
        )
        response = llm.review([
            {"role": "system", "content": "You match user requests to skills. Output only skill names."},
            {"role": "user", "content": prompt},
        ], max_tokens=200, temperature=0.1)

        matched = []
        response_lower = response.lower()
        for skill in self.registry:
            if skill["name"] in response_lower:
                matched.append({**skill, "score": 80})
        return matched

    def build_skill_block(self, matched: list[dict]) -> str:
        """Build <available_skills> block from matched skills."""
        if not matched:
            return ""
        parts = ["<available_skills>"]
        for s in matched:
            parts.append(f"- {s['name']}: {s['description']}")
        parts.append("</available_skills>")
        return "\n".join(parts)
