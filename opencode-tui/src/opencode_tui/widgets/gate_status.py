"""GateStatus — 7 门评审状态网格。

每个 gate 显示 verdict (PASS/REVISE/FAIL) 或 pending。
Fusion gates (G2/G5/G7) 标记 ⚡。
"""

from textual.widgets import Static

from opencode_tui.theme import (
    TEXT, TEXT_MUTED, SUCCESS, WARNING, ERROR, PRIMARY, FUSION_GATES,
)


VERDICT_COLORS = {
    "pass": SUCCESS,
    "revise": WARNING,
    "fail": ERROR,
    "pending": TEXT_MUTED,
}

VERDICT_LABELS = {
    "pass": "PASS",
    "revise": "REVISE",
    "fail": "FAIL",
    "pending": "··",
}

GATE_LABELS = {
    1: "新颖性", 2: "实验设计", 3: "方法论",
    4: "数据分析", 5: "逻辑一致性", 6: "可复现性", 7: "终审",
}


class GateStatus(Static):
    """Gate 评审状态面板。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._gates: dict[int, str] = {}

    def on_mount(self):
        self._render()

    def update_gate(self, gate_id: int, verdict: str):
        self._gates[gate_id] = verdict
        self._render()

    def load_from_state(self, results: dict):
        for key, val in results.items():
            try:
                gid = int(key.replace("phase", "").replace("gate", "").split("_")[-1])
                self._gates[gid] = val.get("verdict", "pending")
            except (ValueError, KeyError):
                pass
        self._render()

    def _render(self):
        lines = ["[bold #61afef]── Gate Status ──[/]"]
        for gid in range(1, 8):
            verdict = self._gates.get(gid, "pending")
            color = VERDICT_COLORS.get(verdict, TEXT_MUTED)
            label = VERDICT_LABELS.get(verdict, "··")
            name = GATE_LABELS.get(gid, f"G{gid}")
            fusion = " ⚡" if gid in FUSION_GATES else ""
            lines.append(
                f"  G{gid} [{color}]{label:>5}[/]"
                f" [dim {TEXT_MUTED}]{name}{fusion}[/]"
            )
        self.update("\n".join(lines))
