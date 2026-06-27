"""CostBudget — 成本/预算仪表板。

显示：
- Session Budget 进度条
- Task Budget 进度条
- 累计 USD 成本
- degrade/stop 告警
"""

from textual.widgets import Static

from opencode_tui.theme import (
    TEXT, TEXT_MUTED, SUCCESS, ERROR, SECONDARY, BG_PANEL,
)


BAR_CHARS = {
    "ok": ("█", "░"),
    "warn": ("▓", "░"),
    "critical": ("▒", "░"),
}


class CostBudget(Static):
    """成本/预算面板。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._session_pct = 0
        self._task_pct = 0
        self._total_cost = 0.0
        self._session_cost = 0.0
        self._task_cost = 0.0
        self._alert = ""

    def on_mount(self):
        self._render()

    def update_budget(self, data: dict):
        self._session_pct = data.get("session_pct", 0)
        self._task_pct = data.get("task_pct", 0)
        self._render()

    def update_cost(self, data: dict):
        self._session_cost = data.get("session_cost", 0.0)
        self._task_cost = data.get("task_cost", 0.0)
        self._total_cost = data.get("total_cost", 0.0)
        self._render()

    def set_alert(self, event: str, msg: str = ""):
        self._alert = msg
        self._render()

    def _bar(self, pct: int, width: int = 10) -> str:
        filled = min(pct * width // 100, width)
        if pct >= 90:
            full, empty = "▒", "░"
        elif pct >= 70:
            full, empty = "▓", "░"
        else:
            full, empty = "█", "─"
        return full * filled + empty * (width - filled)

    def _color_for_pct(self, pct: int) -> str:
        if pct >= 90:
            return ERROR
        if pct >= 70:
            return SECONDARY
        return SUCCESS

    def _render(self):
        lines = [f"[bold #61afef]── Budget/Cost ──[/]"]

        s_color = self._color_for_pct(self._session_pct)
        s_bar = self._bar(self._session_pct)
        lines.append(
            f"  Session [{s_color}]{s_bar}[/]"
            f" [dim {TEXT_MUTED}]{self._session_pct}%[/]"
        )

        t_color = self._color_for_pct(self._task_pct)
        t_bar = self._bar(self._task_pct)
        lines.append(
            f"  Task    [{t_color}]{t_bar}[/]"
            f" [dim {TEXT_MUTED}]{self._task_pct}%[/]"
        )

        lines.append(
            f"  [dim {TEXT_MUTED}]Cost:[/]"
            f" [#7fd88f]${self._total_cost:.4f}[/]"
        )

        if self._alert:
            lines.append(f"  [{SECONDARY}]⚠ {self._alert}[/]")

        self.update("\n".join(lines))
