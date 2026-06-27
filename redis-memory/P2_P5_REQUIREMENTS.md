# P2-P5 需求定义书

> 基于 P1 现有模块（academic_loop.py, loop_detector.py, persist_learnings.py, audit_logger.py, heartbeat.py, scheduler.py）的架构基线分析。
> 参考 Kocoro 的 context/persist.go、audit/audit.go、agent/loopdetect.go 等实现模式。

---

## P1 现状总结（架构基线）

在进入 P2-P5 需求之前，先盘点 P1 已具备的能力：

| 模块 | 核心能力 | Redis/存储依赖 | 线程安全 |
|------|---------|---------------|---------|
| `academic_loop.py` | Phase 0-5 编排、PhaseTracker（JSON 状态）、ContextCompactor（三级压缩）、Watchdog（软/硬超时）、7个评审门 | RedisJSON + RedisTimeSeries | 否（单线程为主） |
| `loop_detector.py` | 9路径循环检测、PhaseLoopDetector（角色感知阈值）、Nudge/ForceStop 升级 | 无（内存状态） | 否 |
| `persist_learnings.py` | 知识提取、去重、有界追加、文件锁、合并GC | 文件系统（MEMORY.md + auto-*.md） | `flock` 文件锁 |
| `audit_logger.py` | JSON-lines 日志、密文脱敏（7+3类模式）、工具调用追踪 | 文件系统（audit.log） | `threading.Lock` |
| `heartbeat.py` | 代理定期健康检查、检查单驱动、HEARTBEAT_OK 静默确认 | 文件系统（HEARTBEAT.md） | `threading.Lock` |
| `scheduler.py` | Cron 调度、有状态/无状态会话、信号量并发控制 | JSON 配置文件 | `threading.Lock` |

**P1 缺口**（P2-P5 需要填补的）：
1. 无质量校准/回归评估机制
2. 无法跨项目迁移知识
3. 无聚合性能仪表盘
4. 无技能版本管理
5. 无长时间实验编排（非阻塞）
6. 无自愈/自动重试
7. 无多项目并发调度
8. 无元优化回路

---

## P2 — 元学习层（Meta-Learning Layer）

### 总体目标
让学术研究系统能够**从自身经历中学习**——评估输出质量、跨项目复用知识、量化性能趋势、适配环境和技能变化。

### 2.1 评审校准（Review Calibration）

**问题**：当前评审门（G1-G7）的裁决基于哈希权重随机，没有真实质量信号校准。

#### 核心能力
1. **校准集管理**：维护 10-20 篇已知质量分数的人工标注论文集
2. **定期再评估**：每周/每两周用校准集运行评审管线，计算 calibration recall/precision
3. **漂移检测**：当校准集的评审通过率偏离基准超过阈值时告警
4. **适应性阈值**：根据漂移检测自动调整评审门的通过难度

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `review_calibration.py` | 校准集 CRUD、评分运行、漂移计算 | `academic_loop._run_review_gates()` |
| `calibration_set.json` | 20 篇标注论文的元数据（DOI、质量分、各门预期结果） | 静态数据文件 |

#### 集成点
- `PhaseTracker.gate_record()` 写入结果时同步触发校准检查
- `AcademicLoop._evaluate_gate()` 不再使用哈希权重，改为查询校准模型
- `AgentMemory.create_long_term_memory()` 持久化校准运行历史

#### 依赖
- P1 已有的 `AgentMemory` 用于存储校准结果
- P1 `SemanticCache` 可用于缓存校准特征

### 2.2 跨项目知识迁移

**问题**：每个项目从零开始，缺少项目间经验传递。

#### 核心能力
1. **全局知识库（Global Lessons Store）**：将各项目的"经验教训"聚合到全局命名空间
2. **论文写作复盘**：每完成一篇论文，自动生成复盘记录（what worked / what didn't）
3. **智能检索**：启动新项目时，从全局库检索相关经验推送给 agent
4. **知识衰减**：陈旧知识自动降权（基于时间戳和项目相关性）

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `global_lessons.py` | 全局知识 CRUD、衰减计算、项目间检索 | `AgentMemory` + `PersistLearnings` |
| `paper_postmortem.py` | 论文完成后的复盘自动化 | `AcademicLoop.phase_complete()` |

