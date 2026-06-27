"""Textual CSS — opencode 视觉移植。

关键设计：
- 3 层背景层次：root(#0a0a0a) < panel(#141414) < element(#1e1e1e)
- 签名元素：┃ 左边框（thick border via Rich Table）
- 紧凑 padding，multiline 消息自动扩展
"""

CSS = """
Screen {
    background: #0a0a0a;
}

/* ── Header / Footer ──────────────────────────── */
Header {
    background: #0a0a0a;
    color: #808080;
    text-style: none;
}

Footer {
    background: #0a0a0a;
    color: #808080;
    text-style: none;
}

/* ── Main Layout ──────────────────────────────── */
#main-layout {
    height: 1fr;
}

/* ── Left Panel (Chat) ────────────────────────── */
#left-panel {
    width: 3fr;
    background: #0a0a0a;
    border: none;
    height: 1fr;
}

#chat-panel {
    height: 1fr;
    background: #0a0a0a;
    border: none;
    padding: 0 1;
    overflow-y: auto;
    scrollbar-color: #484848;
    scrollbar-color-hover: #606060;
    scrollbar-color-active: #606060;
}

ChatPanel > Static {
    height: auto;
    background: #0a0a0a;
}

/* ── Prompt Input ─────────────────────────────── */
#input-area {
    height: auto;
    max-height: 8;
    background: #1e1e1e;
    border: none;
    padding: 0 1;
}

#input-textarea {
    height: 1fr;
    background: #1e1e1e;
    color: #eeeeee;
    border: none;
    padding: 1 0;
}

#input-hint {
    height: 1;
    background: #1e1e1e;
    color: #808080;
}

/* ── Right Panel (Sidebar) ────────────────────── */
#right-panel {
    width: 2fr;
    background: #141414;
    border: none;
    height: 1fr;
}

#sidebar {
    height: 1fr;
    background: #141414;
    overflow-y: auto;
    scrollbar-color: #484848;
    scrollbar-color-hover: #606060;
    scrollbar-color-active: #606060;
}

/* ── Sidebar Widgets ──────────────────────────── */
ProjectInfo {
    height: auto;
    background: #141414;
    padding: 1 2;
}

PhaseRing {
    height: auto;
    background: #141414;
    padding: 1 2;
}

CostBudget {
    height: auto;
    background: #141414;
    padding: 1 2;
}

GateStatus {
    height: auto;
    background: #141414;
    padding: 1 2;
}

AgentActivity {
    height: 1fr;
    background: #141414;
    border: none;
    padding: 0 2;
}

/* ── Mode Switcher ────────────────────────────── */
#mode-bar {
    height: 1;
    background: #0a0a0a;
    padding: 0 1;
}

.mode-btn {
    width: auto;
    padding: 0 1;
}

.mode-btn-active {
    color: #fab283;
    text-style: bold;
}

.mode-btn-inactive {
    color: #808080;
}

/* ── Chat Messages ────────────────────────────── */
.message-line {
    height: 1;
    padding: 0;
}

.message-block {
    height: auto;
    margin-bottom: 0;
}
"""

_DASHBOARD_CSS = CSS
"""
For compabitility with old imports.
"""
