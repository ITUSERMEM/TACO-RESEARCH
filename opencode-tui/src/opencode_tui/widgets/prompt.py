"""PromptInput — 底部输入栏。

opencode 风格：
- ┃ 左边框（灰色 #484848，agent 激活时渐变到 agent 色）
- backgroundElement (#1e1e1e) 统一底色
- textarea + meta 行在同一个带边框容器内
- 底部状态栏（无边框）：spinner / agent·model·provider / 快捷键提示
"""

from textual.widgets import TextArea, Static
from textual.reactive import reactive
from textual.containers import Vertical

from opencode_tui.theme import (
    PRIMARY, ACCENT, TEXT, TEXT_MUTED,
    BG_ROOT, BG_PANEL, BG_ELEMENT, BORDER,
)


COMMANDS = {
    "/help":   "显示命令列表",
    "/clear":  "清空聊天",
    "/mode":   "切换后端 (redis/opencode)",
    "/status": "查看管线状态",
    "/connect": "重新连接后端",
    "/diag":   "诊断信息",
}


class PromptInput(Vertical):
    """底部输入栏。"""

    _busy = reactive(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._agent = "executor"
        self._model = "deepseek-v4-flash"
        self._provider = "zen"

    def compose(self):
        with Vertical(id="input-box"):
            yield TextArea("", id="input-textarea")
            yield Static("", id="input-hint")
        yield Static("", id="input-status")
        yield Static("", id="cmd-suggest")

    def on_mount(self):
        self._update_hint()

    def on_text_area_changed(self, event: TextArea.Changed):
        if event.text_area.id != "input-textarea":
            return
        text = event.text_area.text
        if text.startswith("/"):
            self._show_suggestions(text)
        else:
            self._hide_suggestions()

    def _show_suggestions(self, text: str):
        prefix = text.lower()
        matches = [f"  {c}  {d}" for c, d in COMMANDS.items() if c.startswith(prefix)]
        sg = self.query_one("#cmd-suggest", Static)
        if matches:
            sg.update(f"[dim {TEXT_MUTED}]{chr(10).join(matches)}[/]")
        else:
            sg.update("")

    def _hide_suggestions(self):
        self.query_one("#cmd-suggest", Static).update("")

    def _update_hint(self):
        hint = self.query_one("#input-hint", Static)
        if self._busy:
            hint.update(f"[dim {TEXT_MUTED}]⠋ 推理中...[/]")
        else:
            hint.update(
                f"[{PRIMARY}]{self._agent}[/]"
                f" [dim {TEXT_MUTED}]·[/]"
                f" [dim {TEXT_MUTED}]{self._model}[/]"
                f" [dim {TEXT_MUTED}]· {self._provider}[/]"
            )

    def watch__busy(self, busy: bool):
        self._update_hint()
        st = self.query_one("#input-status", Static)
        if busy:
            st.update(
                f"[dim {TEXT_MUTED}]⠋ 推理中   esc 中断[/]"
            )
        else:
            st.update(
                f"[dim {TEXT_MUTED}]/help 查看命令[/]"
            )

    def set_busy(self, busy: bool):
        self._busy = busy
