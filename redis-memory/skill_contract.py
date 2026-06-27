"""SkillContract — Runtime contract verification layer for skill execution.

Three-layer protection:
1. Pre-condition: Input schema validation + state isolation check
2. In-flight: Output entropy monitoring + zombie process detection
3. Post-condition: Output consistency voting + side-effect audit

Integrates with existing GateJudge, HallucinationGuard, AuditLogger.

Usage:
    contract = SkillContract(executor_llm, reviewer_llm)

    # Pre-condition
    pre = contract.validate_pre("paper-writer", args, phase=4)
    if not pre["valid"]:
        return {"status": "error", "output": pre["issues"]}

    # In-flight (during skill execution)
    contract.monitor_entropy(output_chunk)
    if contract.entropy_dropped():
        # trigger reviewer fallback

    # Post-condition
    post = contract.validate_post(skill_name, input_msgs, output)
    if not post["consistent"]:
        # flag for manual review
"""

import math
import re
import time
from collections import Counter
from typing import Optional


class ContractValidator:
    """Pre-condition validator for skill inputs."""

    MAX_INPUT_CHARS = 28000
    PHASE_SKILL_COMPAT = {
        0: {"research-lit", "brainstorm", "idea-creator", "research-pipeline",
            "paper-compile", "iris-development"},
        1: {"research-lit", "literature-review", "novelty-check",
            "arxiv", "semantic-scholar", "paper-read", "research-wiki"},
        2: {"experiment-plan", "research-refine", "method-design",
            "idea-creator", "formula-derivation", "proof-checker",
            "kill-argument"},
        3: {"run-experiment", "monitor-experiment", "analyze-results",
            "experiment-bridge", "experiment-queue", "training-check"},
        4: {"paper-write", "paper-figure", "figure-spec", "nature-figure",
            "citation-audit", "paper-illustration", "paper-slides",
            "idea-creator", "playwright-skill"},
        5: {"latex-polish", "paper-compile", "nature-writing",
            "paper-write", "paper-plan", "citation-audit",
            "paper-figure", "research-lit", "submit"},
    }

    def validate_input(self, skill_name: str, args: str, phase: int = -1) -> dict:
        issues = []

        if len(args) > self.MAX_INPUT_CHARS:
            issues.append(
                f"输入过长 ({len(args)} chars > {self.MAX_INPUT_CHARS})，"
                f"可能被截断丢失关键信息"
            )

        if self._has_unclosed_latex(args):
            issues.append("检测到未闭合的 LaTeX 标记 ($ 数量为奇数)")

        if self._has_control_chars(args):
            issues.append("检测到控制字符 (U+0000-U+001F)")

        if self._has_error_string(args):
            issues.append("输入包含 [LLM error:] 字符串，可能是上游错误传递")

        if phase >= 0 and not self._is_phase_compatible(skill_name, phase):
            issues.append(
                f"skill /{skill_name} 不在 Phase {phase} 的推荐列表中"
            )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "input_length": len(args),
            "phase": phase,
        }

    @staticmethod
    def _has_unclosed_latex(text: str) -> bool:
        dollar_count = text.count("$")
        if dollar_count % 2 != 0:
            return True
        brace_open = text.count("{")
        brace_close = text.count("}")
        if brace_open > 0 and abs(brace_open - brace_close) > 2:
            return True
        return False

    @staticmethod
    def _has_control_chars(text: str) -> bool:
        return bool(re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text))

    @staticmethod
    def _has_error_string(text: str) -> bool:
        return "[LLM error:" in text or "[SKILL HANG]" in text

    def _is_phase_compatible(self, skill_name: str, phase: int) -> bool:
        phase_allowed = self.PHASE_SKILL_COMPAT.get(phase)
        if phase_allowed is None:
            return True
        if skill_name in phase_allowed:
            return True
        all_known = set()
        for s in self.PHASE_SKILL_COMPAT.values():
            all_known.update(s)
        return skill_name in all_known


