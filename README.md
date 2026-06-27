# PolyAgent-Research

> **EN** Multi-agent autonomous academic research pipeline — 12 AI agents collaborate from literature review to paper submission.
>
> **CN** 多智能体自动化科研管线 — 12 个 AI 智能体协同完成从文献调研到论文投稿的全流程。

![Python 3.12](https://img.shields.io/badge/Python-3.12+-3776AB)
![Tests](https://img.shields.io/badge/Tests-224_passing-success)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Agents](https://img.shields.io/badge/Agents-12-blueviolet)
![Pipeline](https://img.shields.io/badge/Pipeline-Phase_0–5-ff6b6b)

---

## ✨ Highlights / 亮点

- **🧠 12 specialized agents / 12 个领域智能体** — research director, literature researcher, method reviewer, paper writer, and more / 研究总监、文献研究员、方法评审、论文写手等角色各司其职
- **🔄 Phase 0–5 automation / Phase 0–5 全自动管线** — environment init → literature review → method design → experiment → coding → paper writing / 环境初始化 → 文献调研 → 方案设计 → 实验验证 → 代码实现 → 论文撰写
- **🔍 7 LLM-powered review gates / 7 道 LLM 评审门禁** — novelty, methodology, experiment audit, citation audit — automatic quality checks per phase / 新颖性、方法论、实验审计、引用审计，每个阶段自动质检
- **🎯 Three-model routing / 三模型路由** — AGENT\_TIER dispatches skills to Executor/Reviewer/Pro models based on task complexity / 根据 skill 类型自动分配 Executor/Reviewer/Pro 模型，不是用一个 flash 干所有活
- **🛡️ SkillContract runtime protection / SkillContract 运行时保护** — gray-release observation mode + blocking mode to guard the pipeline / 灰度发布 + 阻断模式，防止非法输入进入管线
- **📡 Remote control via Telegram / Telegram 远程操控** — launch pipelines, check progress, receive results from anywhere / 随时随地启动管线、查看进度、接收结果
- **🏭 Production-grade systemd deployment / Systemd 生产部署** — 4 systemd services with auto-restart / 4 个 systemd 服务，开机自启，自动恢复

---

## 🏗️ Architecture / 架构概览

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

**EN** User sends a research topic via Telegram → AcademicLoop launches Phase 0–5 pipeline → each phase runs agents calling skills → Gate Judge reviews results → pass to proceed or revise.

**CN** 用户通过 Telegram 发送研究主题 → AcademicLoop 启动 Phase 0–5 管线 → 每个阶段 Agent 调用 Skill 执行任务 → 阶段结束后 Gate Judge 评审 → 通过进入下一阶段。

---

## ⚡ Quick Start / 快速开始

### Prerequisites / 前置要求

- Docker (Redis Stack)
- Python 3.12+
- 3 LLM API keys (Zen / Ark / DeepSeek)

### Setup / 安装与运行

```bash
# 1. Start Redis Stack / 启动 Redis Stack
docker run -d --name redis-stack -p 6379:6379 \
  -v /data/redis-stack:/data \
  redis/redis-stack-server --appendonly yes

# 2. Install dependencies / 安装依赖
pip install -r redis-memory/requirements.txt
pip install -r telegram_bridge/requirements.txt

# 3. Set environment variables / 配置环境变量
export ZEN_API_KEY="your-key"       # Executor: deepseek-v4-flash
export ARK_API_KEY="your-key"       # Reviewer: glm-5.2
export DEEPSEEK_API_KEY="your-key"  # Pro: deepseek-v4-pro
export TELEGRAM_BOT_TOKEN="your-token"

# 4. Launch / 启动
python3 redis-memory/team_launcher.py --project "My Research"
```

### Run Tests / 运行测试

```bash
cd redis-memory && pytest tests/ -v --tb=short
# Expected: 224 passed, 0 failed / 预期：224 通过，0 失败
```

---

## 🧑‍🔬 12 Agents / 12 个智能体

| Layer / 层级 | Agent / 智能体 | Core Capability / 核心能力 |
|-------|--------|-----------------|
| **Director / 指挥** | Research Director / 研究项目总监 | Pipeline orchestration, decision making / 管线编排、决策调度 |
| | Academic Editor / 学术编辑 | Paper compilation, rebuttal / 论文编译、Rebuttal |
| **Research / 研究** | Literature Researcher / 文献研究员 | Paper search, review writing / 论文检索、综述写作 |
| | Methodologist / 方法论研究员 | Idea generation, experiment design / Idea 生成、实验设计 |
| | Experimenter / 实验工程师 | GPU experiments, result analysis / GPU 实验、结果分析 |
| | Scientific Computing Engineer / 科学计算工程师 | ML implementation, data processing / ML 实现、数据处理 |
| | Code Engineer / 代码工程师 | TDD, automation, CI/CD |
| | Paper Writer / 论文写手 | LaTeX drafting, citation management / LaTeX 起草、引用管理 |
| | Visualization Designer / 可视化设计师 | Figures, slides, diagrams / 图表、幻灯片、示意图 |
| **Review / 评审** | Method Reviewer / 方法评审员 | Proof checking, adversarial review / 证明检查、对抗性评审 |
| | Academic Reviewer / 学术评审员 | Experiment audit, claim verification / 实验审计、Claim 验证 |
| | Citation Auditor / 引用审计员 | BibTeX verification, context check / BibTeX 验证、上下文检查 |

**EN** Each agent is routed to the appropriate LLM tier via AGENT\_TIER: simple retrieval → Reviewer (glm-5.2), routine execution → Executor (deepseek-v4-flash), complex reasoning → Pro (deepseek-v4-pro).

**CN** 每个智能体通过 AGENT\_TIER 自动分配到适合的 LLM 层级：简单检索 → Reviewer（glm-5.2），常规执行 → Executor（deepseek-v4-flash），复杂推理 → Pro（deepseek-v4-pro）。

---

## 🎯 Three-Model Routing / 三模型路由

| Role / 角色 | Model / 模型 | Endpoint / 端点 | Responsible For / 负责任务 |
|------|------|----------|-----------------|
| **Executor** | deepseek-v4-flash | opencode.ai Zen | Default execution: experiments, figures, code / 默认执行：实验、图表、代码 |
| **Reviewer** | glm-5.2 | Volcengine Ark | Review & retrieval: literature, gates, polish / 评审与检索：文献、门禁、润色 |
| **Pro** | deepseek-v4-pro | api.deepseek.com | Complex reasoning: paper writing, proof check, citation audit / 复杂推理：论文写作、证明核验、引用审计 |

**EN** Covers 30+ skills: training/charting → Executor, literature search → Reviewer, paper/proof → Pro.

**CN** 路由表覆盖 30+ skill，训练/图表类 → Executor，文献检索 → Reviewer，论文/证明 → Pro。

---

## 🗺️ Phase 0–5 Pipeline / 管线流程

```
Phase 0 ──→ Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4 ──→ Phase 5
 Init       Literature   Method     Experiment  Coding      Paper
 Setup      Review       Design     Validation  Writing     Submission
               │             │           │         │
            Gate 1       Gate 2       Gate 3    Gates 4+5   Gates 6+7
          Novelty      Method       Experiment  Claim +     Final Review
          Check        Adversarial  Audit       Citation    + Citation
```

---

## 🛡️ SkillContract Security Layers / 安全层

| Layer / 层 | Mechanism / 机制 | Description / 说明 |
|-------|-----------|-------------|
| **L1** | Input validation / 输入验证 | Phase compatibility, LaTeX closure, length check / Phase 兼容性、LaTeX 闭合、长度检查 |
| **L2** | Entropy monitoring / 熵监控 | Shannon entropy detects repetitive/degraded output / 香农熵检测重复/退化输出 |
| **L3** | Consensus voting / 一致性投票 | 3 independent calls, Reviewer adjudicates splits / 3 次独立调用，Reviewer 裁决分歧 |
| **L4** | Root cause analysis / 根因分析 | Pro model differential analysis of fail vs success logs / Pro 模型差分分析失败 vs 成功日志 |

**EN** Supports gray-release: start with `log_only=true` → observe → switch to blocking mode once stable.

**CN** 支持灰度发布模式：先 `log_only=true` 观测 → 确认无误后开启阻断模式。

---

## 🏭 Production Deployment / 生产部署

```bash
# Copy systemd services / 复制 systemd 服务
cp systemd/*.service /etc/systemd/system/ && systemctl daemon-reload

# Start all services / 启动全部服务
systemctl enable --now redis-stack
systemctl enable --now opencode-academic-team
systemctl enable --now opencode-telegram-bridge

# Health check / 查看健康状态
curl http://127.0.0.1:9333/health
```

---

## 📁 Project Structure / 项目结构

```
PolyAgent-Research/
├── redis-memory/         # Core modules / 核心模块（50+ files）
│   ├── academic_loop.py  # Pipeline orchestrator / 管线编排器
│   ├── llm_client.py     # Three-model client / 三模型客户端
│   ├── gate_judge.py     # 7 LLM review gates / 7 门 LLM 评审
│   ├── skill_contract.py # Runtime safety layer / 运行时安全层
│   ├── fault_catalog.py  # 27 fault patterns / 27 故障模式
│   └── tests/            # 224 tests / 224 项测试
├── telegram_bridge/      # Telegram bridge / Telegram 桥接
├── systemd/              # 4 systemd services / 4 个 Systemd 服务
├── skills/               # Skill definitions / 技能文件
└── figures/              # Architecture diagrams & paper figures / 架构图与论文插图
```

---

## 📊 Test Coverage / 测试覆盖

| Module / 模块 | Tests / 测试数 |
|--------|-------|
| Pipeline orchestration / 管线编排 | 38 |
| Loop detection / 循环检测 | 22 |
| SkillContract | 38 |
| Session & scheduling / 会话与调度 | 30 |
| Permissions & hallucination / 权限与幻觉 | 27 |
| Summary & persistence / 摘要与持久化 | 25 |
| Tool budget & heartbeat / 工具预算与心跳 | 20 |
| Fault / Adversarial / 故障与对抗测试 | 12 |
| LLM integration (slow) / LLM 集成（慢） | 11 |
| **Total / 合计** | **224** |

---

---

## 📚 References / 参考项目

| Project / 项目 | GitHub | Description / 说明 |
|-----------|--------|-------------|
| **Kocoro** | [github.com/Kocoro-lab/Kocoro](https://github.com/Kocoro-lab/Kocoro) | Agent engine & daemon that inspired the Phase 0–5 orchestration pattern / 启发了 Phase 0–5 编排模式的智能体引擎 |
| **Shannon** | [github.com/Kocoro-lab/Shannon](https://github.com/Kocoro-lab/Shannon) | Multi-agent framework powering the three-model architecture and AGENT_TIER routing / 支撑三模型架构和 AGENT_TIER 路由的多智能体框架 |
| **Scientific Agent Skills** | [github.com/K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 147 open-source scientific skills referenced for academic research workflows / 147 个开源科研技能，为学术研究工作流提供参考 |

---

## 📄 License / 许可

MIT
