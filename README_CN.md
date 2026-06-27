# PolyAgent-Research

<p align="center">
  <a href="README.md">🇬🇧 English</a>
</p>

> 多智能体自动化科研管线 — 12 个 AI 智能体协同完成从文献调研到论文投稿的全流程。

![Python 3.12](https://img.shields.io/badge/Python-3.12+-3776AB)
![Tests](https://img.shields.io/badge/Tests-269_passing-success)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Agents](https://img.shields.io/badge/Agents-21-blueviolet)
![Pipeline](https://img.shields.io/badge/Pipeline-Phase_0–5-ff6b6b)

---

## ✨ 亮点

- **🧠 21 个领域智能体** — 原 12 个 + 新增 9 个专家（统计评审、事实核查、伦理审查等）
- **🔄 Phase 0–5 全自动管线** — 环境初始化 → 文献调研 → 方案设计 → 实验验证 → 代码实现 → 论文撰写
- **🔍 7 道 LLM 评审门禁** — 关键门禁（G2/G5/G7）启用 **双模型 Fusion 投票**，大幅提升判断可靠性
- **🎯 三模型路由 + ComplexityRouter** — AGENT\_TIER 分配合适模型；ComplexityRouter 根据任务复杂度动态调整迭代预算
- **💰 CostLedger + TokenBudget** — Redis 追加式成本账本 + snapshotMax 对账；三层 token 预算自动降级（large→medium→small）
- **🛡️ SkillContract 运行时保护** — 灰度发布 + 阻断模式，防止非法输入进入管线
- **💬 Telegram 交互式澄清** — 启动管线前评估任务清晰度，通过 InlineKeyboard 发起追问
- **📡 Telegram 远程操控** — 随时随地启动管线、查看进度、接收结果
- **🏭 Systemd 生产部署** — 4 个 systemd 服务，开机自启，自动恢复

---

## 🏗️ 架构概览

```
Telegram ──→ Telegram Bridge ──→ Redis Pub/Sub ──→ AcademicLoop Daemon
                                                       │
                                           ┌───────────┴───────────┐
                                           │   Phase 0 → 1 → 2    │
                                           │   → 3 → 4 → 5        │
                                           │    12 Agents          │
                                           │    7 Review Gates     │
                                           └───────────┬───────────┘
                                                       │
                                    progress/result ────┘
                                             ↓
                                        Telegram
```

用户通过 Telegram 发送研究主题 → AcademicLoop 启动 Phase 0–5 管线 → 每个阶段 Agent 调用 Skill 执行任务 → 阶段结束后 Gate Judge 评审 → 通过进入下一阶段。

---

## ⚡ 快速开始

### 前置要求

- Docker（Redis Stack）
- Python 3.12+
- 3 组 LLM API Key（Zen / Ark / DeepSeek）

### 安装与运行

```bash
# 1. 启动 Redis Stack
docker run -d --name redis-stack -p 6379:6379 \
  -v /data/redis-stack:/data \
  redis/redis-stack-server --appendonly yes

# 2. 安装依赖
pip install -r redis-memory/requirements.txt
pip install -r telegram_bridge/requirements.txt

# 3. 配置环境变量
export ZEN_API_KEY="your-key"       # Executor: deepseek-v4-flash
export ARK_API_KEY="your-key"       # Reviewer: glm-5.2
export DEEPSEEK_API_KEY="your-key"  # Pro: deepseek-v4-pro
export TELEGRAM_BOT_TOKEN="your-token"

# 4. 启动（自动监听 Telegram，收到研究主题即启动管线）
python3 redis-memory/team_launcher.py --project "My Research"
```

### 运行测试

```bash
cd redis-memory && pytest tests/ -v --tb=short
# 预期：224 通过，0 失败
```

---

## 🧑‍🔬 21 个智能体

| 层级 | 智能体 | 核心能力 |
|------|--------|---------|
| **指挥** | 研究项目总监 | 管线编排、决策调度 |
| | 学术编辑 | 论文编译、Rebuttal |
| **研究** | 文献研究员 | 论文检索、综述写作 |
| | 方法论研究员 | Idea 生成、实验设计 |
| | 实验工程师 | GPU 实验、结果分析 |
| | 科学计算工程师 | ML 实现、数据处理 |
| | 代码工程师 | TDD、自动化、CI/CD |
| | 论文写手 | LaTeX 起草、引用管理 |
| | 可视化设计师 | 图表、幻灯片、示意图 |
| **评审** | 方法评审员 | 证明检查、对抗性评审 |
| | 学术评审员 | 实验审计、Claim 验证 |
| | 引用审计员 | BibTeX 验证、上下文检查 |
| | 统计评审员 | 统计方法审计、p-hacking 检测 |
| | 数学检验员 | 公式推导验证、量纲一致性 |
| | 可复现性审计员 | 种子/版本/环境复现检查 |
| | 数据验证员 | 数据集质量分析 |
| | 事实核查员 | 科学声明溯源验证 |
| | 协议编写员 | 实验 SOP/协议编写 |
| | 结果解读者 | 结果分析、替代假说 |
| **写作** | 摘要写手 | 摘要、总结、通俗解释 |
| | 伦理审查员 | 研究伦理、双用风险、隐私审查 |

每个智能体通过 AGENT\_TIER 自动分配到适合的 LLM 层级：简单检索 → Reviewer（glm-5.2），常规执行 → Executor（deepseek-v4-flash），复杂推理 → Pro（deepseek-v4-pro）。

---

## 🎯 三模型路由

| 角色 | 模型 | 端点 | 负责任务 |
|------|------|------|---------|
| **Executor** | deepseek-v4-flash | opencode.ai Zen | 默认执行：实验、图表、代码 |
| **Reviewer** | glm-5.2 | Volcengine Ark | 评审与检索：文献、门禁、润色 |
| **Pro** | deepseek-v4-pro | api.deepseek.com | 复杂推理：论文写作、证明核验、引用审计 |

路由表覆盖 30+ skill，训练/图表类 → Executor，文献检索 → Reviewer，论文/证明 → Pro。

---

## 🗺️ Phase 0–5 管线

```
Phase 0 ──→ Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4 ──→ Phase 5
 Init       Literature   Method     Experiment  Coding      Paper
 Setup      Review       Design     Validation  Writing     Submission
                │             │           │         │
             Gate 1       Gate 2       Gate 3    Gates 4+5   Gates 6+7
           Novelty      Method ★     Experiment  Claim +     Final Review ★
           Check        Adversarial  Audit       Citation    + Citation ★
                         ★ = Fusion 投票（reviewer + pro 双模型 Panel）

---

## 💰 TokenBudget & CostLedger

| 特性 | 机制 | 说明 |
|------|------|------|
| **三层 Token 预算** | Call / Session / Task | Session: 50 万，Task: 500 万 token。自动降级 large→medium→small |
| **CostLedger** | Redis 追加式账本 | `costs:{project}:{session}` List + `INCRBYFLOAT` 项目总计 |
| **snapshotMax** | 双测量对账 | stats-delta 与 turn-end tally 取最大值，防止漏记 |
| **Agent/Subagent 分离** | 角色标记 | 每次记录区分 agent_usd 和 subagent_usd |
| **预算强制** | O(1) 检查 | `is_budget_exceeded()` 读取运行总计，100% 时阻断 |

## 🛡️ SkillContract 安全层

| 层 | 机制 | 说明 |
|----|------|------|
| **L1** | 输入验证 | Phase 兼容性、LaTeX 闭合、长度检查 |
| **L2** | 熵监控 | 香农熵检测重复/退化输出 |
| **L3** | 一致性投票 | 3 次独立调用，Reviewer 裁决分歧 |
| **L4** | 根因分析 | Pro 模型差分分析失败 vs 成功日志 |

支持灰度发布模式：先 `log_only=true` 观测 → 确认无误后开启阻断模式。

---

## 🏭 生产部署

```bash
# 复制 systemd 服务
cp systemd/*.service /etc/systemd/system/ && systemctl daemon-reload

# 启动全部服务
systemctl enable --now redis-stack
systemctl enable --now opencode-academic-team
systemctl enable --now opencode-telegram-bridge

# 查看健康状态
curl http://127.0.0.1:9333/health
```

---

## 📁 项目结构

```
PolyAgent-Research/
├── redis-memory/         # 核心模块（55+ 文件）
│   ├── academic_loop.py  # 管线编排器
│   ├── agent_roster.py   # 21 专家定义
│   ├── cost_ledger.py    # 追加式成本账本
│   ├── llm_client.py     # 三模型客户端
│   ├── gate_judge.py     # 7 门 LLM 评审 + Fusion 投票
│   ├── skill_contract.py # 运行时安全层
│   ├── fault_catalog.py  # 27 故障模式
│   └── tests/            # 269 项测试
├── telegram_bridge/      # Telegram 桥接
├── systemd/              # 4 个 Systemd 服务
├── skills/               # 技能文件
└── figures/              # 架构图与论文插图
```

---

## 📚 参考项目

| 项目 | GitHub | 说明 |
|------|--------|------|
| **Kocoro** | [github.com/Kocoro-lab/Kocoro](https://github.com/Kocoro-lab/Kocoro) | 智能体引擎，启发了 Phase 0–5 编排模式 |
| **Shannon** | [github.com/Kocoro-lab/Shannon](https://github.com/Kocoro-lab/Shannon) | 多智能体框架，支撑三模型架构和 AGENT_TIER 路由 |
| **Scientific Agent Skills** | [github.com/K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 147 个开源科研技能，为学术研究工作流提供参考 |
| **ARIS** | [github.com/wanshuiyin/Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) | 多智能体自动化科研系统 — 语言切换、项目结构、工作流设计参考 |
| **K-Dense BYOK** | [github.com/K-Dense-AI/k-dense-byok](https://github.com/K-Dense-AI/k-dense-byok) | 开源科研助手 — 启发了 Fusion 投票、CostLedger snapshotMax、Interview 澄清和 21 专家智能体模型 |

---

## 📄 许可

MIT
