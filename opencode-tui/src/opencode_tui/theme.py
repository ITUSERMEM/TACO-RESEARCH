"""opencode 色板移植 — 40+ 颜色 token。

从 opencode 默认主题 opencode.json 移植。
所有颜色已在暗色模式下确认。
"""

# ── Brand / Core ─────────────────────────────────────────
PRIMARY = "#fab283"      # 暖桃 — 主强调色、prompt 边框、链接
SECONDARY = "#5c9cf5"    # 蓝 — 文件附件、二级强调
ACCENT = "#9d7cd8"       # 紫 — Markdown 标题、语法关键词

# ── Status ───────────────────────────────────────────────
ERROR = "#e06c75"        # 红 — 错误、拒绝权限
WARNING = "#f5a742"      # 橙 — 警告、思考块、进行中
SUCCESS = "#7fd88f"      # 绿 — 成功、MCP 连接
INFO = "#56b6c2"         # 青 — 信息通知

# ── Text ─────────────────────────────────────────────────
TEXT = "#eeeeee"         # 主要前景
TEXT_MUTED = "#808080"   # 次要/静音文本、时间戳、提示

# ── Background (3 层层次) ────────────────────────────────
BG_ROOT = "#0a0a0a"       # 最底层画布
BG_PANEL = "#141414"       # 内容块（消息、侧边栏）
BG_ELEMENT = "#1e1e1e"     # 交互元素（输入框、悬停）

# ── Borders (5 阶灰度) ───────────────────────────────────
BORDER = "#484848"
BORDER_ACTIVE = "#606060"
BORDER_SUBTLE = "#3c3c3c"

# ── Diff 颜色 ────────────────────────────────────────────
DIFF_ADDED = "#4fd6be"
DIFF_REMOVED = "#c53b53"
DIFF_CONTEXT = "#828bb8"
DIFF_ADDED_BG = "#20303b"
DIFF_REMOVED_BG = "#37222c"
DIFF_CONTEXT_BG = "#141414"
DIFF_LINE_NUM = "#8f8f8f"
DIFF_HUNK_HEADER = "#828bb8"
DIFF_HIGHLIGHT_ADDED = "#b8db87"
DIFF_HIGHLIGHT_REMOVED = "#e26a75"

# ── Markdown ─────────────────────────────────────────────
MD_TEXT = TEXT
MD_HEADING = ACCENT
MD_LINK = PRIMARY
MD_LINK_TEXT = INFO
MD_CODE = SUCCESS
MD_BLOCK_QUOTE = "#e5c07b"
MD_EMPH = "#e5c07b"
MD_STRONG = WARNING
MD_LIST_ITEM = PRIMARY
MD_LIST_ENUM = INFO
MD_CODE_BLOCK = TEXT

# ── Syntax Highlighting ──────────────────────────────────
SYNTAX_COMMENT = "#808080"
SYNTAX_KEYWORD = ACCENT
SYNTAX_FUNCTION = PRIMARY
SYNTAX_VARIABLE = ERROR
SYNTAX_STRING = SUCCESS
SYNTAX_NUMBER = WARNING
SYNTAX_TYPE = "#e5c07b"
SYNTAX_OPERATOR = INFO
SYNTAX_PUNCTUATION = TEXT

# ── Phase (P0-P5) ───────────────────────────────────────
PHASE_COLORS = {
    0: SECONDARY,      # 蓝 — 环境初始化
    1: PRIMARY,        # 桃 — 文献调研
    2: ACCENT,         # 紫 — 方案设计
    3: SUCCESS,        # 绿 — 实验验证
    4: WARNING,        # 橙 — 代码实现
    5: ERROR,          # 玫红 — 论文撰写
}

PHASE_LABELS = {
    0: "环境初始化",
    1: "文献调研",
    2: "方案设计",
    3: "实验验证",
    4: "代码实现",
    5: "论文撰写",
}

# ── Gate (G1-G7) ────────────────────────────────────────
GATE_LABELS = {
    1: "学术新颖性", 2: "实验设计", 3: "方法论",
    4: "数据分析", 5: "逻辑一致性", 6: "可复现性", 7: "终审",
}
FUSION_GATES = {2, 5, 7}

# ── Agent Tier Colors ───────────────────────────────────
TIER_COLORS = {
    "executor": SECONDARY,
    "reviewer": PRIMARY,
    "pro": ACCENT,
}

# ── Event Icons ─────────────────────────────────────────
EVENT_ICONS = {
    "pipeline_start": "🚀", "pipeline_error": "❌",
    "phase_start": "▶", "phase_complete": "✓",
    "agent_start": "▸", "agent_done": "◂",
    "agent_reasoning": "💭", "agent_iter": "◇",
    "agent_skill_select": "🔧", "agent_skill_run": "⚙",
    "agent_skill_ok": "✓", "agent_skill_error": "✗",
    "agent_skill_hang": "⚠", "agent_skill_timeout": "⌛",
    "agent_skill_output": "📄", "agent_skip_skill": "⏭",
    "budget_degrade": "↓", "budget_stop": "⛔",
    "gate_pass": "PASS", "gate_revise": "REVISE", "gate_fail": "FAIL",
    "heartbeat_ok": "♥", "heartbeat_alert": "💔",
}

# ── Helper ──────────────────────────────────────────────
def phase_label(idx: int) -> str:
    return PHASE_LABELS.get(idx, f"Phase {idx}")


def phase_color(idx: int) -> str:
    return PHASE_COLORS.get(idx, TEXT_MUTED)


def tier_color(tier: str) -> str:
    return TIER_COLORS.get(tier, TEXT)
