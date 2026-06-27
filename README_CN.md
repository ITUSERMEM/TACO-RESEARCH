# PolyAgent-Research

<p align="center">
  <a href="README.md">🇬🇧 English</a>
</p>

> 多智能体自动化科研管线 — 12 个 AI 智能体协同完成从文献调研到论文投稿的全流程。

![Python 3.12](https://img.shields.io/badge/Python-3.12+-3776AB)
![Tests](https://img.shields.io/badge/Tests-224_passing-success)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Agents](https://img.shields.io/badge/Agents-12-blueviolet)
![Pipeline](https://img.shields.io/badge/Pipeline-Phase_0–5-ff6b6b)

---

## ✨ 亮点

- **🧠 12 个领域智能体** — 研究总监、文献研究员、方法评审、论文写手等角色各司其职
- **🔄 Phase 0–5 全自动管线** — 环境初始化 → 文献调研 → 方案设计 → 实验验证 → 代码实现 → 论文撰写
- **🔍 7 道 LLM 评审门禁** — 新颖性、方法论、实验审计、引用审计，每个阶段自动质检
- **🎯 三模型路由** — AGENT\_TIER 根据 skill 类型自动分配 Executor/Reviewer/Pro 模型，不是用一个 flash 干所有活
- **🛡️ SkillContract 运行时保护** — 灰度发布 + 阻断模式，防止非法输入进入管线
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

## 🧑‍🔬 12 个智能体

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
          Novelty      Method       Experiment  Claim +     Final Review
          Check        Adversarial  Audit       Citation    + Citation
```

---

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
├── redis-memory/         # 核心模块（50+ 文件）
│   ├── academic_loop.py  # 管线编排器
│   ├── llm_client.py     # 三模型客户端
│   ├── gate_judge.py     # 7 门 LLM 评审
│   ├── skill_contract.py # 运行时安全层
│   ├── fault_catalog.py  # 27 故障模式
│   └── tests/            # 224 项测试
├── telegram_bridge/      # Telegram 桥接
├── systemd/              # 4 个 Systemd 服务
├── skills/               # 技能文件
└── figures/              # 架构图与论文插图
```

---

## 📊 测试覆盖

| 模块 | 测试数 |
|------|-------|
| 管线编排 | 38 |
| 循环检测 | 22 |
| SkillContract | 38 |
| 会话与调度 | 30 |
| 权限与幻觉 | 27 |
| 摘要与持久化 | 25 |
| 工具预算与心跳 | 20 |
| 故障与对抗测试 | 12 |
| LLM 集成（慢） | 11 |
| **合计** | **224** |

---

## 📚 参考项目

| 项目 | GitHub | 说明 |
|------|--------|------|
| **Kocoro** | [github.com/Kocoro-lab/Kocoro](https://github.com/Kocoro-lab/Kocoro) | 智能体引擎，启发了 Phase 0–5 编排模式 |
| **Shannon** | [github.com/Kocoro-lab/Shannon](https://github.com/Kocoro-lab/Shannon) | 多智能体框架，支撑三模型架构和 AGENT_TIER 路由 |
| **Scientific Agent Skills** | [github.com/K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 147 个开源科研技能，为学术研究工作流提供参考 |

---

## 📄 许可

MIT