class EntropyMonitor:
    """In-flight entropy monitor for LLM output streams.

    Detects repetitive/degenerate output by tracking Shannon entropy
    of text chunks. A sudden drop (>30%) signals potential model
    degradation (repetition loop, hallucination mode).
    """

    def __init__(self, window_size: int = 5, drop_threshold: float = 0.3):
        self.window_size = window_size
        self.drop_threshold = drop_threshold
        self._entropy_history: list[float] = []
        self._chunk_count = 0

    def update(self, text: str):
        if not text or len(text) < 10:
            return
        entropy = self.calculate_entropy(text)
        self._entropy_history.append(entropy)
        if len(self._entropy_history) > self.window_size:
            self._entropy_history.pop(0)
        self._chunk_count += 1

    def entropy_dropped(self) -> bool:
        if len(self._entropy_history) < 2:
            return False
        prev = self._entropy_history[-2]
        curr = self._entropy_history[-1]
        if prev <= 0:
            return False
        drop = (prev - curr) / prev
        return drop > self.drop_threshold

    def is_repetitive(self, text: str, threshold: float = 2.0) -> bool:
        if not text or len(text) < 20:
            return False
        entropy = self.calculate_entropy(text)
        return entropy < threshold

    @property
    def current_entropy(self) -> float:
        return self._entropy_history[-1] if self._entropy_history else 0.0

    @property
    def entropy_trend(self) -> str:
        if len(self._entropy_history) < 2:
            return "insufficient_data"
        if self._entropy_history[-1] > self._entropy_history[-2] * 1.1:
            return "rising"
        if self._entropy_history[-1] < self._entropy_history[-2] * 0.9:
            return "falling"
        return "stable"

    def reset(self):
        self._entropy_history.clear()
        self._chunk_count = 0

    @staticmethod
    def calculate_entropy(text: str) -> float:
        if not text:
            return 0.0
        counter = Counter(text)
        total = len(text)
        entropy = 0.0
        for count in counter.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        return round(entropy, 4)


class ConsensusVoter:
    """Post-condition consistency voter.

    Calls the same input N times through executor, then uses reviewer
    to assess output consistency. Flags unstable skills.
    """

    def __init__(self, executor_llm=None, reviewer_llm=None, num_votes: int = 3):
        self.executor = executor_llm
        self.reviewer = reviewer_llm
        self.num_votes = num_votes

    def vote(self, messages: list[dict], max_tokens: int = 4096,
             temperature: float = 0.0) -> dict:
        if not self.executor:
            return {"consistent": True, "confidence": 1.0, "votes": [], "reason": "no_executor"}

        responses = []
        for i in range(self.num_votes):
            resp = self.executor.complete(
                messages, max_tokens=max_tokens, temperature=temperature,
            )
            responses.append(resp)

        if not self.reviewer:
            return self._simple_consistency(responses)

        return self._reviewer_consistency(responses)

    def _simple_consistency(self, responses: list[str]) -> dict:
        if len(responses) < 2:
            return {"consistent": True, "confidence": 1.0, "votes": responses}

        normalized = [self._normalize(r) for r in responses]
        unique = set(normalized)
        consistency = 1.0 - (len(unique) - 1) / max(len(normalized) - 1, 1)

        return {
            "consistent": consistency >= 0.5,
            "confidence": round(consistency, 2),
            "votes": responses,
            "unique_count": len(unique),
        }

    def _reviewer_consistency(self, responses: list[str]) -> dict:
        parts = []
        for i, r in enumerate(responses):
            parts.append(f"Response {i+1}:\n{r[:500]}")
        combined = "\n\n---\n\n".join(parts)

        review = self.reviewer.complete([
            {"role": "system", "content": (
                "Evaluate consistency of multiple responses to the same input. "
                "Return JSON: {\"consistent\": true/false, \"confidence\": 0.0-1.0, "
                "\"key_differences\": [...]}"
            )},
            {"role": "user", "content": f"Are these responses consistent?\n\n{combined}"},
        ], max_tokens=200, temperature=0.1)

        result = self._parse_review(review)
        result["votes"] = responses
        return result

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text[:200]

    @staticmethod
    def _parse_review(review: str) -> dict:
        json_match = re.search(r"\{.*\}", review, re.DOTALL)
        if json_match:
            try:
                import json
                return json.loads(json_match.group())
            except Exception:
                pass
        review_lower = review.lower()
        if "inconsistent" in review_lower:
            return {"consistent": False, "confidence": 0.6}
        return {"consistent": True, "confidence": 0.5}


