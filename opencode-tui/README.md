# opencode-tui

Python TUI 仪表板，融合 opencode 视觉风格，支持双后端（Redis / opencode HTTP API）。

## 功能

- **opencode 风格 UI** — 近黑背景、┃ 左边框、3 层背景层次、Braille spinner
- **双后端切换** — Redis 模式连现有管线，opencode 模式连 HTTP API，`/mode` 命令实时切换
- **Phase 0-5 进度** — 6 阶段状态显示（pending/running/done/error）
- **Gate 评审** — 7 门评审状态网格，fusion gate 标记 ⚡
- **成本预算** — Session/Task 进度条 + 累计 USD
- **实时事件流** — Agent 活动日志，按 tier 着色
- **流式消息** — text_part 实时追加渲染
- **opencode Agent 集成** — 6 个原生 agent + 6 个 MCP tool
- **MCP 服务器** — 6 个复杂 agent 暴露为 opencode tool

## 快速开始

### 安装

```bash
cd /home/opencode/ATTM/opencode-tui
pip install -e .
```

### 启动（Redis 模式）

自动连接本地 Redis，读取现有管线状态：

```bash
python -m opencode_tui
# 或
opencode-tui
```

### 启动（OpenCode 模式）

先启动 opencode server，再启动 TUI：

```bash
# 终端 1：启动 opencode server
opencode serve --port 4096

# 终端 2：启动 TUI
cd /home/opencode/ATTM/opencode-tui
python -m opencode_tui --mode opencode
```

### 启动参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--redis` | `redis://localhost:6379` | Redis URL |
| `--mode` | `redis` | 默认后端（redis/opencode） |

## 使用指南

### 键盘快捷键

| 按键 | 功能 |
|---|---|
| `Enter` | 发送消息 |
| `Esc` | 聚焦输入框 |
| `Ctrl+L` | 清空聊天 |
| `q` | 退出 |

### 命令

| 命令 | 功能 |
|---|---|
| `/help` | 显示命令列表 |
| `/clear` | 清空聊天 |
| `/mode <redis\|opencode>` | 切换后端 |
| `/status` | 查看连接状态 |
| `/connect` | 重新连接后端 |
| `/diag` | 诊断信息（phase/cost/gate） |

### 后端切换

```text
/mode opencode   → 切换到 opencode 后端
/mode redis      → 切回 Redis 后端
/status          → 查看当前连接状态
```

切换后自动重新连接，widget 实时更新为新后端数据。

## 架构

```
┌───────────────────────────────────────────────────┐
│            opencode-tui (Python/Textual)            │
│                                                    │
│  ┌─────────────────────┬─────────────────────┐    │
│  │  Chat               │  Sidebar            │    │
│  │  ┃ user msg         │  PhaseRing  Cost    │    │
│  │  ┃ stream text      │  GateStatus Budget  │    │
│  │  ┃ tool blocks      │  AgentActivity      │    │
│  │  ⚙ bash  → Read    │                     │    │
│  ├─────────────────────┤                     │    │
│  │  ┃ prompt input     │                     │    │
│  │  agent · model      │                     │    │
│  └─────────────────────┴─────────────────────┘    │
│         [/mode redis  |  /mode opencode]           │
└───────┬──────────────────────────┬─────────────────┘
        │                          │
  ┌─────▼─────┐             ┌──────▼──────┐
  │  Redis    │             │  opencode   │
  │  pub/sub  │             │  serve      │
  │  inbox/   │             │  :4096      │
  │  outbox/  │             │  HTTP/SSE   │
  │  progress │             │             │
  └─────┬─────┘             └──────┬──────┘
        │                          │
  ┌─────▼─────┐             ┌──────▼──────┐
  │academic_  │             │ opencode    │
  │loop.py    │             │ agent/*.md  │
  │12 agents  │             │ command/*.md│
  │+ MCP srv  │             │ + MCP tools │
  └───────────┘             └─────────────┘
```

### 文件结构