#### 集成点
- `PersistLearnings.extract_and_persist()` 扩展：同时写入项目本地 MEMORY.md 和全局知识库
- `AcademicLoop._persist_learnings()` 阶段完成时同步复制到全局
- 使用 `AgentMemory` 的 `create_long_term_memory()` 的 `topics` 字段区隔项目

#### 依赖
- P1 `PersistLearnings` 的提取管道
- P1 `AgentMemory` 的长期记忆存储

### 2.3 聚合性能分析

**问题**：审计日志（audit.log）是原始 JSON-lines，缺少聚合视图。

#### 核心能力
1. **事件日志分析**：阶段耗时趋势、各门通过率、循环检测触发频率
2. **技能成功率跟踪**：每种 agent 技能的执行成功率、平均耗时
3. **成本追踪**：LLM 调用成本聚合（按阶段/代理/模型）、预算告警
4. **仪表盘 API**：提供 `/status` 的增强版，包含滚动窗口性能指标

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `analytics_engine.py` | 日志解析、指标计算、聚合查询 | `AuditLogger` (读取 audit.log) |
| `cost_tracker.py` | Token/成本追踪、预算阈值监控 | `AuditLogger.log()` 输出 |
| `dashboard.py` | 增强状态 API，暴露滚动指标 | `AcademicLoop.status()` |

#### 集成点
- `AuditLogger.log()` 的 `cost` 和 `tokens` 参数是成本追踪的数据源
- `AuditLogger.log_cache_summary()` 提供缓存效率指标
- `PhaseTracker._record_metric()` 的 RedisTimeSeries 是趋势数据源
- `LoopDetector` 的 nudge_count/iteration 是循环指标源

#### 依赖
- P1 `AuditLogger` 的日志输出格式
- P1 `PhaseTracker` 的 Metric 时间序列
- P1 `LoopDetector` 的迭代和 nudge 计数

### 2.4 技能版本管理

**问题**：agent 技能（SKILL.md 和其他提示词）变更无追溯，无法回滚。

#### 核心能力
1. **内容哈希清单**：对所有技能文件计算 SHA256 摘要，维护版本映射
2. **变更追踪**：技能更新时记录 diff、时间戳、变更原因
3. **回滚能力**：`/rollback-skill <name> <version>` 命令恢复旧版本
4. **版本标签**：每个项目记录使用的技能版本快照，便于复现

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `skill_versioning.py` | 技能文件哈希、版本 CRUD、回滚执行 | 文件系统（skills 目录）+ `AgentMemory` |
| `skill_manifest.json` | 技能版本映射持久化文件 | 静态数据文件 |

#### 集成点
- `AcademicLoop` 初始化时读取当前技能版本快照
- `AuditLogger.log()` 记录技能变更事件
- 回滚操作通过文件系统替换 + md5 校验执行

#### 依赖
- 无（独立于其他模块，但受益于 `AgentMemory` 的持久化）

### 2.5 趋势适配

**问题**：系统对会议截止日期、新工具出现等外部事件无感知。

#### 核心能力
1. **会议截止日期追踪**：维护顶会日程表（NeurIPS/ICML/ICLR/CVPR...），临近截止自动调整节奏
2. **新工具监控**：检查 arXiv/GitHub 上与活跃项目相关的新库/框架
3. **自适应调度**：根据截止日期和负载历史，动态调整 `MAX_ITERATIONS` 和调度频率
4. **脉动检测**：检测到环境变化（如新 GPU 可用）时调整策略

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `deadline_tracker.py` | 会议日程管理、截止提醒、节奏调整 | `AcademicScheduler` + `AcademicLoop` |
| `tool_monitor.py` | 外部工具/库变更检测 | `Scheduler` 触发 |

#### 集成点
- `AcademicScheduler` 添加基于截止日期的动态调度条目
- `AcademicLoop.MAX_ITERATIONS` 改为可被 `DeadlineTracker` 调整
- `Heartbeat` 的 `active_hours_start/end` 可用于截止前冲刺模式

