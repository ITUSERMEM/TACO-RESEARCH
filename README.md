# Academic Team — Multi-Agent Autonomous Research System

A Kocoro-inspired multi-agent system for autonomous academic research.
Orchestrates 12 AI agents through a Phase 0-5 research pipeline with
LLM-powered review gates, persistent memory, and self-improvement mechanisms.

## Three-Model Architecture

| Role | Model | API Endpoint | Used For |
|------|-------|-------------|----------|
| **Executor** | deepseek-v4-flash | opencode.ai Zen | Agent iteration, writing, tools |
| **Reviewer** | glm-5.2 | Volcengine ark | Gate evaluation, summarization |
| **Pro** | deepseek-v4-pro | api.deepseek.com | Deep audit, proof check, citation |

## System Architecture

```
Telegram ──→ Bridge ──→ Redis Pub/Sub ──→ AcademicLoop Daemon
                                                │
                                    ┌───────────┴───────────┐
                                    │  _run_pipeline()      │
                                    │  Phase 0 → 5          │
                                    │    Agent → skill→ LLM │
                                    │    Gate → pass/revise  │
                                    └───────────┬───────────┘
                                                │
                     progress ────→ Telegram ←──┘
                     result   ────→ Telegram
```

## 12 Agents

| Layer | Agent | Skills |
|-------|-------|--------|
| **Director** | research-director | pipeline orchestration, decisions |
| | academic-editor | paper compilation, rebuttal |
| **Research** | literature-researcher | paper search, review writing |
| | methodologist | idea generation, experiment design |
| | experimenter | GPU experiments, result analysis |
| | scientific-computing-engineer | ML implementation, data processing |
| | code-engineer | TDD, automation, CI/CD |
| | paper-writer | LaTeX drafting, citation management |
| | visualization-designer | figures, slides, diagrams |
| **Review** | method-reviewer | proof checking, adversarial review |
| | academic-reviewer | experiment audit, claim verification |
| | citation-auditor | BibTeX verification, context check |

## Phase 0-5 Pipeline

```
Phase 0 ─→ Phase 1 ─→ Phase 2 ─→ Phase 3 ─→ Phase 4 ─→ Phase 5
  Init      Literature   Method     Experiment  Coding     Paper
  Setup     Review       Design     Validation  Writing    Writing
              │             │           │          │          │
           Gate 1       Gate 2       Gate 3    Gates 4-7   Submit
         Novelty      Method       Experiment  Claim +     v
         Check        Adversarial  Audit       Citation
```

## Quick Start

### Prerequisites

- Docker (for Redis Stack)
- Python 3.12+
- API keys for three LLM endpoints

### Installation

```bash
# 1. Start Redis Stack
docker run -d --name redis-stack -p 6379:6379 \
  -v /data/redis-stack:/var/lib/redis-stack \
  --restart=unless-stopped \
  redis/redis-stack-server:latest \
  redis-stack-server --appendonly yes

# 2. Install dependencies
pip install -r redis-memory/requirements.txt
pip install -r telegram_bridge/requirements.txt

# 3. Set environment variables
export ZEN_API_KEY="your-zen-api-key"
export ARK_API_KEY="your-volcengine-ark-token"
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"

# 4. Run pipeline
python3 -c "
from academic_loop import AcademicLoop, Phase
loop = AcademicLoop(project_title='My Research')
loop.run(start_phase=Phase.PHASE0, end_phase=Phase.PHASE1)
"

# 5. Or start the team launcher (including Telegram bridge)
python3 redis-memory/team_launcher.py --project "Research Topic"
```

### Run Tests

```bash
cd redis-memory
python3 -m pytest tests/ -v --tb=short
# Expected: 128 passed, 0 failed
```

## Systemd Deployment (Linux)

```bash
# Copy service files
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable --now redis-stack
sudo systemctl enable --now opencode-academic-team
sudo systemctl enable --now opencode-telegram-bridge

# Check status
curl http://127.0.0.1:9333/health
```

Edit `/etc/systemd/system/opencode-academic-team.service` to add your API keys:
```
Environment=ZEN_API_KEY=your-key
Environment=ARK_API_KEY=your-key
Environment=DEEPSEEK_API_KEY=your-key
```

## Telegram Bot Setup

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Set the token as `TELEGRAM_BOT_TOKEN` environment variable
3. The bridge auto-connects when `team_launcher.py` is running

The bridge supports two routing modes:
- **AcademicLoop mode** (default when daemon is running)
- **tmux fallback** (direct opencode interaction)

Commands:
- `/status` — View current pipeline status
- `/stop` — Stop running pipeline
- Send any research topic to start Phase 0-5 automatically

## Project Structure

```
academic-team/
├── redis-memory/           # Core modules (40+ files)
│   ├── academic_loop.py    # Phase 0-5 orchestrator
│   ├── llm_client.py       # DualLLM three-model client
│   ├── gate_judge.py       # 7 LLM-powered review gates
│   ├── loop_detector.py    # 9-path loop detection
│   ├── persist_learnings.py # Kocoro memory pipeline
│   ├── permissions.py      # 7-level permission system
│   ├── hallucination_guard.py # 3-layer hallucination detection
│   ├── team_launcher.py    # Unified startup
│   ├── requirements.txt
│   └── tests/              # 128 tests, 14 test files
├── telegram_bridge/        # Telegram bot interface
│   ├── telegram_bridge.py
│   └── start_bridge.sh
├── systemd/                # System service units
│   ├── redis-stack.service
│   ├── opencode-academic-team.service
│   ├── opencode-telegram-bridge.service
│   └── aris-watchdog.service
├── skills/                 # OpenCode skills
│   └── academic-dev-pitfalls/SKILL.md
├── figures/
│   └── ascii_architecture.txt
├── README.md
└── .gitignore
```

## Development Constraints

The project includes a skill file documenting 45 verified bug patterns
encountered during development, organized into 6 categories:
infrastructure, Telegram bridge, orchestrator, module coding, testing,
and security. Load it via opencode's skill system before modifying code:

```
/root/.config/opencode/skills/academic-dev-pitfalls/SKILL.md
```

## Test Coverage

| Module | Tests |
|--------|-------|
| loop_detector | 22 |
| hallucination_guard | 12 |
| permissions | 15 |
| phase_state_machine | 12 |
| read_tracker | 6 |
| tool_result_budget | 8 |
| skill_executor | 8 |
| summarizer | 8 |
| persist_learnings | 10 |
| session_cache | 8 |
| scheduler | 8 |
| heartbeat | 6 |
| **Total** | **128** |

## License

MIT