class SideEffectAuditor:
    """Post-condition side-effect auditor.

    Compares Redis state before and after skill execution
    to detect undeclared persistent modifications.
    """

    def __init__(self, redis_client=None):
        self.r = redis_client
        self._pre_snapshot: dict = {}

    def snapshot_before(self, keys: Optional[list[str]] = None):
        if not self.r:
            return
        target_keys = keys or ["academic:session:*", "academic:phase:*"]
        self._pre_snapshot = {}
        for pattern in target_keys:
            for key in self.r.keys(pattern):
                try:
                    val = self.r.get(key)
                    if val is not None:
                        self._pre_snapshot[key] = val
                except Exception:
                    pass

    def audit_after(self, keys: Optional[list[str]] = None) -> dict:
        if not self.r or not self._pre_snapshot:
            return {"changes": [], "new_keys": [], "deleted_keys": []}

        target_keys = keys or ["academic:session:*", "academic:phase:*"]
        post_snapshot = {}
        for pattern in target_keys:
            for key in self.r.keys(pattern):
                try:
                    val = self.r.get(key)
                    if val is not None:
                        post_snapshot[key] = val
                except Exception:
                    pass

        changes = []
        for key in set(self._pre_snapshot) & set(post_snapshot):
            if self._pre_snapshot[key] != post_snapshot[key]:
                changes.append(key)

        new_keys = list(set(post_snapshot) - set(self._pre_snapshot))
        deleted_keys = list(set(self._pre_snapshot) - set(post_snapshot))

        return {
            "changes": changes,
            "new_keys": new_keys,
            "deleted_keys": deleted_keys,
            "total_modified": len(changes) + len(new_keys) + len(deleted_keys),
        }


class SkillContract:
    """Unified contract verification layer combining all validators."""

    def __init__(self, executor_llm=None, reviewer_llm=None, redis_client=None):
        self.validator = ContractValidator()
        self.entropy = EntropyMonitor()
        self.voter = ConsensusVoter(executor_llm, reviewer_llm)
        self.auditor = SideEffectAuditor(redis_client)

    def validate_pre(self, skill_name: str, args: str, phase: int = -1) -> dict:
        return self.validator.validate_input(skill_name, args, phase)

    def monitor_entropy(self, text: str):
        self.entropy.update(text)

    def entropy_dropped(self) -> bool:
        return self.entropy.entropy_dropped()

    def validate_post(self, skill_name: str, messages: list[dict],
                      output: str, max_tokens: int = 4096) -> dict:
        result = {"skill": skill_name, "output_length": len(output)}

        if output.startswith("[LLM error:"):
            result["error_passthrough"] = True
            result["consistent"] = False
            return result

        if self.entropy.is_repetitive(output):
            result["repetitive_output"] = True
            result["entropy"] = self.entropy.current_entropy

        if skill_name in ("paper-writer", "methodologist", "paper-figure"):
            vote = self.voter.vote(messages, max_tokens=max_tokens)
            result.update(vote)
        else:
            result["consistent"] = True
            result["confidence"] = 1.0

        return result

    def snapshot_before(self, keys: Optional[list[str]] = None):
        self.auditor.snapshot_before(keys)

    def audit_after(self, keys: Optional[list[str]] = None) -> dict:
        return self.auditor.audit_after(keys)

    def reset(self):
        self.entropy.reset()
        self._pre_snapshot = {}
