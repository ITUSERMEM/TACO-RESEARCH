"""ChatPanel — 流式消息渲染。

支持：
- completed 消息：直接追加
- streaming 消息：start → update → end 实时更新同一行
- 工具块：独立 Static widget 可独立更新
"""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static
from textual.widgets._static import RenderableType

from opencode_tui.theme import TEXT_MUTED


class ChatPanel(VerticalScroll):
    """聊天面板 — 支持流式渲染的消息列表。"""

    MAX_MESSAGES = 200

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._stream_widget: Static | None = None
        self._msg_count = 0

    def write(self, content: RenderableType):
        """追加一条已完成消息。"""
        self._add_msg(Static(content, classes="message-block"))

    def start_stream(self, content: RenderableType = ""):
        """开始一条流式消息。"""
        self._stream_widget = Static(content, classes="message-block streaming")
        self._add_msg(self._stream_widget)

    def update_stream(self, content: RenderableType):
        """更新当前流式消息。"""
        if self._stream_widget:
            self._stream_widget.update(content)
            self.scroll_end()

    def end_stream(self, content: RenderableType | None = None):
        """结束流式消息（变为已完成消息）。"""
        if self._stream_widget:
            if content is not None:
                self._stream_widget.update(content)
            self._stream_widget.remove_class("streaming")
            self._stream_widget = None
        self.scroll_end()

    def write_stream(self, text: str, finished: bool = False):
        """便捷方法：追加一行流式文本。

        当 finished=True 时结束流式，否则在该消息上追加。
        """
        content = f"[dim {TEXT_MUTED}]┃[/] {text}"
        if self._stream_widget is None:
            self.start_stream(content)
        elif finished:
            self.end_stream(content)
        else:
            self.update_stream(content)

    def tool_block(self, icon: str, title: str, output: str = "", status: str = "running"):
        """渲染一个工具调用块。"""
        icon_color = {"running": "#5c9cf5", "ok": "#7fd88f", "error": "#e06c75"}
        color = icon_color.get(status, "#808080")
        lines = [f"[dim {color}]┃[/] [{color}]{icon} {title}[/]"]
        if output:
            lines.append(f"[dim {TEXT_MUTED}]┃[/] [dim]{output[:200]}[/]")
        self.write("\n".join(lines))

    def write_bar(self, text: str, bar_color: str, text_color: str = "#eeeeee"):
        """带 ┃ 左边框的单行消息。"""
        self.write(f"[bold {bar_color}]┃[/] [{text_color}]{text}[/]")

    def clear(self):
        self._stream_widget = None
        self._msg_count = 0
        self.remove_children()

    def _add_msg(self, widget: Static):
        self.mount(widget)
        self._msg_count += 1
        self.scroll_end()
        if self._msg_count > self.MAX_MESSAGES:
            children = list(self.children)
            if len(children) > self.MAX_MESSAGES:
                to_remove = children[: len(children) - self.MAX_MESSAGES]
                for w in to_remove:
                    w.remove()