#### 依赖
- P1 `AcademicScheduler` 的 cron 调度
- P1 `Heartbeat` 的周期性执行

---

## P3 — 长时间运行自治（Long-Running Autonomy）

### 总体目标
让系统能**无人值守运行数天**——编排长时间实验、自我修复故障、自动走完论文提交管线、优化资源利用。

### 3.1 多日实验编排

**问题**：当前 `AcademicLoop._execute_phase()` 是同步阻塞的，无法跨越数天的实验周期。

#### 核心能力
1. **检查点（Checkpoint）**：每个实验阶段创建检查点（阶段状态、中间结果、上下文摘要）
2. **中断恢复**：系统重启后从最新检查点恢复，而非从头开始
3. **异步阶段执行**：P3 实验阶段改为异步，释放主循环处理其他任务
4. **进度跟踪**：长时间运行的实验有进度条/ETA 估算

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `checkpoint_manager.py` | 检查点创建/恢复/GC、健康验证 | `PhaseTracker` + RedisJSON |
| `long_running_experiment.py` | 异步实验编排器、进度估算 | `AcademicLoop.PHASE3` |
| `recovery_handler.py` | 系统重启后的恢复入口 | `AcademicLoop.__init__()` |

#### 集成点
- `PhaseTracker.state` 扩展检查点元数据（checkpoint_id、resume_token）
- `ContextCompactor` 的摘要写入检查点
- `Watchdog` 的软超时触发检查点创建（而非直接 force-stop）

#### 依赖
- P1 `PhaseTracker` 的 RedisJSON 状态
- P1 `ContextCompactor` 的上下文摘要
- P1 `Watchdog` 的超时机制

### 3.2 自愈（Self-Healing）

**问题**：实验失败/进程挂起/GPU OOM 需要人工介入。

#### 核心能力
1. **自动重试**：作业失败后自动重试（带指数退避），最多 N 次
2. **进程监控**：定期检查 GPU 作业、agent 进程是否存活
3. **环境修复**：检测到 CUDA OOM 后自动清理缓存/降低 batch size 重试
4. **分级恢复策略**：快速重试 → 参数调整 → 降低复杂度 → 上报人工

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `auto_retry.py` | 指数退避重试引擎、失败分类 | `LongRunningExperiment` + `Experimenter` |
| `process_monitor.py` | GPU 作业/agent 进程生命周期监控 | `Heartbeat` + `AuditLogger` |
| `healing_actions.py` | 具体修复动作（清理缓存、调整参数、回退配置） | `AutoRetry` |

#### 集成点
- `Heartbeat` 扩展：在健康检查中集成进程存活检测
- `AuditLogger.log(event="error")` 是自愈的触发信号
- `LoopDetector` 的 SameToolError 路径可与自愈联动（连续错误触发修复）

#### 依赖
- P1 `Heartbeat` 的周期执行
- P1 `AuditLogger` 的错误事件
- P1 `LoopDetector` 的错误检测

### 3.3 自动论文提交管线

**问题**：论文从编译到提交的流程（格式检查 → PDF 生成 → 上传）需要自动化。

#### 核心能力
1. **自动编译**：LaTeX 编译 + 错误修复循环（引用 P1 `paper-compile` skill）
2. **格式检查**：页数限制/引用格式/图像分辨率/匿名性检查
3. **提交流程**：通过 OpenReview/CMT API 或浏览器自动化完成上传
4. **提交验证**：提交后检查回执确认成功

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `submission_pipeline.py` | 编排编译→检查→提交的完整管线 | `AcademicLoop.PHASE5` |
| `format_validator.py` | 页数/字数/图分辨率/匿名性检查 | `SubmissionPipeline` |
| `submission_adapters/` | 各平台（OpenReview/CMT/HotCRP）适配器 | `SubmissionPipeline` |

#### 集成点
- `PhaseTracker.gate_record()` 记录格式检查门结果
- `AuditLogger.log(event="paper_revision")` 记录编译迭代次数
- `AcademicLoop` 的 Phase5 完成后触发提交管线

