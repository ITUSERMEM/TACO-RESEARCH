# P2-P5 全阶段修复与建设方案

## 总览

当前状态：P0+P1 骨架代码存在但无法运行（C1-C3 致命问题）。
本方案分 4 步，从"能让 P0+P1 真正跑起来"到"完全自治学术团队"。

---

## Step 1：让系统能跑（修复致命缺陷）

### S1.1 模块部署集成（C3 → 修复）

**当前问题**：12 个 P1 模块不在 `__init__.py` 中，无 `requirements.txt`，Heartbeat/Scheduler/AcademicLoop 从未启动。

**操作清单**：

| # | 操作 | 文件 |
|---|------|------|
| 1 | 创建 redis-memory 的 `requirements.txt` | `redis-memory/requirements.txt` |
| 2 | 创建 telegram_bridge 的 `requirements.txt` | `telegram_bridge/requirements.txt` |
| 3 | 更新 `__init__.py` 导出全部模块 | `redis-memory/__init__.py` |
| 4 | 创建统一启动器 `team_launcher.py`（管理 AcademicLoop + Heartbeat + Scheduler） | `redis-memory/team_launcher.py` |
| 5 | 创建 `opencode-academic-team.service` systemd 单元 | `/etc/systemd/system/opencode-academic-team.service` |
| 6 | 更新 `start_memory.sh` 同步启动 team_launcher | `redis-memory/start_memory.sh` |

**文件内容**：

`requirements.txt`：
```
redis>=5.0
sentence-transformers>=3.0
pyyaml>=6.0
```

`telegram_bridge/requirements.txt`：
```
python-telegram-bot>=21.0
```

`__init__.py`：添加所有 12+ 模块的导出。

`team_launcher.py`：主入口，依次 start：
- AcademicLoop（后台 daemon 模式，监听 Redis pub/sub）
- AcademicScheduler
- Heartbeat
- AuditLogger（挂载到 loop 回调）
- 健康检查 HTTP endpoint（端口 9333）

---

### S1.2 Bridge ↔ AcademicLoop 桥接（C1 → 修复）

**当前问题**：Telegram 消息发给 tmux opencode，AcademicLoop 在独立进程 sleep，互不感知。

**方案**：Redis Pub/Sub 作为消息总线

```
Telegram Bridge                          AcademicLoop
       │                                      │
       │  publish(channel="academic:inbox")  │
       ├─────────────────────────────────────►│  subscribe()
       │                                      │
       │                              ┌───────┴───────┐
       │                              │  route_by_phase│
       │                              │  Phase 0: → PH0_handler
       │                              │  Phase 1: → PH1_handler
       │                              │  ...           │
       │                              └───────┬───────┘
       │                                      │
       │  publish(channel="academic:outbox")  │
       │◄─────────────────────────────────────┤
       │                                      │
```

**操作清单**：

| # | 操作 | 文件 |
|---|------|------|
| 1 | AcademicLoop 新增 `daemon_mode=True`，启动时 subscribe `academic:inbox` | `academic_loop.py` |
| 2 | Telegram bridge 支持将消息 publish 到 `academic:inbox` | `telegram_bridge.py` |
| 3 | AcademicLoop 处理完的消息 publish 到 `academic:outbox` | `academic_loop.py` |
| 4 | Bridge 订阅 `academic:outbox` 返回结果给用户 | `telegram_bridge.py` |
| 5 | 添加 `/phase` 命令查看当前 Phase 状态 | `telegram_bridge.py` |

**消息格式**：
```python
{
    "type": "user_message" | "phase_command" | "status_query",
    "chat_id": 12345,
    "text": "研究 XXX 方向",
    "timestamp": "...",
}
```

---

### S1.3 Token 安全（H1 → 修复）

| # | 操作 |
|---|------|
| 1 | `chmod 600 bot_token.txt` |
| 2 | 为 opencode-academic-team.service 添加 `ProtectHome=yes` `PrivateTmp=yes` `NoNewPrivileges=yes` |

---

### S1.4 EINTR 处理（H4 → 修复）

| # | 操作 | 文件 |
|---|------|------|
| 1 | 为 `FileLock.lock()` 添加 `InterruptedError` 重试循环 | `persist_learnings.py` 第 29-33 行 |
| 2 | 移除 `_bounded_append()` 中冗余的 `with open(self.lock_path, "a")` | 第 168 行 |

---

## Step 2：让功能真实有效

### S2.1 真实审查门（C2 → 修复）

**当前问题**：`_evaluate_gate()` 用 `hash % 100` 决定 verdict，`messages` 参数完全没用。

**方案**：将 `messages` 传给 LLM（通过 llm-chat MCP）进行真实审查。

```python
def _evaluate_gate(self, gate_id, phase, session_id, messages):
    transcript = self._build_gate_transcript(messages, gate_id)
    prompt = self._build_gate_prompt(gate_id, phase, transcript)
    verdict, issues, recs = self._llm_judge(prompt)
    # verdict: pass / revise / fail
    # issues: 具体问题列表
    # recs: 具体建议列表
    return verdict, {"issues": issues, "recommendations": recs}
```

