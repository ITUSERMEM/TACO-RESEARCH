"""PromptInput — 底部输入栏。

opencode 风格：
- ┃ 左边框（颜色 = agent color）
- backgroundElement 底色
- status line：agent · model · provider
- 输入 / 时显示命令补全提示
"""

from textual.widgets import TextArea, Static
from textual.reactive import reactive
from textual.containers import Vertical

from opencode_tui.theme import PRIMARY, TEXT_MUTED, BG_ELEMENT


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
    _show_suggest = reactive(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._agent = "executor"
        self._model = "deepseek-v4-flash"
        self._provider = "zen"

    def compose(self):
        yield TextArea("", id="input-textarea")
        yield Static("", id="input-hint")
        yield Static("", id="cmd-suggest")

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
        if matches:
            sg = self.query_one("#cmd-suggest", Static)
            sg.update(f"[dim {TEXT_MUTED}]{chr(10).join(matches)}[/]")
            self._show_suggest = True
        else:
            self._hide_suggestions()

    def _hide_suggestions(self):
        if self._show_suggest:
            self.query_one("#cmd-suggest", Static).update("")
            self._show_suggest = False

    def watch__busy(self, busy: bool):
        hint = self.query_one("#input-hint", Static)
        if busy:
            hint.update(f"[dim {TEXT_MUTED}]⠋ 推理中...   esc 中断[/]")
        else:
            hint.update(
                f"[{self._agent_color()}]{self._agent}[/]"
                f" [dim {TEXT_MUTED}]·[/]"
                f" [dim {TEXT_MUTED}]{self._model}[/]"
                f" [dim {TEXT_MUTED}]· {self._provider}[/]"
            )

    def _agent_color(self) -> str:
        return PRIMARY

    def set_busy(self, busy: bool):
        self._busy = busy
