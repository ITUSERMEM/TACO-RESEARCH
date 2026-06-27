# TACO-RESEARCH

> **T**eam **A**gent for **C**ode & **O**utput **R**esearch

<p align="center">
  <a href="README.md">🇬🇧 English</a>
</p>

> 一条 Telegram 消息 → 一份论文初稿。21 个 AI 智能体、5 个阶段、7 道门禁，全自动科研管线。

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12%2B-3776AB">
  <img alt="Tests" src="https://img.shields.io/badge/Tests-269_passing-success">
  <img alt="Agents" src="https://img.shields.io/badge/Agents-21-blueviolet">
  <img alt="Pipeline" src="https://img.shields.io/badge/Pipeline-Phase_0–5-ff6b6b">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-yellow">
</p>

---

## 🚀 快速开始

```bash
pip install -r redis-memory/requirements.txt -r telegram_bridge/requirements.txt
export TELEGRAM_BOT_TOKEN="your-token" ZEN_API_KEY="your-key" ARK_API_KEY="your-key" DEEPSEEK_API_KEY="your-key"
docker run -d --name redis-stack -p 6379:6379 redis/redis-stack-server --appendonly yes
python3 redis-memory/team_launcher.py --project "My Research"
```

给 Telegram 机器人发一个研究主题，剩下的交给管线。

---

## 🧠 工作原理

```
  Telegram → 桥接器 → AcademicLoop 守护进程
                         │
    Phase 0 → 1 → 2 → 3 → 4 → 5
    初始化   文献  方案  实验  编码  论文
      │       │     │     │     │      │
      G1     G2★   G3   G4+5  G6    G7★
```

每阶段完成后经过一道 **评审门禁** 才能进入下一阶段。关键门禁（★）启用 **Fusion 投票** — reviewer + pro 双模型 Panel 共同裁决。

---

## 👥 21 个智能体

| 👔 指挥 | 🔬 研究 | 🔍 评审 | ✍️ 写作 |
|---------|---------|---------|---------|
| 研究项目总监 | 文献研究员 | 方法评审员 | 摘要写手 |
| 学术编辑 | 方法论研究员 | 学术评审员 | 伦理审查员 |
| | 实验工程师 | 引用审计员 | |
| | 科学计算工程师 | 统计评审员 | |
| | 代码工程师 | 数学检验员 | |
| | 论文写手 | 可复现性审计员 | |
| | 可视化设计师 | 数据验证员 | |
| | | 事实核查员 | |
| | | 协议编写员 | |
| | | 结果解读者 | |

每个智能体自动分配到适合的模型层级：简单任务 → Executor，评审 → Reviewer，深度推理 → Pro。

---

## ⚡ 三模型，一条管线

| 层级 | 模型 | 负责 |
|------|------|------|
| ⚡ Executor | deepseek-v4-flash | 实验、图表、编码 — 干活主力 |
| 🧪 Reviewer | glm-5.2 | 文献检索、门禁评审、润色 — 把关 |
| 🧠 Pro | deepseek-v4-pro | 论文写作、证明核验、引用审计 — 深度思考 |

ComplexityRouter 对每个任务打分（0–1），自动路由到合适模型。简单问题用快模型，难题上 Pro。

---

## 💡 特别之处

**🛡️ SkillContract** — 4 层运行时安全：输入验证 → 熵监控 → 一致性投票 → 根因分析。灰度发布后一键开启阻断模式。

**💰 成本控制** — Redis 追加式账本记录每一笔 token 花费。三层 TokenBudget 超出阈值自动降级（大→中→小），杜绝意外超支。

**💬 Telegram 交互式澄清** — 启动前评估任务清晰度，不清晰时通过 InlineKeyboard 追问。模糊需求在源头被识别。

---

## 🏭 生产部署

```bash
cp systemd/*.service /etc/systemd/system/ && systemctl daemon-reload
systemctl enable --now redis-stack opencode-academic-team opencode-telegram-bridge
curl http://127.0.0.1:9333/health
```

4 个 systemd 服务，开机自启，健康检查，自动恢复。

---

## 📁 项目结构

```
├── redis-memory/       # 核心模块：管线、智能体、门禁、合约、测试
├── telegram_bridge/    # Telegram 机器人
├── systemd/            # 生产服务配置
├── skills/             # 技能定义
└── figures/            # 架构图
```

---

## 📚 参考项目

[Kocoro](https://github.com/Kocoro-lab/Kocoro) · [Shannon](https://github.com/Kocoro-lab/Shannon) · [Scientific Agent Skills](https://github.com/K-Dense-AI/scientific-agent-skills) · [ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) · [K-Dense BYOK](https://github.com/K-Dense-AI/k-dense-byok)

---

## 📄 许可

MIT