#### 依赖
- P1 `AcademicLoop.PHASE5` 论文撰写阶段
- P1 `PhaseTracker` 的门状态

### 3.4 资源优化

**问题**：GPU 调度原始（Vast.ai/Modal 直接分配），无缓存预热。

#### 核心能力
1. **GPU 调度**：多作业的队列管理、优先级排序、抢占式调度
2. **缓存预热**：常用数据集/模型在实验开始前预加载
3. **资源预算**：每个项目/阶段的 GPU 小时数预算和预警
4. **竞态处理**：检测资源争用（OOM、CUDA timeout）并调度到不同 GPU

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `gpu_scheduler.py` | GPU 队列管理、优先级调度、配额跟踪 | `Experimenter` + `RunExperiment` |
| `cache_warmer.py` | 常用资源的预加载和保持 | `GPUScheduler` |
| `resource_budget.py` | GPU 小时/内存/存储的成本预算 | `CostTracker` |

#### 集成点
- `Scheduler` 的 `MAX_CONCURRENT` 扩展为 GPU 感知
- `RunExperiment` 调用前查询 `GPUScheduler` 获取分配
- `CostTracker` 集成资源成本

#### 依赖
- P2 `CostTracker`（P2.3）
- P1 `Scheduler` 的信号量模式

---

## P4 — 跨团队协作（Cross-Team Collaboration）

### 总体目标
让系统**同时支持多个独立研究项目**，在项目间智能调度资源、共享知识、复用代码和数据。

### 4.1 多项目并发

**问题**：当前 `AcademicLoop` 是单体项目级，一个实例只能处理一篇论文。

#### 核心能力
1. **项目生命周期管理**：多个 `AcademicLoop` 实例各自独立运行
2. **项目元数据隔离**：每个项目有独立的 `namespace` 和 Redis key 前缀
3. **项目级配置**：每项目可独立设置 `MAX_ITERATIONS`、agent 角色集、评审门
4. **项目仪表盘**：聚合视图展示所有项目状态和进度

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `project_manager.py` | 多项目生命周期 CRUD、命名空间分配 | `AcademicLoop`（工厂模式创建实例） |
| `project_registry.json` | 项目的持久化注册表 | 静态数据文件 |
| `project_dashboard.py` | 多项目聚合状态视图 | `AcademicLoop.status()` |

#### 集成点
- `AcademicLoop.__init__()` 改为接受 `namespace` 参数（P1 已有）
- `PhaseTracker` 的 Redis key 自动使用 namespace 前缀（P1 已有 `STATE_KEY = "academic:phase:state"` 但有 namespace 参数）
- `AgentMemory` 的 namespace 隔离

#### 依赖
- P1 `AcademicLoop` 和 `PhaseTracker` 的 namespace 设计（已在 `__init__` 中包含但未深度使用）

### 4.2 项目间资源调度

**问题**：多项目竞争 GPU/API 配额/上下文窗口等有限资源。

#### 核心能力
1. **资源池化**：所有项目的 GPU/API 预算统一管理
2. **优先级调度**：高优先级项目（截止日期临近）优先分配资源
3. **公平调度**：确保没有项目饿死的最小资源保证
4. **资源抢占**：低优先级作业在资源争用时被挂起/降级

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `pool_scheduler.py` | 资源池管理器、优先级队列、公平性保证 | `ProjectManager` + `GPUScheduler` |
| `resource_quota.py` | 项目级配额定义和强制 | `PoolScheduler` |

#### 集成点
- `GPUScheduler`（P3.4）扩展为跨项目资源池
- `ProjectManager` 提供每个项目的优先级和配额
- `Scheduler` 的 `Semaphore` 模式扩展为加权分配

#### 依赖
- P3 `GPUScheduler`
- P4 `ProjectManager`

### 4.3 项目间知识共享

**问题**：P2 全局知识库需要感知项目归属。

