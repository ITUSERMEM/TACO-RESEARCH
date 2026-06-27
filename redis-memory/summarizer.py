"""Two-Phase Summarizer for Phase Transitions.

Kocoro-inspired GenerateSummary with:
- Phase 1 (<analysis>): Chronological walkthrough of the phase
- Phase 2 (<summary>): 5 labeled sections for phase transition

Usage:
    summarizer = PhaseSummarizer()
    summary = summarizer.summarize(messages, phase=1)
"""

import json
from datetime import datetime, timezone
from typing import Optional

SUMMARY_CAP_CHARS = 300_000


PHASE_SUMMARY_TEMPLATES = {
    0: {
        "title": "Idea Discovery Summary",
        "sections": [
            "Current problem & gap",
            "Proposed approach & rationale",
            "Alternative directions considered",
            "Open questions / assumptions",
        ],
    },
    1: {
        "title": "Literature Review Summary",
        "sections": [
            "Papers found & key findings",
            "Existing methods categorized",
            "Gap in literature confirmed",
            "Research direction refined",
            "Open questions",
        ],
    },
    2: {
        "title": "Method Design Summary",
        "sections": [
            "Architecture decisions",
            "Training strategy",
            "Ablation design",
            "Implementation checklist",
            "Risk areas",
        ],
    },
    3: {
        "title": "Experiment Summary",
        "sections": [
            "Results achieved",
            "Failed experiments & lessons",
            "Visualizations created",
            "Remaining experiments",
        ],
    },
    4: {
        "title": "Coding Summary",
        "sections": [
            "Modules implemented",
            "Dependencies added",
            "Tests written & passing",
            "Integration status",
        ],
    },
    5: {
        "title": "Paper Draft Summary",
        "sections": [
            "Section completion status",
            "Citation coverage",
            "Figure alignment",
            "Remaining writing tasks",
        ],
    },
}


class PhaseSummarizer:
    """Two-phase summarization for Phase→Phase transitions.

    Phase 1 (<analysis>): Chronological walkthrough identifying:
    - User corrections & decisions
    - Files read / modified
    - Errors & resolutions
    - Skills activated

    Phase 2 (<summary>): Structured output with templates per phase.

    Uses LLM for real summarization (not keyword matching).
    """

    def __init__(self, max_input_chars: int = SUMMARY_CAP_CHARS, llm=None):
        self.max_input_chars = max_input_chars
        self.llm = llm  # reviewer-tier LLMClient (glm-5.2), set externally

    def summarize(self, messages: list[dict], phase: int) -> dict:
        """Generate complete two-phase summary.

        Returns:
            {"analysis": str, "summary": str, "template": str}
        """
        transcript = self._cap_transcript(messages)
        analysis = self._phase1_analysis(transcript, phase)
        summary = self._phase2_summary(transcript, phase, analysis)
        template = self._get_template_text(phase)

        return {
            "analysis": analysis,
            "summary": summary,
            "template": template,
        }

    # ── Phase 1: Chronological Analysis ──

    def _phase1_analysis(self, transcript: str, phase: int) -> str:
        if self.llm:
            prompt = (
                f"Analyze this Phase {phase} conversation transcript. Identify:\n"
                "1. Key decisions made and rationale\n"
                "2. Corrections or changes in direction\n"
                "3. Files/sources read or modified\n"
                "4. Errors encountered and resolutions\n"
                "5. Skills or tools activated\n\n"
                f"<transcript>\n{transcript[:100000]}\n</transcript>\n\n"
                "Return in <analysis> tags with labeled sections."
            )
            result = self.llm.complete([
                {"role": "system", "content": "You are a research process analyst."},
                {"role": "user", "content": prompt},
            ], max_tokens=1500, temperature=0.2)
            return result

        messages = transcript.split("\n---MESSAGE---\n")
        analysis_parts = [f"<analysis phase=\"{phase}\">\n"]
        analysis_parts.append(f"Messages analyzed: {len(messages)}\n")
        analysis_parts.append("\n</analysis>")
        return "".join(analysis_parts)

    # ── Phase 2: Structured Summary ──

    def _phase2_summary(self, transcript: str, phase: int, analysis: str) -> str:
        template = PHASE_SUMMARY_TEMPLATES.get(phase)
        if not template:
            return f"<summary><phase>{phase}</phase><status>no-template</status></summary>"

        if self.llm:
            sections_desc = "\n".join(f"- {s}" for s in template["sections"])
            prompt = (
                f"Generate a structured Phase {phase} summary ({template['title']}).\n"
                f"Sections to fill:\n{sections_desc}\n\n"
                f"<transcript>\n{transcript[:100000]}\n</transcript>\n\n"
                f"<analysis>\n{analysis[:5000]}\n</analysis>\n\n"
                f"Return in <summary> tags with each section populated."
            )
            result = self.llm.complete([
                {"role": "system", "content": "You are a research summary writer."},
                {"role": "user", "content": prompt},
            ], max_tokens=2000, temperature=0.2)
            return result

        parts = [f"<summary phase=\"{phase}\">"]
        parts.append(f"<title>{template['title']}</title>")
        parts.append(f"<generated_at>{datetime.now(timezone.utc).isoformat()}</generated_at>")
        parts.append("</summary>")
        return "\n".join(parts)

    # ── Helpers ──

    def _cap_transcript(self, messages: list[dict]) -> str:
        """Build transcript from messages, capped at max_input_chars."""
        parts = []
        total = 0

        for msg in messages[-50:]:
            content = msg.get("content", "")
            if isinstance(content, dict):
                content = json.dumps(content, ensure_ascii=False)
            elif not isinstance(content, str):
                content = str(content)

            block = f"ROLE: {msg.get('role', 'unknown')}\n{content}\n---MESSAGE---\n"
            total += len(block)

            if total > self.max_input_chars:
                break
            parts.append(block)

        return "".join(parts)

    def _get_template_text(self, phase: int) -> str:
        t = PHASE_SUMMARY_TEMPLATES.get(phase)
        if not t:
            return ""
        sections = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(t["sections"]))
        return f"## {t['title']}\n\n{sections}\n"


# ── Quick Test ───────────────────────────────────────────────

if __name__ == "__main__":
    msgs = [
        {"role": "user", "content": "We should investigate physics-informed methods."},
        {"role": "assistant", "content": "Decision: Use PINN-based approach with spectral features."},
        {"role": "user", "content": "Actually, that's not right. We need few-shot capability too."},
        {"role": "assistant", "content": "Correction: Design a meta-learning framework with physical priors."},
        {"role": "assistant", "content": "→ Skill experiment-bridge deployed for GPU experiments."},
    ]

    s = PhaseSummarizer()
    result = s.summarize(msgs, phase=1)

    print("=== Analysis ===")
    print(result["analysis"][:300])
    print("\n=== Summary ===")
    print(result["summary"][:300])
    print("\n=== Template ===")
    print(result["template"][:200])
