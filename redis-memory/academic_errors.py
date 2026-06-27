"""AcademicError — Hierarchical exception system for the academic team.

Pattern:
  AcademicError
  ├── LLMError        (API call failures)
  ├── SkillError      (skill execution failures)
  ├── GateError       (review gate failures)
  ├── PipelineError   (Phase pipeline failures)
  └── ConfigError     (configuration failures)
"""

from typing import Optional


class AcademicError(Exception):
    """Base exception for all academic team errors."""

    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        self.code = code
        self.details = details or {}
        super().__init__(f"[{code}] {message}")


class LLMError(AcademicError):
    """LLM API call failed (timeout, auth, rate limit)."""

    @classmethod
    def timeout(cls, model: str, elapsed: float):
        return cls("LLM_TIMEOUT", f"{model} timed out after {elapsed:.0f}s", {"model": model, "elapsed": elapsed})

    @classmethod
    def auth(cls, model: str):
        return cls("LLM_AUTH", f"{model} authentication failed", {"model": model})

    @classmethod
    def rate_limit(cls, model: str):
        return cls("LLM_RATE_LIMIT", f"{model} rate limited", {"model": model})

    @classmethod
    def empty(cls, model: str):
        return cls("LLM_EMPTY", f"{model} returned empty response", {"model": model})


class SkillError(AcademicError):
    """Skill execution failed."""

    @classmethod
    def timeout(cls, skill: str, elapsed: float):
        return cls("SKILL_TIMEOUT", f"{skill} timed out after {elapsed:.0f}s", {"skill": skill, "elapsed": elapsed})

    @classmethod
    def not_found(cls, skill: str):
        return cls("SKILL_NOT_FOUND", f"Skill {skill} not found", {"skill": skill})

    @classmethod
    def hang(cls, skill: str, cmd: str, partial_output: str):
        return cls("SKILL_HANG", f"{skill} hung for 30s", {"skill": skill, "cmd": cmd[:200], "output": partial_output[:500]})


class GateError(AcademicError):
    """Review gate evaluation failed."""

    @classmethod
    def llm_failed(cls, gate_id: int, detail: str):
        return cls("GATE_LLM_FAIL", f"Gate {gate_id}: {detail}", {"gate": gate_id})

    @classmethod
    def invalid_verdict(cls, gate_id: int, verdict: str):
        return cls("GATE_INVALID", f"Gate {gate_id}: invalid verdict {verdict}", {"gate": gate_id, "verdict": verdict})


class PipelineError(AcademicError):
    """Phase pipeline execution failed."""

    @classmethod
    def phase_failed(cls, phase: int, detail: str):
        return cls("PIPELINE_PHASE_FAIL", f"Phase {phase}: {detail}", {"phase": phase})

    @classmethod
    def stale_state(cls, age: float):
        return cls("PIPELINE_STALE", f"Stale pipeline state ({age:.0f}s old)", {"age": age})


class ConfigError(AcademicError):
    """Configuration error."""

    @classmethod
    def missing_key(cls, key: str):
        return cls("CONFIG_MISSING_KEY", f"Missing config key: {key}", {"key": key})

    @classmethod
    def invalid_yaml(cls, path: str, error: str):
        return cls("CONFIG_INVALID_YAML", f"Invalid YAML in {path}: {error}", {"path": path})
