# opencode-tui

> **English** | [**中文**](#opencode-tui-1)

Python TUI dashboard blending opencode visual style with dual-backend support (Redis / opencode HTTP API).

Python 编写的 TUI 仪表板，融合 opencode 视觉风格，支持 Redis / opencode HTTP API 双后端。

---

## Quick Start / 快速开始

### Installation / 安装

```bash
cd /home/opencode/ATTM/opencode-tui
pip install -e .
```

### Start (Redis Mode) / 启动（Redis 模式）

```bash
python -m opencode_tui
```

Connects to an existing Redis pipeline. Left panel: chat + right panel: dashboard (PhaseRing/CostBudget/GateStatus/AgentActivity).

连接已有 Redis 管线。左侧聊天 + 右侧仪表板（PhaseRing/CostBudget/GateStatus/AgentActivity）。

### Start (OpenCode Mode) / 启动（OpenCode 模式）

```bash
# Terminal 1: start the opencode server first / 先启动 opencode 服务
opencode serve --port 4096

# Terminal 2: launch TUI / 启动 TUI
cd /home/opencode/ATTM/opencode-tui
python -m opencode_tui --mode opencode
```

The TUI connects to opencode via HTTP/SSE, sends prompts to the LLM, and streams responses.

TUI 通过 HTTP/SSE 连接 opencode，发送 prompt 给 LLM 并流式接收回复。

### Startup Arguments / 启动参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--redis` | `redis://localhost:6379` | Redis URL |
| `--mode` | `redis` | Default backend (redis/opencode) |

---

## TUI Usage / 使用说明

### Screen Layout / 界面布局

```
+---------------------------------+---------------------+
|  Header (clock)                 |                     |
+---------------------------------+                     |
|  Chat Panel                     |  Sidebar            |
|                                 |                     |
|  | User Message (| primary bar) |  ProjectInfo        |
|  | stream text (live append)   |  -- Phase --        |
|  | cog bash: command            |  P0 Environment     |
|  |   output                     |  P1 Literature      |
|  | agent model 12s             |  P2 Method Design   |
|                                 |  -- Budget --       |
|  | User Message                 |  Session ####.. 42% |
|  | Received (demo mode)         |  Cost $0.1125       |
|                                 |  -- Gate --         |
|  +-------------------------+   |  G1 PASS Novelty    |
|  | Input message...        |   |  G2 PASS Experiment |
|  | executor deepseek...    |   |  -- Activity --     |
|  +-------------------------+   |  Environment Ready  |
+---------------------------------+  G1 Novelty PASS   |
|  Footer (opencode-tui 1.0)    |                     |
+---------------------------------+---------------------+
```

### Keyboard Shortcuts / 快捷键

| 按键 | 操作 |
|---|---|
| `Enter` | Send message / 发送消息 |
| `Esc` | Focus input / 聚焦输入框 |
| `Ctrl+L` | Clear chat / 清空聊天 |
| `q` | Quit / 退出 |

### TUI Commands / 命令

Type these in the input field / 在输入框中输入：

| 命令 | 操作 |
|---|---|
| `/help` | Show all commands / 显示所有命令 |
| `/clear` | Clear chat history / 清空聊天记录 |
| `/mode redis` | Switch to Redis backend / 切换到 Redis 后端 |
| `/mode opencode` | Switch to opencode backend / 切换到 opencode 后端 |
| `/status` | View connection status / 查看连接状态 |
| `/connect` | Reconnect / 重新连接 |
| `/diag` | Diagnostic info / 诊断信息 |

Backend switch example / 后端切换示例：

```
/mode opencode   -> switches to opencode, connects to :4096
/mode redis      -> switches back to Redis, connects to localhost:6379
/status          -> shows "opencode (connected)"
```

### Sending Messages / 发送消息

- Non-command text sends on Enter / 非命令文本按 Enter 发送
- Redis mode: published to `academic:inbox`, processed by pipeline / 发布到 `academic:inbox`，管线处理
- OpenCode mode: LLM reply streams into chat / LLM 回复流式进入聊天
- No backend connection: local echo demo mode / 无后端连接时本地回显

### Dashboard Widgets / 仪表板组件

| 组件 | 内容 | 数据源 |
|---|---|---|
| **ProjectInfo** | Project title + status + backend mode | poll 3s or event |
| **PhaseRing** | 6-phase progress icons | poll 3s or event |
| **CostBudget** | Session/Task progress bar + USD cost | poll 3s |
| **GateStatus** | 7 gate reviews: PASS/REVISE/FAIL | poll 3s or event |
| **AgentActivity** | Real-time event log, color-coded by tier | real-time event |

---

## OpenCode Integration / OpenCode 集成

opencode-tui ships with a complete `.opencode/` configuration, usable directly in opencode.

opencode-tui 自带完整 `.opencode/` 配置，可直接在 opencode 中使用。

### Register with opencode / 注册到 opencode

```jsonc
// opencode.jsonc or .opencode/opencode.jsonc
{
  "mcp": {
    "academic-pipeline": {
      "type": "local",
      "command": ["python", "-m", "academic_mcp.academic_server"],
      "cwd": "/home/opencode/ATTM/opencode-tui"
    }
  }
}
```

### Agents / 智能体

6 agent definitions in `.opencode/agent/`, auto-discovered on opencode startup:

`.opencode/agent/` 下 6 个智能体定义，opencode 启动时自动发现：

| Agent | Model | Role | Allowed Tools |
|---|---|---|---|
| `literature-researcher` | deepseek-v4-flash | Literature search | Bash, Read, WebFetch, Grep |
| `methodologist` | deepseek-v4-pro | Method design | Bash, Read, Write, WebFetch |
| `code-engineer` | deepseek-v4-flash | Code implementation | Bash, Read, Edit, Write, Grep |
| `visualization-designer` | deepseek-v4-flash | Visualization | Bash, Read, Edit, Write |
| `citation-auditor` | deepseek-v4-flash | Citation audit | Bash, Read, WebFetch |
| `academic-editor` | deepseek-v4-pro | Paper polishing | Bash, Read, Edit, Write |

```
/agent literature-researcher
/agent code-engineer
```

### Phase Commands / 阶段命令

6 slash commands in `.opencode/command/` / 6 个斜杠命令：

```
/phase0 "Research Title"    # Environment Setup / 环境搭建
/phase1                     # Literature Survey / 文献调研
/phase2                     # Method Design / 方法设计
/phase3                     # Experiment Validation / 实验验证
/phase4                     # Code Implementation / 编码实现
/phase5                     # Paper Writing / 论文写作
```

### MCP Server (6 Tools / 6 个工具)

`academic_mcp/academic_server.py` registered with opencode:

| Tool | Parameters | Function |
|---|---|---|
| `research-director` | `action: start/status/skip/stop` | Pipeline orchestration / 管线编排 |
| `experimenter` | `action: design/run/monitor/report` | Experiment management / 实验管理 |
| `scientific-computing-engineer` | `action: check_gpu/optimize/profile` | GPU/compute / GPU 计算 |
| `paper-writer` | `section: abstract/intro/method/...` | Paper writing / 论文写作 |
| `method-reviewer` | `action: review_method/check_novelty/...` | Method review / 方法评审 |
| `academic-reviewer` | `review_type: full/novelty/experiments/...` | Full review / 全面评审 |

### Pipeline Skill / 管线技能

`.opencode/skills/pipeline/SKILL.md` defines the orchestration flow / 定义编排流程：

```
Phase 0: Environment Setup       -> G1 Academic Novelty
Phase 1: Literature Survey       -> G2 Experiment Design (fusion)
Phase 2: Method Design           -> G3 Methodology
Phase 3: Experiment Validation   -> G4 Data Analysis
Phase 4: Code Implementation     -> G5 Logical Consistency (fusion)
Phase 5: Paper Writing           -> G6 Reproducibility -> G7 Final Review (fusion)
```

```
/skill pipeline
```

### Typical Workflow / 典型工作流

```text
1. Start opencode serve
2. python -m opencode_tui --mode opencode
3. In TUI: type "Research rotating machinery fault diagnosis" / 输入研究主题
4. LLM starts inference / LLM 开始推理
5. TUI displays streaming text, tool calls, and reasoning / TUI 实时显示流式文本
6. Results shown in the chat panel / 结果展示在聊天面板
7. Switch back to Redis pipeline: /mode redis / 切回 Redis 管线
```

---

## Architecture / 架构

```
+---------------------------------------------------+
|            opencode-tui (Python/Textual)            |
|  Chat + PhaseRing + CostBudget + GateStatus        |
|  [/mode redis  |  /mode opencode]                   |
+--------+--------------------------+-----------------+
         |                          |
   +-----v-----+             +------v------+
   |  Redis    |             |  opencode   |
   |  pub/sub  |             |  serve      |
   |  inbox/   |             |  :4096      |
   |  outbox/  |             |  HTTP/SSE   |
   |  progress |             |             |
   +-----+-----+             +------+------+
         |                          |
   +-----v-----+             +------v------+
   |academic_  |             | opencode    |
   |loop.py    |             | agent/*.md  |
   |12 agents  |             | command/*.md|
   |+ MCP srv  |             | + MCP tools |
   +-----------+             +-------------+
```

## Event Flow / 事件流

### Redis Mode / Redis 模式

```
TUI input text -> academic:inbox (pub) -> academic_loop.py
                                        -> academic:progress (pub) -> TUI widget update
                                        -> academic:outbox (pub) -> TUI displays reply
```

### OpenCode Mode / OpenCode 模式

```
TUI input text -> POST /session/:id/message  -> opencode LLM
               -> GET /event (SSE)
               <- message.part.updated (text/tool/reasoning streaming)
               <- session.status (idle -> complete)
               <- permission.asked (auto reply once)
```

---

## File Structure / 文件结构

```
/home/opencode/ATTM/opencode-tui/
+-- pyproject.toml               # Dependencies / 依赖
+-- src/opencode_tui/             # TUI core code / 核心代码
|   +-- app.py                   # Main App / 主应用
|   +-- __main__.py              # Entry point / 入口
|   +-- theme.py / css.py        # Palette + CSS / 主题 + 样式
|   +-- backend/                 # Dual backend / 双后端
|   +-- client/                  # HTTP client + SSE / 客户端
|   +-- widgets/                 # 7 widgets / 7 个组件
+-- academic_mcp/                # MCP server / MCP 服务 (6 tools)
+-- .opencode/                   # opencode integration / 集成配置
|   +-- opencode.jsonc           # Provider + MCP config
|   +-- agent/                   # 6 agents / 6 个智能体
|   +-- command/                 # 6 phase commands / 6 个阶段命令
|   +-- skills/pipeline/         # Pipeline skill / 管线技能
+-- tests/                       # 28 tests / 28 个测试
```

## Testing / 测试

```bash
cd /home/opencode/ATTM/opencode-tui
python -m pytest tests/ -v
```

28 tests / 28 个测试:
- SSE parsing (8): single/multi event, comments, empty data, invalid JSON
- Theme tokens (7): primary/secondary/accent/phase/gate/fusion
- Message rendering (9): bar_message/user/assistant/system/tool_header/output/footer
- Event classes (3): PhaseEvent/ChatMessage/BackendStatusEvent

---

## opencode-tui

> **中文** | [**English**](#quick-start--快速开始)

Python TUI 仪表板，融合 opencode 视觉风格，支持 Redis / opencode HTTP API 双后端。

### 安装

```bash
cd /home/opencode/ATTM/opencode-tui
pip install -e .
```

### 启动（Redis 模式）

```bash
python -m opencode_tui
```

连接已有 Redis 管线。左侧聊天 + 右侧仪表板。

### 启动（OpenCode 模式）

```bash
opencode serve --port 4096
cd /home/opencode/ATTM/opencode-tui
python -m opencode_tui --mode opencode
```

### 快捷键

| 按键 | 操作 |
|---|---|
| `Enter` | 发送消息 |
| `Esc` | 聚焦输入框 |
| `Ctrl+L` | 清空聊天 |
| `q` | 退出 |

### 命令

| 命令 | 操作 |
|---|---|
| `/help` | 显示所有命令 |
| `/clear` | 清空聊天记录 |
| `/mode redis` | 切换到 Redis 后端 |
| `/mode opencode` | 切换到 opencode 后端 |
| `/status` | 查看连接状态 |
| `/connect` | 重新连接 |
| `/diag` | 诊断信息 |

### 仪表板组件

| 组件 | 内容 |
|---|---|
| **ProjectInfo** | 项目标题 + 连接状态 + 后端模式 |
| **PhaseRing** | 6 阶段进度图标 |
| **CostBudget** | Session/Task 进度条 + 累计 USD 成本 |
| **GateStatus** | 7 门评审结果 |
| **AgentActivity** | 实时事件流日志 |

### 智能体

| Agent | 角色 |
|---|---|
| `literature-researcher` | 文献搜索与综述 |
| `methodologist` | 方法设计 |
| `code-engineer` | 编码实现 |
| `visualization-designer` | 可视化输出 |
| `citation-auditor` | 引用审计 |
| `academic-editor` | 论文润色 |

### 阶段命令

```
/phase0 "研究标题"    # 环境搭建
/phase1               # 文献调研
/phase2               # 方法设计
/phase3               # 实验验证
/phase4               # 编码实现
/phase5               # 论文写作
```

### 管线流程

```
Phase 0: 环境搭建       -> G1 学术新颖性
Phase 1: 文献调研       -> G2 实验设计 (融合)
Phase 2: 方法设计       -> G3 方法论
Phase 3: 实验验证       -> G4 数据分析
Phase 4: 编码实现       -> G5 逻辑一致性 (融合)
Phase 5: 论文写作       -> G6 可复现性 -> G7 终审 (融合)
```

### 文件结构

```
/home/opencode/ATTM/opencode-tui/
├── pyproject.toml           # 依赖配置
├── src/opencode_tui/        # TUI 核心代码
│   ├── app.py              # 主应用
│   ├── __main__.py          # 入口
│   ├── theme.py / css.py    # 主题 + CSS
│   ├── backend/             # 双后端
│   ├── client/              # HTTP 客户端
│   └── widgets/             # 7 个组件
├── academic_mcp/            # MCP 服务 (6 工具)
├── .opencode/               # opencode 集成配置
│   ├── opencode.jsonc       # Provider + MCP 配置
│   ├── agent/               # 6 个智能体
│   ├── command/             # 6 个阶段命令
│   └── skills/pipeline/     # 管线技能
└── tests/                   # 28 个测试
```

### 测试

```bash
cd /home/opencode/ATTM/opencode-tui
python -m pytest tests/ -v
```
