"""PromptInput — 底部输入栏。

opencode 风格：
- ┃ 左边框（颜色 = agent color）
- backgroundElement 底色
- status line：agent · model · provider
- spinner 标识推理中
"""

from textual.widgets import TextArea, Static
from textual.reactive import reactive
from textual.containers import Vertical

from opencode_tui.theme import (
    PRIMARY, TEXT, TEXT_MUTED, BG_ELEMENT, BORDER,
)


class PromptInput(Vertical):
    """底部输入栏。"""

    _busy = reactive(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._agent = "executor"
        self._model = "deepseek-v4-flash"
        self._provider = "zen"

    def compose(self):
        yield TextArea(
            "",
            id="input-textarea",
        )
        yield Static("输入消息... /help 查看命令", id="input-hint")

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
