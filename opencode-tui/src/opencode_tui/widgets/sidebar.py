"""Sidebar — 右侧边栏容器。

包含：
- ProjectInfo
- PhaseRing
- CostBudget
- GateStatus
- AgentActivity

opencode 风格：backgroundPanel 底色，紧凑 spacing。
"""

from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static
from textual.app import ComposeResult

from opencode_tui.theme import TEXT, TEXT_MUTED, BG_PANEL
from opencode_tui.widgets.phase_ring import PhaseRing
from opencode_tui.widgets.cost_budget import CostBudget
from opencode_tui.widgets.gate_status import GateStatus
from opencode_tui.widgets.agent_activity import AgentActivity


class ProjectInfo(Static):
    """项目信息面板。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._title = ""
        self._status = "disconnected"
        self._mode = "redis"

    def set_title(self, title: str):
        self._title = title[:80]
        self._render()

    def set_status(self, status: str):
        self._status = status
        self._render()

    def set_mode(self, mode: str):
        self._mode = mode
        self._render()

    def _render(self):
        mode_color = "#808080" if self._mode == "opencode" else "#5c9cf5"
        self.update(
            f"[bold #eeeeee]{self._title or 'opencode-tui'}[/]\n"
            f"[dim #808080]{self._status} · [/]"
            f"[{mode_color}]◉ {self._mode}[/]"
        )


class Sidebar(VerticalScroll):
    """右侧边栏。"""

    def compose(self) -> ComposeResult:
        yield ProjectInfo(id="project-info")
        yield PhaseRing(id="phase-ring")
        yield CostBudget(id="cost-budget")
        yield GateStatus(id="gate-status")
        yield AgentActivity(id="agent-activity")

    @property
    def phase_ring(self) -> PhaseRing:
        return self.query_one("#phase-ring", PhaseRing)

    @property
    def cost_budget(self) -> CostBudget:
        return self.query_one("#cost-budget", CostBudget)

    @property
    def gate_status(self) -> GateStatus:
        return self.query_one("#gate-status", GateStatus)

    @property
    def agent_activity(self) -> AgentActivity:
        return self.query_one("#agent-activity", AgentActivity)

    @property
    def project_info(self) -> ProjectInfo:
        return self.query_one("#project-info", ProjectInfo)
