# 科研牛马Agent

<p align="center">
  <a href="README_CN.md">🇨🇳 中文版</a>
</p>

> Your research paper, autonomously. From one Telegram message to submission-ready draft — 21 AI agents, 5 phases, 7 review gates.

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12%2B-3776AB">
  <img alt="Tests" src="https://img.shields.io/badge/Tests-269_passing-success">
  <img alt="Agents" src="https://img.shields.io/badge/Agents-21-blueviolet">
  <img alt="Pipeline" src="https://img.shields.io/badge/Pipeline-Phase_0–5-ff6b6b">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-yellow">
</p>

---

## 🚀 Quick Start

```bash
pip install -r redis-memory/requirements.txt -r telegram_bridge/requirements.txt
export TELEGRAM_BOT_TOKEN="your-token" ZEN_API_KEY="your-key" ARK_API_KEY="your-key" DEEPSEEK_API_KEY="your-key"
docker run -d --name redis-stack -p 6379:6379 redis/redis-stack-server --appendonly yes
python3 redis-memory/team_launcher.py --project "My Research"
```

Send a research topic to your Telegram bot. The pipeline takes it from there.

---

## 🧠 How It Works

```
  Telegram → Bridge → AcademicLoop Daemon
                         │
    Phase 0 → 1 → 2 → 3 → 4 → 5
    Init     Lit   Meth  Exp  Code  Paper
      │       │     │     │     │      │
      G1     G2★   G3   G4+5  G6    G7★
```

Each phase completes a research step, then hits a **Review Gate** before proceeding. Critical gates (★) use **Fusion voting** — reviewer + pro dual-model panel for decisions that matter.

---

## 👥 The 21

| 👔 Directors | 🔬 Researchers | 🔍 Reviewers | ✍️ Writers |
|---|---|---|---|
| Research Director | Literature Researcher | Method Reviewer | Abstract Writer |
| Academic Editor | Methodologist | Academic Reviewer | Ethics Reviewer |
| | Experimenter | Citation Auditor | |
| | SciComp Engineer | Statistical Reviewer | |
| | Code Engineer | Math Checker | |
| | Paper Writer | Reproducibility Auditor | |
| | Vis Designer | Data Validator | |
| | | Fact Checker | |
| | | Protocol Writer | |
| | | Results Interpreter | |

Every agent auto-routed to the right LLM tier — simple tasks → Executor, reviews → Reviewer, deep reasoning → Pro.

---

## ⚡ Three Brains, One Pipeline

| Tier | Model | Handles |
|------|-------|---------|
| ⚡ Executor | deepseek-v4-flash | Experiments, figures, code — the workhorse |
| 🧪 Reviewer | glm-5.2 | Literature, review gates, polish — the critic |
| 🧠 Pro | deepseek-v4-pro | Paper writing, proofs, audits — the deep thinker |

ComplexityRouter scores each task (0–1) and routes to the right tier. Simple tasks get the flash, hard problems get the pro.

---

## 💡 What Makes It Special

**🛡️ SkillContract** — 4-layer runtime safety: input validation → entropy monitoring → consensus voting → root cause analysis. Gray-release to block mode.

**💰 Cost Control** — Redis append-only ledger tracks every token spend. Triple-layer TokenBudget auto-degrades (large→medium→small) when running hot. No bill shock.

**💬 Telegram Interview** — Before launch, assesses task clarity and asks follow-up questions via InlineKeyboard. Vague briefs get caught early.

---

## 🏭 Production

```bash
cp systemd/*.service /etc/systemd/system/ && systemctl daemon-reload
systemctl enable --now redis-stack opencode-academic-team opencode-telegram-bridge
curl http://127.0.0.1:9333/health
```

4 systemd services, auto-restart, health checks.

---

## 📁 Structure

```
├── redis-memory/       # Core: pipeline, agents, gates, contracts, tests
├── telegram_bridge/    # Telegram bot
├── systemd/            # Production services
├── skills/             # Skill definitions
└── figures/            # Diagrams
```

---

## 📚 Built Upon

[Kocoro](https://github.com/Kocoro-lab/Kocoro) · [Shannon](https://github.com/Kocoro-lab/Shannon) · [Scientific Agent Skills](https://github.com/K-Dense-AI/scientific-agent-skills) · [ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) · [K-Dense BYOK](https://github.com/K-Dense-AI/k-dense-byok)

---

## 📄 License

MIT