**操作清单**：

| # | 操作 | 文件 |
|---|------|------|
| 1 | 创建 `gate_judge.py`——审查门 LLM 评判器 | `redis-memory/gate_judge.py` |
| 2 | 替换 `academic_loop.py:_evaluate_gate()` 的 hash 逻辑 | `academic_loop.py` |
| 3 | 审查结果写入 AuditLogger + PhaseTracker | `academic_loop.py` |

---

### S2.2 真实 Agent 执行（H3 → 修复）

**当前问题**：`_execute_phase()` 的迭代循环只 `sleep(0.1)`，没有 LLM 调用或工具执行。

**方案**：每次迭代调用 `llm-chat` MCP 执行当前 agent 角色。

```python
def _execute_iteration(self, phase, iteration, messages):
    role = PHASE_AGENTS[phase][iteration % len(PHASE_AGENTS[phase])]
    prompt = self._build_agent_prompt(role, phase, messages)
    
    # llm-chat MCP 调用
    response = self._llm_complete(prompt)
    
    # 解析 tool_calls 并执行
    for tool_call in response.get("tool_calls", []):
        result = self._execute_tool(tool_call)
        self.loop_detector.record(tool_call["name"], tool_call.get("args"))
    
    return response
```

**操作清单**：

| # | 操作 | 文件 |
|---|------|------|
| 1 | 创建 `llm_client.py`——LLM 调用封装（支持 llm-chat MCP） | `redis-memory/llm_client.py` |
| 2 | 替换 `_execute_phase()` 的 `sleep(0.1)` 为真实 LLM 调用 | `academic_loop.py` |
| 3 | LoopDetector 集成到迭代循环中 | `academic_loop.py` |
| 4 | MemoryPreflight 注入在每次 LLM 调用前 | `academic_loop.py` |
| 5 | AuditLogger 记录每次迭代 | `academic_loop.py` |

---

### S2.3 真实摘要生成（H2 → 修复）

**当前问题**：`PhaseSummarizer._phase1_analysis()` 只是关键词匹配，不调用 LLM。

**方案**：`llm-chat` MCP 调用 Kocoro 风格的两阶段提示词。

```python
def _phase1_analysis(self, transcript, phase):
    prompt = f"""Analyze the following conversation transcript from Phase {phase}.
Identify:
1. Key decisions made
2. User corrections & why
3. Files read or modified  
4. Errors encountered and resolutions
5. Skills activated

<transcript>
{transcript[:200000]}
</transcript>

Return in <analysis> tags."""
    return self._llm_complete(prompt)
```

**操作清单**：

| # | 操作 | 文件 |
|---|------|------|
| 1 | 为 `PhaseSummarizer` 添加 LLM 调用 | `summarizer.py` |
| 2 | 为 `ContextCompactor._generate_summary()` 添加 LLM 调用 | `academic_loop.py` |
| 3 | 为 `PersistLearnings._extract_learnings()` 添加 LLM 调用 | `persist_learnings.py` |

---

### S2.4 统一存储后端（H5 → 修复）

**方案**：AuditLogger 改为写 Redis（同时保留 JSONL 文件作为备份）。

```python
class AuditLogger:
    def log(self, event, ...):
        # Redis: 追加到 sorted set
        self.r.zadd("audit:events", {json.dumps(entry): time.time()})
        # File: 追加到 JSONL 备份
        with open(self.log_path, "a") as f:
            f.write(line + "\n")
```

**操作清单**：

| # | 操作 | 文件 |
|---|------|------|
| 1 | AuditLogger 添加 Redis 写入 | `audit_logger.py` |
| 2 | PhaseTracker 复用 AuditLogger 接口（而不是各自独立写 Redis） | `academic_loop.py` |

---

## Step 3：元学习层（P2）

### P2.1 审稿校准

**文件**：`review_calibration.py`

**功能**：
- 校准集：10 篇已知质量的论文（评分 + 评审意见）
- 每次 LLM 评审后对比校准集分布，检测 drift
- 校准指标：harshness 偏移、漏检率、误报率

```python
CALIBRATION_SET = [
    {"paper": "...", "ground_truth": {"quality": 7.5, "issues": ["..."]}},
    ...
]

class ReviewCalibrator:
    def evaluate_drift(self, recent_reviews: list[dict]) -> dict:
        """Compare recent review distribution vs calibration set."""
```

**集成点**：挂载到 `GateJudge` 每次评审后自动校准检查。

---

### P2.2 跨项目知识传递

**文件**：`global_lessons.py`

**功能**：
- 所有 Phase 完成的 lessons 写入全局 Redis key `global:lessons`
- 新项目启动时自动注入相关 lessons
- lessons 按类型分类：实验教训、写作教训、审稿反馈

**集成点**：`PersistLearnings.consolidate_if_needed()` 扩展写入全局存储。

---

### P2.3 聚合分析引擎

**文件**：`analytics_engine.py`

