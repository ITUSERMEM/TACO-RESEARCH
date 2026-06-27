---
name: phase1
description: Phase 1 - 文献调研
model: deepseek-v4-pro
---

Execute literature review for the given research topic:

Steps:
1. Invoke literature-researcher agent to search papers
2. Read and summarize 10-20 relevant papers
3. Identify research gaps and current SOTA
4. Generate structured literature survey
5. Output PHASE1_REPORT.md to project directory

The literature-researcher agent will use WebFetch to find papers.