#### 核心能力
1. **跨项目知识检索**：启动新项目时，从其他项目的 MEMORY.md/全局知识库检索相关知识
2. **知识引用追踪**：记录从哪些项目获取了知识，追踪复用效果
3. **协同过滤推荐**：相似项目的历史配置、成功策略推荐
4. **知识权限**：标记敏感/不共享的知识条目

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `knowledge_broker.py` | 跨项目检索、相关性排序、引用追踪 | `GlobalLessons` + `ProjectManager` |
| `knowledge_graph.py` | 项目→知识→技能的关联图谱 | `KnowledgeBroker` |

#### 集成点
- `GlobalLessons`（P2.2）扩展项目归属字段
- `ProjectManager` 提供项目相似度计算
- `AgentMemory` 的 `search_long_term_memory()` 跨命名空间查询

#### 依赖
- P2 `GlobalLessons`
- P4 `ProjectManager`

### 4.4 代码/数据跨实验复用

**问题**：不同项目的相似实验重复编写代码，数据集重复下载。

#### 核心能力
1. **实验模板库**：维护已验证的实验配置模板（项目无关）
2. **数据集缓存注册表**：记录已下载数据集的位置和格式，避免重复下载
3. **代码模块共享**：跨项目引用 utils/、models/、datasets/ 目录
4. **结果缓存**：已运行的实验（相同配置+数据）跳过，直接返回结果

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `experiment_template_lib.py` | 实验模板的 CRUD、变量替换、版本管理 | `Experimenter` |
| `dataset_registry.py` | 已缓存数据集的元数据注册表 | `CacheWarmer` |
| `cross_project_share.py` | 代码/数据目录的符号链接或 git subtree 管理 | `ProjectManager` |

#### 集成点
- `SemanticCache`（P1）扩展为实验级别的缓存
- `GPUScheduler`（P3.4）在分配 GPU 时优先调度到已缓存数据的节点
- `LongRunningExperiment`（P3.1）执行前查询模板库和缓存

#### 依赖
- P3 `CacheWarmer`
- P4 `ProjectManager`

---

## P5 — 完全自治（Full Autonomy）

### 总体目标
系统**完全自主运行研究生命周期**——从选题到发表，同时持续优化自身架构。

### 5.1 全自主研究生涯

**问题**：目前需要人工确定研究方向和触发管线。

#### 核心能力
1. **自主选题**：根据文献趋势、系统历史成功率、可用资源自动选择研究方向
2. **端到端管线**：从文献调研 → 方法设计 → 实验 → 论文 → 提交，全自动
3. **多分支探索**：同时探索多个研究方向，自动选择最有希望的分支深入
4. **失败优雅处理**：当某个方向被判定无望时，自动记录教训并切换方向

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `autonomous_orchestrator.py` | 全自主生命周期编排（选题→提交） | 所有 P1-P4 模块 |
| `research_branch_manager.py` | 多分支研究追踪、探索 vs 利用平衡 | `AutonomousOrchestrator` |
| `direction_switch.py` | 方向切换策略、教训记录、回滚 | `AutonomousOrchestrator` |

#### 集成点
- 调用 `AcademicLoop.run()` 进行单个项目的研究管线
- `ProjectManager` 管理多分支项目和切换
- `GlobalLessons` 记录每个方向的教训

#### 依赖
- P4 `ProjectManager` + `KnowledgeBroker`

### 5.2 系统元优化

**问题**：系统配置（`MAX_ITERATIONS`、`NUDGE_ESCALATION_LIMIT`、评审门权重等）是硬编码的。

#### 核心能力
1. **实验影响评估**：将系统各配置参数作为"元参数"，对比不同配置下的论文产出质量
2. **A/B 测试框架**：同时运行两组不同配置的学术循环，比较最终论文质量
3. **自动调参**：使用贝叶斯优化或强化学习方法调整系统参数
4. **配置版本实验**：每次系统变更自动记录为一"实验"并追踪产出效果

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `meta_optimizer.py` | 元参数定义、自动调参、对比分析 | `AcademicLoop` + `ProjectManager` |
| `ab_test_framework.py` | A/B 测试编排、结果对比、统计显著性 | `MetaOptimizer` |
| `config_experiment.py` | 系统配置变更→产出效果的追踪 | `MetaOptimizer` + `AnalyticsEngine` |