**功能**：
- 从 AuditLogger + PhaseTracker + AgentMemory 读取数据
- 计算：每 Phase 通过率、平均迭代次数、Token 消耗、失败模式分布
- 生成仪表盘 JSON 供外部读取

**集成点**：`team_launcher.py` 启动时挂载，HTTP endpoint `/metrics`。

---

### P2.4 技能版本化管理

**文件**：`skill_versioning.py`

**功能**：
- 每次 `/meta-optimize` 后记录 skill 内容 hash 到 Redis
- 支持 `--rollback <N>` 回滚到前一个版本
- 版本 manifest：`skill:manifest:agent-team`

---

### P2.5 趋势适配

**文件**：`trend_monitor.py`

**功能**：
- 每周扫描 arXiv/Semantic Scholar 热点关键词
- 追踪会议截止日期（NeurIPS/ICML/CVPR）
- 检测工具/库的社区热度变化

**集成点**：`AcademicScheduler.cron` 每周任务。

---

## Step 4：自主运行层（P3）+ 跨团队层（P4）+ 完全自治层（P5）

### P3.1 多日实验检查点

**文件**：`checkpoint_manager.py`

**功能**：
- PhaseTracker 状态 + AgentMemory 的 session 序列化到 Redis
- 支持 `--resume` 从中断的 Phase 继续
- 实验 GPU 状态持久化到 `ts:gpu:*`

### P3.2 自愈基础设施

**文件**：`auto_retry.py`

**功能**：
- 从 AuditLogger 的错误事件中检测重复失败
- GPU OOM → 自动减小 batch size 重试
- 网络超时 → 指数退避重试（3 次上限）
- 死了的 systemd 服务 → 自动重启（已通过 Restart=always 部分实现）

### P4.1 多项目管理

**文件**：`project_manager.py`

**功能**：
- `AcademicLoop` 实例化为多个 project 对象（已有 `namespace` 参数支持）
- `ProjectManager` 管理项目生命周期
- 资源池调度：GPU/Token 配额

### P5.1 全自主生命周期

**文件**：`autonomous_orchestrator.py`

**功能**：
- 从 P2.5 的趋势检测自动触发新 idea 发现
- 自动执行 Phase 0→5 全流程
- 自动提交到 arXiv/会议

---

## 文件创建总表

### Step 1 - 让系统跑（6 文件）

| 文件 | 改动类型 |
|------|----------|
| `redis-memory/requirements.txt` | 新建 |
| `telegram_bridge/requirements.txt` | 新建 |
| `redis-memory/__init__.py` | 修改（扩充导出） |
| `redis-memory/team_launcher.py` | 新建 |
| `redis-memory/academic_loop.py` | 修改（添加 daemon_mode） |
| `telegram_bridge/telegram_bridge.py` | 修改（Redis pub/sub） |
| `redis-memory/persist_learnings.py` | 修改（EINTR 修复） |
| `/etc/systemd/system/opencode-academic-team.service` | 新建 |

### Step 2 - 功能有效（6 文件）

| 文件 | 改动类型 |
|------|----------|
| `redis-memory/gate_judge.py` | 新建 |
| `redis-memory/llm_client.py` | 新建 |
| `redis-memory/academic_loop.py` | 修改（真实 Agent 执行） |
| `redis-memory/summarizer.py` | 修改（LLM 调用） |
| `redis-memory/persist_learnings.py` | 修改（LLM 提取） |
| `redis-memory/audit_logger.py` | 修改（Redis 双写） |

### Step 3-4 - 元学习 + 自治（14 文件）

| 阶段 | 文件 |
|------|------|
| P2.1 | `review_calibration.py` |
| P2.2 | `global_lessons.py` |
| P2.3 | `analytics_engine.py` |
| P2.4 | `skill_versioning.py` |
| P2.5 | `trend_monitor.py` |
| P3.1 | `checkpoint_manager.py` |
| P3.2 | `auto_retry.py` |
| P4.1 | `project_manager.py` |
| P4.2 | `pool_scheduler.py` |
| P4.3 | `knowledge_broker.py` |
| P4.4 | `experiment_template_lib.py` |
| P5.1 | `autonomous_orchestrator.py` |
| P5.2 | `meta_optimizer.py` |
| P5.3 | `review_feedback_analyzer.py` |

---

## 依赖顺序

```
Step 1 ──→ Step 2 ──→ P2.1+P2.3 ──→ P2.2+P2.4+P2.5 ──→ P3 ──→ P4 ──→ P5
   │            │
   └── 无前置    └── 依赖 Step 1
```

---

## 总工作量预估

| Step | 新文件 | 修改文件 | 预估工时 |
|------|--------|---------|---------|
| Step 1 | 4 | 5 | 2-3h |
| Step 2 | 2 | 6 | 4-6h |
| Step 3 | 5 | 0 | 4-5h |
| Step 4 | 9 | 0 | 6-8h |
| **合计** | **20** | **11** | **16-22h** |

---

## 后处理

全部完成后：3 轮全量审查（同本次模式），检查每项功能的正确性、集成完整性、安全性和可观测性。

---

要开始执行 Step 1 吗？
