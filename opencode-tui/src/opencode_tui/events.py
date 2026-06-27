"""事件类型 — 后端无关的抽象事件。

TUI widget 只消费这些 Textual Message，
不关心事件来自 Redis pub/sub 还是 opencode SSE。
"""

from dataclasses import dataclass, field
from textual.message import Message


@dataclass
class PhaseEvent(Message):
    phase: int
    status: str  # pending | running | done | error
    detail: str = ""
    project_id: str = ""
    project_title: str = ""


@dataclass
class AgentEvent(Message):
    agent: str
    status: str  # start | done | reasoning | skill_run | skill_ok | skill_error | skill_hang
    detail: str = ""
    phase: int = -1


@dataclass
class GateEvent(Message):
    gate_id: int
    verdict: str  # pass | revise | fail
    detail: str = ""
    fusion: bool = False


@dataclass
class BudgetEvent(Message):
    event: str  # degrade | stop | update
    session_cost: float = 0.0
    task_cost: float = 0.0
    session_pct: int = 0
    task_pct: int = 0
    degrade_step: str = ""
    message: str = ""


@dataclass
class BackendStatusEvent(Message):
    backend: str  # redis | opencode
    connected: bool
    error: str = ""


@dataclass
class ChatMessage(Message):
    role: str  # user | assistant | system
    content: str
    agent: str = ""
    model: str = ""
    duration: float = 0.0
    is_streaming: bool = False


@dataclass
class PipelineLifecycleEvent(Message):
    event: str  # start | complete | error
    detail: str = ""