```
/home/opencode/ATTM/opencode-tui/
├── pyproject.toml              # 项目元数据 + 依赖
├── README.md                   # 本文件
├── src/opencode_tui/
│   ├── app.py                  # 主 App (Textual) — 布局 + 事件流 + 命令路由
│   ├── theme.py                # opencode 色板（40+ token）
│   ├── css.py                  # Textual CSS（┃边、3层背景）
│   ├── events.py               # 后端无关的事件类型
│   ├── backend/
│   │   ├── base.py             # 抽象 Backend 接口
│   │   ├── redis_backend.py    # Redis pub/sub + polling
│   │   └── opencode_backend.py # opencode HTTP/SSE
│   ├── client/
│   │   ├── http.py             # httpx 客户端（session/prompt/permission）
│   │   └── sse.py              # SSE 流解析
│   └── widgets/
│       ├── chat.py             # 流式消息列表（VerticalScroll）
│       ├── prompt.py           # ┃ 左边框输入栏 + status line
│       ├── sidebar.py          # 右侧栏容器
│       ├── phase_ring.py       # Phase 0-5 进度
│       ├── cost_budget.py      # 成本/预算仪表板
│       ├── gate_status.py      # 7 门评审网格
│       ├── agent_activity.py   # 实时事件流
│       ├── spinner.py          # Braille ⠋⠙⠹⠸... 80ms
│       └── message.py          # Rich Table ┃ 消息渲染
├── academic_mcp/
│   └── academic_server.py      # Python MCP server（6 tool）
├── .opencode/
│   ├── opencode.jsonc          # provider + mcp + permission 配置
│   ├── agent/                  # 6 个原生 agent 定义
│   ├── command/                # 6 个 Phase 命令
│   └── skills/pipeline/        # 管线编排 skill
└── tests/
    ├── test_client.py          # SSE 解析 + 客户端测试（10）
    └── test_widgets.py         # 色板 + 消息渲染 + 事件测试（18）
```

## OpenCode 集成

### Agent 定义（6 个原生）

`.opencode/agent/` 中的 agent 供 opencode 原生调度：

| Agent | Model | Role |
|---|---|---|
| literature-researcher | deepseek-v4-flash | 文献检索与综述 |
| methodologist | deepseek-v4-pro | 方法论设计 |
| code-engineer | deepseek-v4-flash | 代码实现 |
| visualization-designer | deepseek-v4-flash | 可视化 |
| citation-auditor | deepseek-v4-flash | 引用审计 |
| academic-editor | deepseek-v4-pro | 论文润色 |

### MCP Server（6 个复杂 agent）

由 `academic_mcp/academic_server.py` 通过 MCP 协议暴露：

| Tool | 功能 |
|---|---|
| `research-director` | 管线编排：start/stop/skip phase |
| `experimenter` | 实验：design/run/monitor/report |
| `scientific-computing-engineer` | 计算：check_gpu/optimize/profile |
| `paper-writer` | 论文：abstract/intro/method/full |
| `method-reviewer` | 评审：review_method/check_novelty |
| `academic-reviewer` | 完整学术评审 |

注册到 opencode 后，这些 tool 在聊天中直接可用：

```jsonc
// .opencode/opencode.jsonc
"mcp": {
  "academic-pipeline": {
    "type": "local",
    "command": ["python", "-m", "academic_mcp.academic_server"],
    "cwd": "/home/opencode/ATTM/opencode-tui"
  }
}
```

## 事件流

### Redis 模式

```
TUI → academic:inbox (pub) → academic_loop.py
                         → academic:progress (pub) → TUI 订阅
                         → academic:outbox (pub) → TUI 订阅
```

### OpenCode 模式

```
TUI → POST /session                (create session)
   → GET /event                    (SSE subscribe)
   → POST /session/:id/message     (send prompt)
   ← SSE: message.part.updated     (streaming text/tool/reasoning)
   ← SSE: session.status           (idle → complete)
   ← SSE: permission.asked         (auto-reply once)
```

## 测试

```bash
cd /home/opencode/ATTM/opencode-tui
python -m pytest tests/ -v
```

28 项测试覆盖：
- SSE 解析（8）：单事件/多事件/注释/空数据/非法 JSON
- 色板 token（7）：PRIMARY/SECONDARY/ACCENT/Phase colors/Gate labels/Fusion
- 消息渲染（9）：bar_message/user/assistant/system/tool_header/tool_output/footer
- 事件类（3）：PhaseEvent/ChatMessage/BackendStatusEvent

## 色板

所有颜色移植自 opencode 默认主题：

```
背景：     #0a0a0a → #141414 → #1e1e1e（3 层层次）
强调：     #fab283（暖桃）  #5c9cf5（蓝）  #9d7cd8（紫）
成功/错误： #7fd88f / #e06c75
警告/信息： #f5a742 / #56b6c2
文本：     #eeeeee / #808080（静音）
边框：     #484848 / #606060 / #3c3c3c
```
