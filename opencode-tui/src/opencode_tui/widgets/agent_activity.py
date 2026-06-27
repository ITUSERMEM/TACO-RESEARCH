"""AgentActivity — 实时事件流日志。

所有 agent/gate/budget 事件按时间顺序追加。
颜色按 agent tier 区分（executor/reviewer/pro）。
"""

from textual.widgets import RichLog

from opencode_tui.theme import (
    TEXT, TEXT_MUTED, BG_PANEL, BG_ROOT,
    SECONDARY, PRIMARY, ACCENT,
)


TIER_COLORS = {
    "executor": SECONDARY,
    "reviewer": PRIMARY,
    "pro": ACCENT,
}

MAX_LINES = 100


class AgentActivity(RichLog):
    """实时事件流。"""

    def __init__(self, **kwargs):
        super().__init__(
            highlight=True,
            markup=True,
            max_lines=MAX_LINES,
            wrap=True,
            **kwargs,
        )

    def append_event(self, text: str, tier: str = ""):
        color = TIER_COLORS.get(tier, TEXT_MUTED)
        self.write(f"[dim {color}]·[/] [{color}]{text}[/]")