#### 集成点
- `AcademicLoop.MAX_ITERATIONS` 等常量改为从 `MetaOptimizer` 获取
- `PhaseTracker` 的 Metric 时间序列提供元优化数据源
- `AnalyticsEngine`（P2.3）的聚合指标作为优化目标函数

#### 依赖
- P4 `ProjectManager`（多项目对比）
- P2 `AnalyticsEngine`（性能指标）
- P1 `PhaseTracker`（时间序列数据）

### 5.3 社区互动

**问题**：审稿人反馈（OpenReview 评论）需要人工读取和处理。

#### 核心能力
1. **审稿意见分析**：自动解析审稿人的结构化/非结构化评论
2. **答复草案生成**：基于评审意见自动生成逐点回复（rebuttal）
3. **修改计划**：从评审意见中提取 actionable items，生成修改计划
4. **反馈学习**：将接受/拒绝的评审模式加入 `GlobalLessons`

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `review_feedback_analyzer.py` | 评审意见 NLP 分析、情感倾向、actionable item 提取 | `SubmissionPipeline` |
| `auto_rebuttal_gen.py` | 逐点回复自动生成 | `ReviewFeedbackAnalyzer` |
| `feedback_to_lessons.py` | 评审模式 → 全局教训的转化 | `GlobalLessons` + `MetaOptimizer` |

#### 集成点
- `SubmissionPipeline`（P3.3）提交后等待评审回执
- `GlobalLessons`（P2.2）存储评审模式
- `MetaOptimizer`（P5.2）使用评审结果作为奖励信号

#### 依赖
- P3 `SubmissionPipeline`
- P2 `GlobalLessons`
- P5 `MetaOptimizer`

### 5.4 论文成果追踪

**问题**：没有系统级的论文发表记录和分析。

#### 核心能力
1. **发表记录**：每篇论文的提交/接受/发表状态追踪
2. **接受率分析**：按会议/期刊/研究方向的接受率统计
3. **评分反馈回路**：审稿人评分 → 系统参数调整（哪个评审门的权重需要调整）
4. **影响度量**：论文引用/关注度的跟踪（通过 Semantic Scholar/Google Scholar API）

#### 文件清单
| 文件 | 职责 | 集成对象 |
|------|------|---------|
| `publication_tracker.py` | 论文生命周期状态机、影响因子追踪 | `ProjectManager` + `AnalyticsEngine` |
| `acceptance_analytics.py` | 接受率统计、评分分布、趋势分析 | `PublicationTracker` |
| `score_to_parameter.py` | 评分→系统参数调整的映射函数 | `MetaOptimizer` + `ReviewCalibration` |

#### 集成点
- `ProjectManager` 的每个项目关联论文状态
- `ReviewCalibration`（P2.1）使用接受率作为校准信号
- `MetaOptimizer`（P5.2）使用评分作为奖励信号
- `AnalyticsEngine`（P2.3）汇总发表统计

#### 依赖
- P2 `ReviewCalibration` + `AnalyticsEngine`
- P4 `ProjectManager`
- P5 `MetaOptimizer`

---

## 阶段依赖关系总图

```
P1 (现有基线)
├──→ P2.1 评审校准
├──→ P2.2 跨项目知识
├──→ P2.3 聚合分析
├──→ P2.4 技能版本
└──→ P2.5 趋势适配

P2 (元学习层)
├──→ P3.1 多日实验
├──→ P3.2 自愈
├──→ P3.3 自动提交
└──→ P3.4 资源优化

P3 (长时自治)
├──→ P4.1 多项目管理
├──→ P4.2 资源池调度
├──→ P4.3 知识共享
└──→ P4.4 代码复用

P4 (跨团队协作)
├──→ P5.1 全自主生命周期
├──→ P5.2 系统元优化
├──→ P5.3 社区互动
└──→ P5.4 成果追踪
```

---

## 文件名冲突矩阵

