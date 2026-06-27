"""Braille spinner — opencode 原生动画。

帧序列：⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏  @  80ms
"""

from textual.widgets import Static
from textual.reactive import reactive


FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
INTERVAL = 0.08


class Spinner(Static):
    """Animated braille spinner with label."""

    _frame = reactive(0)

    def __init__(
        self,
        label: str = "",
        *,
        color: str = "#808080",
        paused: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._label = label
        self._color = color
        self._paused = paused

    def on_mount(self):
        if not self._paused:
            self.set_interval(INTERVAL, self._advance)

    def _advance(self):
        self._frame = (self._frame + 1) % len(FRAMES)

    def watch__frame(self, index: int):
        self._render_frame(index)

    def _render_frame(self, index: int):
        spinner = FRAMES[index]
        if self._label:
            self.update(f"[bold {self._color}]{spinner}[/] [dim]{self._label}[/]")
        else:
            self.update(f"[bold {self._color}]{spinner}[/]")

    def set_label(self, label: str):
        self._label = label
        self._render_frame(self._frame)

    def set_color(self, color: str):
        self._color = color
        self._render_frame(self._frame)

    def toggle(self):
        self._paused = not self._paused
