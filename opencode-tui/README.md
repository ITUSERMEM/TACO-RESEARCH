# opencode-tui

Python TUI 仪表板，融合 opencode 视觉风格，支持双后端（Redis / opencode HTTP API）。

## 快速开始

### 安装

```bash
cd /home/opencode/ATTM/opencode-tui
pip install -e .
```

### 启动（Redis 模式）

```bash
python -m opencode_tui
```

连现有 Redis 管线。左侧聊天 + 右侧仪表板（PhaseRing/CostBudget/GateStatus/AgentActivity）。

### 启动（OpenCode 模式）

```bash
# 终端 1：先启动 opencode server
opencode serve --port 4096

# 终端 2：再启动 TUI
cd /home/opencode/ATTM/opencode-tui
python -m opencode_tui --mode opencode
```

TUI 通过 HTTP/SSE 连接 opencode，发送 prompt 到 LLM，流式显示回复。

### 启动参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--redis` | `redis://localhost:6379` | Redis URL |
| `--mode` | `redis` | 默认后端（redis/opencode） |

---

## TUI 使用

### 屏幕布局

```
┌─────────────────────────────────┬─────────────────────┐
│  Header (clock)                │                     │
├─────────────────────────────────┤                     │
│  Chat 面板                      │  Sidebar            │
│                                 │                     │
│  ┃ 用户消息 (┃ primary 左边框)  │  ProjectInfo        │
│  ┃ stream text (实时追加)      │  ── Phase ──        │
│  ┃ ⚙ bash: command             │  P0 ✓ 环境初始化    │
│  ┃   output                     │  P1 · 文献调研      │
│  ┃ ▣ agent · model · 12s       │  P2 ▸ 方案设计      │
│                                 │  ── Budget ──       │
│  ┃ 用户消息                     │  Session ████░░ 42% │
│  ┃ 已收到 (演示模式)            │  Cost $0.1125       │
│                                 │  ── Gate ──         │
│  ┌─────────────────────────┐   │  G1 PASS 新颖性     │
│  │ ┃ 输入消息...            │   │  G2 PASS 实验设计⚡ │
│  │ executor · deepseek...   │   │  ── Activity ──     │
│  └─────────────────────────┘   │  · 环境初始化完成    │
├─────────────────────────────────┤  · G1 新颖性 PASS   │
│  Footer (opencode-tui · 1.0)  │                     │
└─────────────────────────────────┴─────────────────────┘
```

### 键盘快捷键

| 按键 | 功能 |
|---|---|
| `Enter` | 发送消息 |
| `Esc` | 聚焦输入框 |
| `Ctrl+L` | 清空聊天 |
| `q` | 退出 |

### TUI 命令

在输入框输入以下命令：

| 命令 | 功能 |
|---|---|
| `/help` | 显示所有命令 |
| `/clear` | 清空聊天历史 |
| `/mode redis` | 切换到 Redis 后端 |
| `/mode opencode` | 切换到 opencode 后端 |
| `/status` | 查看连接状态和后端信息 |
| `/connect` | 重新连接当前后端 |
| `/diag` | 诊断信息（phase/cost/gate/budget 详情） |

切换后端示例：

```
/mode opencode   → 切换到 opencode，自动连 :4096
/mode redis      → 切回 Redis，自动连 localhost:6379
/status          → 显示 "◉ opencode (connected)"
```

### 发送消息

- 非命令文本直接按 Enter 发送
- Redis 模式：消息发布到 `academic:inbox`，由 pipeline 处理
- OpenCode 模式：发送 prompt 到当前 session，LLM 回复流式显示在聊天中
- 未连接后端时：本地回显演示模式

### 仪表板 Widget

| Widget | 显示内容 | 数据源 |
|---|---|---|
| **ProjectInfo** | 项目标题 + 连接状态 + 后端模式 | poll 3s 或 event |
| **PhaseRing** | 6 阶段进度图标：pending(·) / running(▸) / done(✓) / error(✗) | poll 3s 或 event |
| **CostBudget** | Session/Task 进度条 + 累计 USD cost | poll 3s |
| **GateStatus** | 7 门评审：PASS/REVISE/FAIL + fusion ⚡ | poll 3s 或 event |
| **AgentActivity** | 实时 agent/gate/budget 事件日志，按 tier 着色 | 实时 event |

---

## OpenCode 集成

opencode-tui 附带完整的 `.opencode/` 配置，可直接在 opencode 中使用。

### 注册到 opencode

在 opencode 项目目录中引用或复制：

