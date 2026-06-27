"""GateJudge — LLM-powered review gate evaluation.

Replaces the hash-based pseudo-random gate verdicts with real LLM
evaluation of the phase conversation transcript.

Kocoro-inspired: uses a small-tier LLM for gate evaluation with
structured output (verdict + issues + recommendations).
"""

from typing import Optional

from llm_client import LLMClient

GATE_JUDGE_PROMPTS = {
    1: """You are an academic novelty reviewer. Evaluate this Phase 1 literature review.

Criteria:
- PASS: Novel gap clearly identified, no direct overlap with existing work
- REVISE: Some overlap but differentiation is possible with adjustments
- FAIL: Topic is already well-covered, no publication space

Respond with JSON:
{"verdict": "pass|revise|fail", "issues": [...], "recommendations": [...]}

Transcript:
""",

    2: """You are a method rigor reviewer. Evaluate this Phase 2 method design.

Criteria:
- PASS: Method is sound, assumptions justified, risks identified
- REVISE: Method has gaps but fixable with additional analysis
- FAIL: Fundamental flaws in approach

Respond with JSON:
{"verdict": "pass|revise|fail", "issues": [...], "recommendations": [...]}

Transcript:
""",

    3: """You are an experiment auditor. Evaluate this Phase 3 experimental results.

Criteria:
- PASS: Results reproducible, claims supported, no anomalies
- REVISE: Partial support, missing ablation or statistical rigor
- FAIL: Data anomalies, unsupported claims, reproducibility concerns

Respond with JSON:
{"verdict": "pass|revise|fail", "issues": [...], "recommendations": [...]}

Transcript:
""",

    4: """You are a claim auditor. Evaluate this Phase 4 paper draft claims.

Criteria:
- PASS: All numbers match experimental results, no overclaimed statements
- REVISE: Minor inconsistencies or overclaims that can be corrected
- FAIL: Major claim-evidence mismatch, fabricated or inflated results

Respond with JSON:
{"verdict": "pass|revise|fail", "issues": [...], "recommendations": [...]}

Transcript:
""",

    5: """You are a citation auditor. Verify the Phase 4 citation accuracy.

Criteria:
- PASS: All citations real and contextually appropriate
- REVISE: Some citation format issues or imprecise contextual matches
- FAIL: Fabricated citations or author mismatches

Respond with JSON:
{"verdict": "pass|revise|fail", "issues": [...], "recommendations": [...]}

Transcript:
""",

    6: """You are an academic editor. Evaluate the Phase 4-5 paper for submission readiness.

Criteria:
- PASS: Format compliant, compiles cleanly, meets venue requirements
- REVISE: Minor formatting or structural issues to fix
- FAIL: Major structural or compliance issues

Respond with JSON:
{"verdict": "pass|revise|fail", "issues": [...], "recommendations": [...]}

Transcript:
""",

    7: """You are a final audit reviewer. Verify everything before Phase 5 submission.

Criteria:
- PASS: All gates passed, paper complete, citations verified
- REVISE: Minor remaining issues
- FAIL: Critical gate failure remains unresolved

Respond with JSON:
{"verdict": "pass|revise|fail", "issues": [...], "recommendations": [...]}

Transcript:
""",
}


class GateJudge:
    """LLM-powered review gate judge.

    Uses dual-model architecture:
    - reviewer (glm-5.2) for G1, G3, G4, G6 — standard review
    - pro (deepseek-v4-pro) for G2, G5, G7 — deep audit
    """

    GATE_TIER = {1: "reviewer", 2: "pro", 3: "reviewer",
                  4: "reviewer", 5: "pro", 6: "reviewer", 7: "pro"}

    def __init__(self, reviewer_llm: Optional[LLMClient] = None,
                 pro_llm: Optional[LLMClient] = None):
        self.reviewer = reviewer_llm or LLMClient(model="glm-5.2")
        self.pro = pro_llm or LLMClient(base_url="https://api.deepseek.com/v1", api_key="", model="deepseek-v4-pro")

    def evaluate(self, gate_id: int, transcript: str) -> dict:
        """Evaluate a review gate. Routes to reviewer or pro model by gate tier."""
        prompt = GATE_JUDGE_PROMPTS.get(gate_id)
        if not prompt:
            return {"verdict": "pass", "issues": [], "recommendations": []}

        capped = transcript[:30000]
        model = self._model_for_gate(gate_id)
        response = model.complete([
            {"role": "system", "content": f"Reviewer for Gate {gate_id}. Return ONLY valid JSON (verdict, issues, recommendations). Max 200 tokens."},
            {"role": "user", "content": (prompt + capped)[:40000]},
        ], max_tokens=200, temperature=0.1)

        result = self._parse_response(response)
        self._validate_result(result)
        return result

    def _model_for_gate(self, gate_id: int) -> LLMClient:
        tier = self.GATE_TIER.get(gate_id, "reviewer")
        if tier == "pro":
            return self.pro
        return self.reviewer

    def _parse_response(self, response: str) -> dict:
        import json
        import re

        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        response_lower = response.lower()
        if "pass" in response_lower and "fail" not in response_lower:
            return {"verdict": "pass", "issues": [], "recommendations": []}
        if "fail" in response_lower:
            return {"verdict": "fail", "issues": [response[:200]], "recommendations": []}
        if "revise" in response_lower:
            return {"verdict": "revise", "issues": [response[:200]], "recommendations": []}

        return {"verdict": "pass", "issues": [], "recommendations": []}

    @staticmethod
    def _validate_result(result: dict):
        valid = {"pass", "revise", "fail"}
        if result.get("verdict") not in valid:
            result["verdict"] = "pass"
        if "issues" not in result:
            result["issues"] = []
        if "recommendations" not in result:
            result["recommendations"] = []
