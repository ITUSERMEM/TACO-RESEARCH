"""Event System — Unified event types and emitter for the academic team.

All pipeline events are typed (EventType enum) and carry structured payloads.
Telegram progress, audit logs, and monitoring all consume the same event stream.

Usage:
    emitter = EventEmitter(redis_client)
    emitter.emit(EventType.PHASE_STARTED, phase=1, phase_label="文献调研")
    emitter.emit(EventType.AGENT_ACTIVATED, agent="literature-researcher")
"""

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_FAILED = "pipeline_failed"

    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_FAILED = "phase_failed"

    AGENT_ACTIVATED = "agent_activated"
    AGENT_SKILL_SELECTED = "agent_skill_selected"
    AGENT_SKILL_STARTED = "agent_skill_started"
    AGENT_SKILL_COMPLETED = "agent_skill_completed"
    AGENT_SKILL_FAILED = "agent_skill_failed"
    AGENT_SKILL_HUNG = "agent_skill_hung"
    AGENT_COMPLETED = "agent_completed"

    GATE_STARTED = "gate_started"
    GATE_PASSED = "gate_passed"
    GATE_REVISED = "gate_revised"
    GATE_FAILED = "gate_failed"

    LLM_CALL_STARTED = "llm_call_started"
    LLM_CALL_COMPLETED = "llm_call_completed"
    LLM_CALL_FAILED = "llm_call_failed"


class EventEmitter:
    """Publish structured events to Redis pub/sub and optionally to audit log."""

    CHANNEL = "academic:events"

    def __init__(self, redis_client, audit_logger=None):
        self.r = redis_client
        self.audit = audit_logger

    def emit(self, event_type: EventType, **data):
        """Emit a typed event to the event channel."""
        payload = {
            "type": event_type.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        line = json.dumps(payload, ensure_ascii=False)
        try:
            self.r.publish(self.CHANNEL, line)
        except Exception:
            pass
        if self.audit:
            try:
                self.audit.log(event_type.value, details=data)
            except Exception:
                pass

    def emit_llm(self, event_type: EventType, model: str, elapsed: float,
                 tokens: int = 0, error: Optional[str] = None):
        """Emit an LLM call event with timing and cost data."""
        self.emit(event_type, model=model, elapsed_sec=round(elapsed, 1),
                  tokens=tokens, error=error)

    def emit_skill(self, event_type: EventType, skill: str, elapsed: float,
                   status: str, output_len: int = 0, error: Optional[str] = None):
        """Emit a skill execution event."""
        self.emit(event_type, skill=skill, elapsed_sec=round(elapsed, 1),
                  status=status, output_chars=output_len, error=error)