```jsonc
// opencode.jsonc 或 .opencode/opencode.jsonc
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

### Agent（opencode 原生调度）

`.opencode/agent/` 中的 6 个 agent 定义，opencode 启动时自动发现：

| Agent | Model | Role | 允许的工具 |
|---|---|---|---|
| `literature-researcher` | deepseek-v4-flash | 文献检索与综述 | Bash, Read, WebFetch, Grep |
| `methodologist` | deepseek-v4-pro | 方法设计 | Bash, Read, Write, WebFetch |
| `code-engineer` | deepseek-v4-flash | 代码实现 | Bash, Read, Edit, Write, Grep |
| `visualization-designer` | deepseek-v4-flash | 可视化出图 | Bash, Read, Edit, Write |
| `citation-auditor` | deepseek-v4-flash | 引用审计 | Bash, Read, WebFetch |
| `academic-editor` | deepseek-v4-pro | 论文润色 | Bash, Read, Edit, Write |

在 opencode 中切换 agent：

```
/agent literature-researcher
/agent code-engineer
```

### Phase 命令

`.opencode/command/` 中的 6 个 slash 命令：

```
/phase0 "研究标题"    # 环境初始化
/phase1               # 文献调研
/phase2               # 方案设计
/phase3               # 实验验证
/phase4               # 代码实现
/phase5               # 论文撰写
```

每个命令定义了该阶段的具体步骤，open code 会按 prompt 逐一执行。

### MCP Server（6 个 tool）

`academic_mcp/academic_server.py` 注册到 opencode 后，在聊天中直接调用：

```
调用 research-director 查看管线状态
调用 experimenter 启动实验 exp_001
调用 paper-writer 写摘要
调用 academic-reviewer 评审当前论文
```

| Tool | 参数 | 功能 |
|---|---|---|
| `research-director` | `action: start/status/skip/stop` | 管线编排 |
| `experimenter` | `action: design/run/monitor/report` | 实验管理 |
| `scientific-computing-engineer` | `action: check_gpu/optimize/profile/fix_numerical` | GPU/计算 |
| `paper-writer` | `section: abstract/intro/method/experiments/conclusion/full` | 论文撰写 |
| `method-reviewer` | `action: review_method/check_novelty/check_reproducibility` | 方法评审 |
| `academic-reviewer` | `review_type: full/novelty/experiments/writing` | 完整评审 |

### Pipeline Skill

`.opencode/skills/pipeline/SKILL.md` 定义了完整管线编排流程：

```
Phase 0: 环境初始化    → G1 学术新颖性
Phase 1: 文献调研      → G2 实验设计 (fusion)
Phase 2: 方案设计      → G3 方法论
Phase 3: 实验验证      → G4 数据分析
Phase 4: 代码实现      → G5 逻辑一致性 (fusion)
Phase 5: 论文撰写      → G6 可复现性 → G7 终审 (fusion)
```

在 opencode 中加载 skill：

```
/skill pipeline
```

### 典型工作流

```text
1. 启动 opencode serve
2. python -m opencode_tui --mode opencode
3. 在 TUI 中：输入 "研究旋转机械故障诊断"
4. opencode 后端创建 session，LLM 开始推理
5. TUI 实时显示流式文本、工具调用、推理过程
6. 结果在聊天面板中完整展示
7. 如需切换回 Redis 管线：/mode redis
```

---

## 架构

```
┌───────────────────────────────────────────────────┐
│            opencode-tui (Python/Textual)            │
│  Chat + PhaseRing + CostBudget + GateStatus        │
│  [/mode redis  |  /mode opencode]                   │
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

## 事件流

### Redis 模式

```
TUI 输入 text → academic:inbox (pub) → academic_loop.py
                                       → academic:progress (pub) → TUI 更新 widget
                                       → academic:outbox (pub) → TUI 显示回复
```

### OpenCode 模式

```
TUI 输入 text → POST /session/:id/message  → opencode LLM
              → GET /event (SSE)
              ← message.part.updated (text/tool/reasoning 流式)
              ← session.status (idle → 完成)
              ← permission.asked (自动 reply once)
```

## 文件结构

```
/home/opencode/ATTM/opencode-tui/
├── pyproject.toml               # 依赖：textual, httpx, redis, mcp
├── src/opencode_tui/             # TUI 核心代码
│   ├── app.py                   # 主 App — 布局 + 事件流 + 命令路由
│   ├── __main__.py              # python -m 入口
│   ├── theme.py / css.py        # opencode 色板 + CSS
│   ├── backend/                 # Redis / opencode 双后端
│   ├── client/                  # opencode HTTP 客户端 + SSE 解析
│   └── widgets/                 # 7 个 widget + spinner + message 渲染
├── academic_mcp/                # Python MCP server（6 tool）
├── .opencode/                   # opencode 集成
│   ├── opencode.jsonc           # provider + mcp + permission 配置
│   ├── agent/                   # 6 agent 定义
│   ├── command/                 # 6 phase 命令
│   └── skills/pipeline/         # 管线编排 skill
└── tests/                       # 28 项测试
```

## 测试

```bash
cd /home/opencode/ATTM/opencode-tui
python -m pytest tests/ -v
```

28 项测试：
- SSE 解析（8）：单事件/多事件/注释/空数据/非法 JSON
- 色板 token（7）：primary/secondary/accent/phase/gate/fusion
- 消息渲染（9）：bar_message/user/assistant/system/tool_header/output/footer
- 事件类（3）：PhaseEvent/ChatMessage/BackendStatusEvent
