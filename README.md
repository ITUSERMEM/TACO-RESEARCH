# PolyAgent-Research

<p align="center">
  <a href="README_CN.md">🇨🇳 中文版</a>
</p>

> Multi-agent autonomous academic research pipeline — 12 AI agents collaborate from literature review to paper submission.

![Python 3.12](https://img.shields.io/badge/Python-3.12+-3776AB)
![Tests](https://img.shields.io/badge/Tests-269_passing-success)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Agents](https://img.shields.io/badge/Agents-21-blueviolet)
![Pipeline](https://img.shields.io/badge/Pipeline-Phase_0–5-ff6b6b)

---

## ✨ Highlights

- **🧠 21 specialized agents** — 12 original + 9 new specialists (statistical-reviewer, fact-checker, ethics-reviewer, and more)
- **🔄 Phase 0–5 automation** — environment init → literature review → method design → experiment → coding → paper writing
- **🔍 7 LLM-powered review gates** — critical gates (G2/G5/G7) use **dual-model Fusion voting** for higher reliability
- **🎯 Three-model routing w/ ComplexityRouter** — AGENT\_TIER dispatches by task; ComplexityRouter dynamically adjusts iteration budgets based on task complexity
- **💰 CostLedger + TokenBudget** — Redis append-only cost ledger with snapshotMax reconciliation; 3-layer token budget with auto-degrade chain (large→medium→small)
- **🛡️ SkillContract runtime protection** — gray-release observation mode + blocking mode to guard the pipeline
- **💬 Telegram Interview** — before launching the pipeline, assesses task clarity and asks clarifying questions via InlineKeyboard
- **📡 Remote control via Telegram** — launch pipelines, check progress, receive results from anywhere
- **🏭 Production-grade systemd deployment** — 4 systemd services with auto-restart

---

## 🏗️ Architecture

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

User sends a research topic via Telegram → AcademicLoop launches Phase 0–5 pipeline → each phase runs agents calling skills → Gate Judge reviews results → pass to proceed or revise.

---

## ⚡ Quick Start

### Prerequisites

- Docker (Redis Stack)
- Python 3.12+
- 3 LLM API keys (Zen / Ark / DeepSeek)

### Setup

```bash
# 1. Start Redis Stack
docker run -d --name redis-stack -p 6379:6379 \
  -v /data/redis-stack:/data \
  redis/redis-stack-server --appendonly yes

# 2. Install dependencies
pip install -r redis-memory/requirements.txt
pip install -r telegram_bridge/requirements.txt

# 3. Set environment variables
export ZEN_API_KEY="your-key"       # Executor: deepseek-v4-flash
export ARK_API_KEY="your-key"       # Reviewer: glm-5.2
export DEEPSEEK_API_KEY="your-key"  # Pro: deepseek-v4-pro
export TELEGRAM_BOT_TOKEN="your-token"

# 4. Launch (auto-listens on Telegram, starts pipeline on topic)
python3 redis-memory/team_launcher.py --project "My Research"
```

### Run Tests

```bash
cd redis-memory && pytest tests/ -v --tb=short
# Expected: 224 passed, 0 failed
```

---

## 🧑‍🔬 21 Agents

| Layer | Agent | Core Capability |
|-------|-------|-----------------|
| **Director** | Research Director | Pipeline orchestration, decision making |
| | Academic Editor | Paper compilation, rebuttal |
| **Research** | Literature Researcher | Paper search, review writing |
| | Methodologist | Idea generation, experiment design |
| | Experimenter | GPU experiments, result analysis |
| | Scientific Computing Engineer | ML implementation, data processing |
| | Code Engineer | TDD, automation, CI/CD |
| | Paper Writer | LaTeX drafting, citation management |
| | Visualization Designer | Figures, slides, diagrams |
| **Review** | Method Reviewer | Proof checking, adversarial review |
| | Academic Reviewer | Experiment audit, claim verification |
| | Citation Auditor | BibTeX verification, context check |
| | Statistical Reviewer | Statistical method audit, p-hacking detection |
| | Math Checker | Derivation verification, dimensional consistency |
| | Reproducibility Auditor | Seed/version/environment rerun checks |
| | Data Validator | Dataset quality profiling |
| | Fact Checker | Scientific claim verification against sources |
| | Protocol Writer | Experimental SOP/protocol drafting |
| | Results Interpreter | Result analysis, alternative explanations |
| **Writing** | Abstract Writer | Abstracts, summaries, lay explanations |
| | Ethics Reviewer | Research ethics, dual-use, privacy review |

Each agent is routed to the appropriate LLM tier via AGENT\_TIER: simple retrieval → Reviewer (glm-5.2), routine execution → Executor (deepseek-v4-flash), complex reasoning → Pro (deepseek-v4-pro).

---

## 🎯 Three-Model Routing

| Role | Model | Endpoint | Responsible For |
|------|-------|----------|-----------------|
| **Executor** | deepseek-v4-flash | opencode.ai Zen | Default execution: experiments, figures, code |
| **Reviewer** | glm-5.2 | Volcengine Ark | Review & retrieval: literature, gates, polish |
| **Pro** | deepseek-v4-pro | api.deepseek.com | Complex reasoning: paper writing, proof check, citation audit |

Covers 30+ skills: training/charting → Executor, literature search → Reviewer, paper/proof → Pro.

---

## 🗺️ Phase 0–5 Pipeline

```
Phase 0 ──→ Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4 ──→ Phase 5
 Init       Literature   Method     Experiment  Coding      Paper
 Setup      Review       Design     Validation  Writing     Submission
                │             │           │         │
             Gate 1       Gate 2       Gate 3    Gates 4+5   Gates 6+7
           Novelty      Method ★     Experiment  Claim +     Final Review ★
           Check        Adversarial  Audit       Citation    + Citation ★
                         ★ = Fusion voting (reviewer + pro dual-model panel)

---

## 💰 TokenBudget & CostLedger

| Feature | Mechanism | Details |
|---------|-----------|---------|
| **3-Layer Token Budget** | Call / Session / Task | Session: 500K, Task: 5M tokens. Auto-degrade large→medium→small |
| **CostLedger** | Redis append-only | `costs:{project}:{session}` List + `INCRBYFLOAT` project total |
| **snapshotMax** | Dual-measurement reconciliation | Max of stats-delta and turn-end tally prevents undercounting |
| **Agent/Subagent split** | Role-tagged entries | Separate `agent_usd` and `subagent_usd` in per-session summaries |
| **Budget enforcement** | O(1) check | `is_budget_exceeded()` reads running total, blocks at 100% |

## 🛡️ SkillContract Security Layers

| Layer | Mechanism | Description |
|-------|-----------|-------------|
| **L1** | Input validation | Phase compatibility, LaTeX closure, length check |
| **L2** | Entropy monitoring | Shannon entropy detects repetitive/degraded output |
| **L3** | Consensus voting | 3 independent calls, Reviewer adjudicates splits |
| **L4** | Root cause analysis | Pro model differential analysis of fail vs success logs |

Supports gray-release: start with `log_only=true` → observe → switch to blocking mode once stable.

---

## 🏭 Production Deployment

```bash
# Copy systemd services
cp systemd/*.service /etc/systemd/system/ && systemctl daemon-reload

# Start all services
systemctl enable --now redis-stack
systemctl enable --now opencode-academic-team
systemctl enable --now opencode-telegram-bridge

# Health check
curl http://127.0.0.1:9333/health
```

---

## 📁 Project Structure

```
PolyAgent-Research/
├── redis-memory/         # Core modules (55+ files)
│   ├── academic_loop.py  # Pipeline orchestrator
│   ├── agent_roster.py   # 21 expert definitions
│   ├── cost_ledger.py    # Append-only cost ledger
│   ├── llm_client.py     # Three-model client
│   ├── gate_judge.py     # 7 LLM review gates + Fusion voting
│   ├── skill_contract.py # Runtime safety layer
│   ├── fault_catalog.py  # 27 fault patterns
│   └── tests/            # 269 tests
├── telegram_bridge/      # Telegram bridge
├── systemd/              # 4 systemd services
├── skills/               # Skill definitions
└── figures/              # Architecture diagrams & paper figures

```

---

## 📚 References

| Project | GitHub | Description |
|---------|--------|-------------|
| **Kocoro** | [github.com/Kocoro-lab/Kocoro](https://github.com/Kocoro-lab/Kocoro) | Agent engine & daemon that inspired the Phase 0–5 orchestration pattern |
| **Shannon** | [github.com/Kocoro-lab/Shannon](https://github.com/Kocoro-lab/Shannon) | Multi-agent framework powering the three-model architecture and AGENT_TIER routing |
| **Scientific Agent Skills** | [github.com/K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 147 open-source scientific skills referenced for academic research workflows |
| **ARIS** | [github.com/wanshuiyin/Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) | Multi-agent autonomous research system — language switch pattern, project structure, and workflow design reference |
| **K-Dense BYOK** | [github.com/K-Dense-AI/k-dense-byok](https://github.com/K-Dense-AI/k-dense-byok) | Open-source research assistant — inspired Fusion voting, CostLedger snapshotMax, Interview clarification, and the 21-specialist agent model |

---

## 📄 License

MIT
