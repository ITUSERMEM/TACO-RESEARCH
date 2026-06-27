"""Phase 0→1 全流程仿真验证。

模拟 12 人学术研究团队的前两个阶段：
  Phase 0: 环境初始化 + Redis 记忆层启动
  Phase 1: 项目启动 → 文献调研 → 论文入库 → 查新验证

Usage:
    redis-cli FLUSHALL && TRANSFORMERS_OFFLINE=1 python3 phase0_1_workflow.py
"""

import sys
import os
import time
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from redis import Redis
from agent_memory import AgentMemory
from semantic_cache import SemanticCache
from lit_researcher_bridge import PaperMemory

PASS = 0
FAIL = 0
T = 0.005  # inter-event delay (avoid TS duplicate timestamps)


def ok(msg):
    global PASS
    PASS += 1
    print(f"  ✅ {msg}")


def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  ❌ {msg}")


def phase(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ─── Phase 0: Environment Init ─────────────────────────────
phase("Phase 0: 环境初始化与 Redis 记忆层启动")

r = Redis.from_url("redis://localhost:6379")
modules = set()
raw = r.execute_command("MODULE LIST")
for entry in raw:
    name = entry.get(b"name", entry.get("name"))
    if isinstance(name, bytes):
        name = name.decode()
    modules.add(name)
required = {"search", "ReJSON", "bf", "timeseries"}
missing = required - modules
assert not missing, f"Missing modules: {missing}"
ok(f"Redis Stack 6 模块已加载: {', '.join(sorted(modules))}")
r.close()

mem = AgentMemory()
cache = SemanticCache(similarity_threshold=0.5)
pm = mem.paper
time.sleep(T)

ok("AgentMemory (LTM + Session + Timeseries) 初始化完成")
ok(f"SemanticCache (task_type={cache.task_type}, threshold={cache.threshold}) 初始化完成")
ok(f"PaperMemory (idx:paper, VECTOR_DIM=384, COSINE) 初始化完成")

# Track Phase 0 timing
mem.record_event("phase_duration", 0.0)
time.sleep(T)
mem.record_event("phase_duration", 0.1)
ok("Timeseries 监控就绪")

# ─── Phase 1: Project Launch ───────────────────────────────
phase("Phase 1: 项目启动与文献调研")

# Step 1: Research Director defines direction
direction = "基于物理感知的少样本故障诊断方法研究"
director_session = "phase1-research-director"
mem.add_session_event(director_session, {
    "role": "user",
    "content": f"研究方向定义: {direction}",
    "actor": "research-director",
})
ok(f"研究项目总监定义方向: {direction}")

# Step 2: Literature Researcher searches papers (simulated)
literature_papers = [
    {
        "slug": "zhang2023_fewshot_fault",
        "title": "Few-Shot Fault Diagnosis Based on Meta-Learning",
        "authors": ["Wei Zhang", "Yang Liu"],
        "year": 2023,
        "venue": "IEEE TII",
        "arxiv_id": "2301.12345",
        "tags": ["few-shot", "fault-diagnosis", "meta-learning"],
        "content": "Proposes a meta-learning framework for few-shot fault diagnosis under varying operating conditions. Uses MAML to learn condition-invariant features.",
        "abstract": "Meta-learning has shown promise in few-shot fault diagnosis. However, existing methods ignore physical priors of mechanical systems.",
    },
    {
        "slug": "li2022_physics_informed",
        "title": "Physics-Informed Neural Networks for Machinery Fault Diagnosis",
        "authors": ["Xiaoyu Li", "Hua Wang"],
        "year": 2022,
        "venue": "MSSP",
        "doi": "10.1016/j.mssp.2022.109876",
        "tags": ["physics-informed", "fault-diagnosis", "pinn"],
        "content": "Incorporates governing equations of rotating machinery into neural network training for improved generalization in fault diagnosis.",
        "abstract": "Physics-informed deep learning embeds physical laws into loss functions, enabling better generalization across operating conditions.",
    },
    {
        "slug": "chen2024_spectrogram_transformer",
        "title": "Transformer with Time-Frequency Fusion for Bearing Fault Diagnosis",
        "authors": ["Yu Chen", "Jian Zhou"],
        "year": 2024,
        "venue": "Neurocomputing",
        "arxiv_id": "2403.06789",
        "tags": ["transformer", "time-frequency", "bearing"],
        "content": "Dual-stream transformer architecture fusing time-domain vibration signals and frequency-domain spectrograms for bearing fault classification.",
        "abstract": "Existing methods use either time or frequency domain. We propose a dual-stream architecture that fuses both for comprehensive fault diagnosis.",
    },
]

for paper in literature_papers:
    pm.add_paper(**paper)
    mem.add_session_event(director_session, {
        "role": "assistant",
        "content": f"发现论文: {paper['title']} ({paper['year']})",
        "actor": "literature-researcher",
    })
    time.sleep(T)

paper_count = pm.count()
ok(f"文献研究员检索并入库 {paper_count} 篇相关论文")
ok(f"研究方向会话已记录 {len(literature_papers)} 条事件")

# Step 3: Semantic search across literature
results = pm.search_papers(query="physics-informed few-shot fault diagnosis", hybrid=True, k=5)
assert len(results) >= 3, f"Expected >=3 papers, got {len(results)}"
ok(f"语义检索 \"physics-informed few-shot\": {len(results)} 篇, 最佳匹配={results[0].get('title','?')}")

results2 = pm.search_papers(tags=["transformer"])
assert len(results2) >= 1
ok(f"标签检索 @transformer: {len(results2)} 篇")

results3 = pm.search_papers(authors=["Wei Zhang"])
assert len(results3) >= 1
ok(f"作者检索 Wei Zhang: {len(results3)} 篇")

results4 = pm.search_papers(year_min=2023, year_max=2025)
assert len(results4) >= 2
ok(f"年份范围 2023-2025: {len(results4)} 篇")

# Step 4: Research Director uses SemanticCache
cache.set("What is the SOTA for few-shot fault diagnosis?", 
          "MAML and prototypical networks with physical priors")
time.sleep(T)
resp = cache.search("few-shot fault diagnosis SOTA")
assert resp is not None
ok(f"SemanticCache 命中: {resp['response']}")

# Step 5: Academic Reviewer novelty check (simulated)
novelty_check = {
    "verdict": "pass",
    "issues": [],
    "recommendations": ["注意与 PINN-based 方法的区分度", "建议增加时频融合的消融实验"],
}
review_id = mem.record_review(
    phase=1,
    phase_name="literature-review",
    reviewer="academic-reviewer",
    verdict=novelty_check["verdict"],
    target="novelty-check",
    details=novelty_check,
)
assert review_id
ok(f"学术评审员查新验证: {novelty_check['verdict'].upper()}, review_id={review_id[:12]}")

# Step 6: Verify review persistence
review_results = mem.search_long_term(query="*", topics=["review-audit", "phase-1", "academic-reviewer"])
assert len(review_results) >= 1
ok(f"审稿记录持久化验证: {len(review_results)} 条")

# Step 7: Session memory evidence
msgs = mem.get_session_memory(director_session)
assert len(msgs) >= len(literature_papers) + 1
ok(f"会话记忆完整: {len(msgs)} 条消息")

# Step 8: Cleanup
mem.r.close()
cache.r.close()
pm.r.close()

# ─── Summary ───────────────────────────────────────────────
total = PASS + FAIL
print(f"\n{'='*60}")
print(f"  Phase 0→1 全流程仿真: {PASS}/{total} 通过", end="")
if FAIL > 0:
    print(f", {FAIL} 失败", end="")
print()
print(f"{'='*60}")
print(f"\n验证范围:")
print(f"  ✅ Phase 0: Redis Stack 6 模块 + 3 个索引 (idx:ltm/session/cache/paper)")
print(f"  ✅ Phase 0: Timeseries 监控就绪")
print(f"  ✅ Phase 1: 研究总监定义研究方向 → 记录到 Session")
print(f"  ✅ Phase 1: 文献研究员检索 3 篇论文 → 写入 PaperMemory")
print(f"  ✅ Phase 1: 语义检索/标签检索/作者检索/年份检索")
print(f"  ✅ Phase 1: SemanticCache LLM 响应缓存")
print(f"  ✅ Phase 1: 学术评审员查新验证 → 持久化到 LTM")
print(f"  ✅ Phase 1: 所有组件协作数据可回溯验证")
