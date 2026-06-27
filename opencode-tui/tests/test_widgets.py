"""Widget 单元测试。"""

import pytest
from opencode_tui.theme import (
    PRIMARY, SECONDARY, ACCENT,
    PHASE_COLORS, PHASE_LABELS,
    GATE_LABELS, FUSION_GATES,
)
from opencode_tui.widgets.message import (
    bar_message, user_message, assistant_message, system_message,
    tool_header, tool_output, message_footer,
)


class TestTheme:
    """色板 token。"""

    def test_primary_hex(self):
        assert PRIMARY == "#fab283"

    def test_secondary_hex(self):
        assert SECONDARY == "#5c9cf5"

    def test_accent_hex(self):
        assert ACCENT == "#9d7cd8"

    def test_phase_colors_complete(self):
        for i in range(6):
            assert i in PHASE_COLORS, f"missing phase {i} color"
            assert PHASE_COLORS[i].startswith("#"), f"bad phase {i} color"

    def test_phase_labels_complete(self):
        for i in range(6):
            assert i in PHASE_LABELS, f"missing phase {i} label"
            assert PHASE_LABELS[i], f"empty phase {i} label"

    def test_fusion_gates(self):
        assert FUSION_GATES == {2, 5, 7}

    def test_gate_labels(self):
        for gid in range(1, 8):
            assert gid in GATE_LABELS


class TestBars:
    """┃ 左边框消息渲染。"""

    def test_bar_message_returns_table(self):
        t = bar_message("hello")
        assert t is not None
        assert t.row_count == 1

    def test_user_message(self):
        t = user_message("hi")
        assert t is not None

    def test_assistant_message(self):
        t = assistant_message("hi")
        assert t is not None

    def test_system_message(self):
        t = system_message("warn")
        assert t is not None

    def test_system_message_urgent(self):
        t = system_message("error", urgent=True)
        assert t is not None

    def test_tool_header(self):
        t = tool_header("$", "run test")
        assert t is not None

    def test_tool_output(self):
        t = tool_output("result")
        assert t is not None

    def test_message_footer(self):
        t = message_footer("agent", "model", 1.5)
        assert t is not None


class TestEvents:
    """事件数据类。"""

    def test_phase_event(self):
        from opencode_tui.events import PhaseEvent
        e = PhaseEvent(phase=2, status="running")
        assert e.phase == 2
        assert e.status == "running"

    def test_chat_message(self):
        from opencode_tui.events import ChatMessage
        e = ChatMessage(role="user", content="hello")
        assert e.role == "user"
        assert e.content == "hello"

    def test_backend_status(self):
        from opencode_tui.events import BackendStatusEvent
        e = BackendStatusEvent(backend="opencode", connected=True)
        assert e.backend == "opencode"
        assert e.connected