| 新文件名 | P1 已存在同名？ | 备注 |
|---------|---------------|------|
| `review_calibration.py` | 否 | 新增 |
| `global_lessons.py` | 否 | 新增 |
| `analytics_engine.py` | 否 | 新增 |
| `cost_tracker.py` | 否 | 新增 |
| `dashboard.py` | 否 | 新增 |
| `skill_versioning.py` | 否 | 新增 |
| `deadline_tracker.py` | 否 | 新增 |
| `tool_monitor.py` | 否 | 新增 |
| `checkpoint_manager.py` | 否 | 新增 |
| `long_running_experiment.py` | 否 | 新增 |
| `recovery_handler.py` | 否 | 新增 |
| `auto_retry.py` | 否 | 新增 |
| `process_monitor.py` | 否 | 新增 |
| `healing_actions.py` | 否 | 新增 |
| `submission_pipeline.py` | 否 | 新增 |
| `format_validator.py` | 否 | 新增 |
| `gpu_scheduler.py` | 否 | 新增 |
| `cache_warmer.py` | 否 | 新增 |
| `resource_budget.py` | 否 | 新增 |
| `project_manager.py` | 否 | 新增 |
| `project_dashboard.py` | 否 | 新增 |
| `pool_scheduler.py` | 否 | 新增 |
| `resource_quota.py` | 否 | 新增 |
| `knowledge_broker.py` | 否 | 新增 |
| `knowledge_graph.py` | 否 | 新增 |
| `experiment_template_lib.py` | 否 | 新增 |
| `dataset_registry.py` | 否 | 新增 |
| `cross_project_share.py` | 否 | 新增 |
| `autonomous_orchestrator.py` | 否 | 新增 |
| `research_branch_manager.py` | 否 | 新增 |
| `direction_switch.py` | 否 | 新增 |
| `meta_optimizer.py` | 否 | 新增 |
| `ab_test_framework.py` | 否 | 新增 |
| `config_experiment.py` | 否 | 新增 |
| `review_feedback_analyzer.py` | 否 | 新增 |
| `auto_rebuttal_gen.py` | 否 | 新增 |
| `feedback_to_lessons.py` | 否 | 新增 |
| `publication_tracker.py` | 否 | 新增 |
| `acceptance_analytics.py` | 否 | 新增 |
| `score_to_parameter.py` | 否 | 新增 |
| `submission_adapters/` | 否 | 新增目录 |

**注**：所有 39 个新文件名与 P1 现有 6 个文件无冲突。

---

## P1 扩展现有文件清单

以下 P1 文件需要扩展以支持 P2-P5：

| P1 文件 | 扩展内容 | 影响阶段 |
|---------|---------|---------|
| `academic_loop.py` | `MAX_ITERATIONS` 改为可调；`_evaluate_gate()` 调用校准模型；支持 resume | P2.1, P3.1, P5.2 |
| `loop_detector.py` | 阈值可从外部配置；支持 per-project 覆盖 | P4.1, P5.2 |
| `persist_learnings.py` | 扩展 `extract_and_persist()` 同时写入全局知识库 | P2.2 |
| `audit_logger.py` | 增强 cache 摘要字段（CER、SystemStableHash）；元事件支持 | P2.3, P5.2 |
| `heartbeat.py` | 集成进程监控；`_record_event()` 改为写入 RedisTimeSeries | P3.2 |
| `scheduler.py` | 扩展动态调度（基于截止日期）；GPU 感知并发限制 | P2.5, P3.4 |

---

## 实现建议优先级

推荐分两个大迭代实现：

**迭代 A（P2 全部 + P4.1）** ~4-6 周
1. P2.4 技能版本（独立、低成本、高价值）
2. P2.1 评审校准（核心质量机制）
3. P2.3 聚合分析 + 成本追踪（可见性）
4. P2.2 全局知识库（核心复用机制）
5. P2.5 趋势适配（外部感知）
6. P4.1 多项目管理（为后续阶段奠基）

**迭代 B（P3 + P4.2-P4.4 + P5）** ~6-10 周
1. P3.1 多日实验（核心自治能力）
2. P3.2 自愈（可靠性）
3. P3.4 资源优化（效率）
4. P4.2-P4.4 协作层
5. P3.3 自动提交 + P5.3 社区互动
6. P5.4 成果追踪 + P5.2 元优化
7. P5.1 全自主生命周期（终极整合）
