---
name: pipeline
description: Academic Pipeline orchestration skill. Load this when running multi-phase research workflows: Phase 0 (环境初始化) → Phase 1 (文献调研) → Phase 2 (方案设计) → Phase 3 (实验验证) → Phase 4 (代码实现) → Phase 5 (论文撰写). Each phase uses a specialized agent from the academic team and runs through GateJudge review before transitioning.
---

# Academic Pipeline

## Phase Flow
```
Phase 0: 环境初始化    → G1 学术新颖性
Phase 1: 文献调研      → G2 实验设计 (fusion)
Phase 2: 方案设计      → G3 方法论
Phase 3: 实验验证      → G4 数据分析
Phase 4: 代码实现      → G5 逻辑一致性 (fusion)
Phase 5: 论文撰写      → G6 可复现性 → G7 终审 (fusion)
```

## Quick Start
```
/phase0 "research topic"
# or full pipeline
/research "topic description"
```

## Gate Pass Criteria
- G1: Novelty score > 6/10
- G2: Experiment design covers key baselines
- G3: Method technically sound and reproducible
- G4: Results statistically significant
- G5: Claims supported by evidence
- G6: All code and data available
- G7: Paper submission ready

## Fusion Gates (G2, G5, G7)
These require dual-model review. Both models must pass.

## Context
- Pipeline orchestrator: academic_loop.py
- Redis state key: academic:phase:state
- Progress events: academic:progress (pub/sub)
- Agent registration: agent/*.md
- Phase commands: command/*.md
