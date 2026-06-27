"""FaultCatalog — Systematic fault pattern catalog for skill execution.

Generates and maintains a structured catalog of known failure modes
that tests cannot cover but occur in production. Two modes:

1. Built-in catalog: 50+ pre-defined fault patterns across 5 dimensions
2. LLM-expanded: calls Pro model to discover new patterns from logs

Usage:
    catalog = FaultCatalog()
    patterns = catalog.get_all()
    high_priority = catalog.get_by_priority("critical")
    catalog.expand_with_llm(pro_llm, recent_logs)
    catalog.save("fault_catalog.json")
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional


FAULT_DIMENSIONS = {
    "input_boundary": "输入边界 — 超长/特殊字符/空值/格式冲突",
    "model_behavior": "模型行为 — 温度波动/截断/幻觉/格式偏离",
    "skill_execution": "Skill执行 — 竞态/僵尸/超时/输出异常",
    "state_pollution": "状态污染 — 跨请求残留/stale状态/缓存不一致",
    "external_deps": "外部依赖 — 代理断开/API限流/存储延迟",
}

BUILTIN_PATTERNS = [
    # ── A. Input Boundary ──
    {
        "id": "IB-001",
        "dimension": "input_boundary",
        "name": "超长上下文截断丢失关键信息",
        "trigger": "输入 > 30000 chars，GateJudge 截断后丢失末尾的公式/引用",
        "test_blind_spot": "测试用短输入，不覆盖截断边界",
        "detection": "截断前后内容差异检查：对比 transcript[-500:] 与 capped[-500:]",
        "prevention": "智能截断：按段落边界截断，保留末尾 2000 chars 摘要",
        "priority": "critical",
        "affected_components": ["gate_judge.py:130", "skill_executor.py:68"],
    },
    {
        "id": "IB-002",
        "dimension": "input_boundary",
        "name": "特殊 Unicode 导致 JSON 解析失败",
        "trigger": "输入包含零宽字符(U+200B)、BOM(U+FEFF)、代理对(surrogate pairs)",
        "test_blind_spot": "测试用纯 ASCII/中文，不含 Unicode 边界字符",
        "detection": "JSON 解析前用 regex 扫描控制字符",
        "prevention": "输入清洗：strip 零宽字符，normalize Unicode",
        "priority": "high",
        "affected_components": ["gate_judge.py:147", "llm_client.py:74"],
    },
    {
        "id": "IB-003",
        "dimension": "input_boundary",
        "name": "空值/None 注入导致 AttributeError",
        "trigger": "LLM 返回空 content (None)，下游 .strip() 崩溃",
        "test_blind_spot": "Mock 总是返回非空字符串",
        "detection": "complete() 返回前检查 content is None",
        "prevention": "llm_client.py:74 已有 `or \"\"` 防护，但 suggest_skill 等调用点未检查",
        "priority": "high",
        "affected_components": ["skill_executor.py:170"],
    },
    {
        "id": "IB-004",
        "dimension": "input_boundary",
        "name": "Markdown 嵌套冲突导致输出解析错误",
        "trigger": "skill 输出包含 ```json 嵌套在 ```markdown 内",
        "test_blind_spot": "测试用简单 JSON，不含嵌套代码块",
        "detection": "正则匹配最外层代码块",
        "prevention": "GateJudge._parse_response 使用最外层 {} 匹配",
        "priority": "medium",
        "affected_components": ["gate_judge.py:151"],
    },
    {
        "id": "IB-005",
        "dimension": "input_boundary",
        "name": "LaTeX 公式未闭合导致下游渲染崩溃",
        "trigger": "LLM 生成 $\\frac{a}{b$ 缺少闭合 }",
        "test_blind_spot": "测试不验证 LaTeX 语法正确性",
        "detection": "括号/花括号计数检查",
        "prevention": "ContractValidator.validate_input 添加 LaTeX 闭合检查",
        "priority": "medium",
        "affected_components": ["paper-writer skill output"],
    },
    {
        "id": "IB-006",
        "dimension": "input_boundary",
        "name": "shlex.quote 对空字符串行为异常",
        "trigger": "args 为空字符串时 shlex.quote('') 返回 \"''\"",
        "test_blind_spot": "测试总是传非空 args",
        "detection": "args 为空时跳过 shlex.quote",
        "prevention": "skill_executor.py:68 已有条件判断 `if args`",
        "priority": "low",
        "affected_components": ["skill_executor.py:68"],
    },

    # ── B. Model Behavior ──
    {
        "id": "MB-001",
        "dimension": "model_behavior",
        "name": "温度波动导致输出格式偏离",
        "trigger": "temperature > 0.1 时 LLM 可能输出非 JSON 格式",
        "test_blind_spot": "测试用 temperature=0.0，生产用 0.1-0.3",
        "detection": "GateJudge._parse_response 已有 fallback 解析",
        "prevention": "Gate 评审固定 temperature=0.1，关键路径用 0.0",
        "priority": "critical",
        "affected_components": ["gate_judge.py:135"],
    },
    {
        "id": "MB-002",
        "dimension": "model_behavior",
        "name": "max_tokens 截断导致 JSON 不完整",
        "trigger": "GateJudge max_tokens=200，复杂评审需要更多 token",
        "test_blind_spot": "测试用简单输入，200 tokens 足够",
        "detection": "检查 JSON 是否完整（闭合大括号）",
        "prevention": "_parse_response 已有 fallback；可动态调整 max_tokens",
        "priority": "high",
        "affected_components": ["gate_judge.py:135"],
    },
    {
        "id": "MB-003",
        "dimension": "model_behavior",
        "name": "工具调用幻觉 (tool call hallucination)",
        "trigger": "LLM 声称执行了搜索/读取但实际未调用",
        "test_blind_spot": "测试不验证 LLM 声称的动作是否真实执行",
        "detection": "HallucinationGuard 3 层检测",
        "prevention": "已有 HallucinationGuard，但仅覆盖 3 种模式",
        "priority": "high",
        "affected_components": ["hallucination_guard.py"],
    },
    {
        "id": "MB-004",
        "dimension": "model_behavior",
        "name": "模型返回重复文本（退化模式）",
        "trigger": "deepseek-v4-flash 在高负载时输出重复句子",
        "test_blind_spot": "测试检查非空但不检查重复",
        "detection": "EntropyMonitor 检测熵突然下降",
        "prevention": "skill_contract.py EntropyMonitor + 自动重试",
        "priority": "high",
        "affected_components": ["llm_client.py"],
    },
    {
        "id": "MB-005",
        "dimension": "model_behavior",
        "name": "模型返回 [LLM error: ...] 被当作正常输出",
        "trigger": "LLM 调用失败，complete() 返回错误字符串，下游当正常文本处理",
        "test_blind_spot": "测试中 LLM 总是成功",
        "detection": "检查输出是否以 [LLM error: 开头",
        "prevention": "complete() 改为 raise 异常或返回 Result 类型",
        "priority": "critical",
        "affected_components": ["llm_client.py:77", "academic_loop.py"],
    },
    {
        "id": "MB-006",
        "dimension": "model_behavior",
        "name": "reasoning token 消耗 max_tokens 预算",
        "trigger": "deepseek-v4-pro 的 reasoning 占用大量 token，实际输出为空",
        "test_blind_spot": "测试用简单问题，reasoning 不消耗太多",
        "detection": "检查 usage.reasoning_tokens 占比",
        "prevention": "pro 模型 max_tokens 提高到 500+，或分离 reasoning budget",
        "priority": "medium",
        "affected_components": ["llm_client.py"],
    },

    # ── C. Skill Execution ──
    {
        "id": "SE-001",
        "dimension": "skill_execution",
        "name": "select.select 30s idle 竞态条件",
        "trigger": "skill 在 30s 边界恰好输出最后一行，被误判为 hang",
        "test_blind_spot": "测试用 mock subprocess，不触发真实时序",
        "detection": "hang 返回前检查 proc.poll() 是否已退出",
        "prevention": "skill_executor.py:119 已有 poll 检查，但 30s 分支未检查",
        "priority": "critical",
        "affected_components": ["skill_executor.py:95-118"],
    },
    {
        "id": "SE-002",
        "dimension": "skill_execution",
        "name": "子进程僵尸状态",
        "trigger": "proc.kill() 后子进程变为 zombie，未被 wait() 回收",
        "test_blind_spot": "测试不检查 zombie 进程",
        "detection": "proc.wait(timeout=5) 检查返回值",
        "prevention": "skill_executor.py:103-104 已有 kill+wait",
        "priority": "medium",
        "affected_components": ["skill_executor.py:103"],
    },
    {
        "id": "SE-003",
        "dimension": "skill_execution",
        "name": "stderr 读取阻塞",
        "trigger": "stderr 缓冲区满，子进程阻塞等待读取",
        "test_blind_spot": "测试不产生大量 stderr",
        "detection": "stderr 用非阻塞读取",
        "prevention": "skill_executor.py:98 用 read(2000) 限制读取量",
        "priority": "high",
        "affected_components": ["skill_executor.py:98", "skill_executor.py:134"],
    },
    {
        "id": "SE-004",
        "dimension": "skill_execution",
        "name": "skill 输出包含 ANSI 转义序列污染",
        "trigger": "opencode CLI 输出彩色终端序列，_strip_chrome 未完全清除",
        "test_blind_spot": "测试用纯文本输出",
        "detection": "正则匹配 \\x1b[ 序列",
        "prevention": "_strip_chrome 已有 ANSI 清除，但可能遗漏新序列",
        "priority": "low",
        "affected_components": ["skill_executor.py:222-223"],
    },
    {
        "id": "SE-005",
        "dimension": "skill_execution",
        "name": "timeout 命令嵌套导致信号传递失败",
        "trigger": "timeout 120 opencode run ... 中 opencode 内部也有超时",
        "test_blind_spot": "测试不触发 120s 超时",
        "detection": "检查 returncode == 124 (timeout 退出码)",
        "prevention": "skill_executor.py:142 检查 elapsed >= SKILL_TIMEOUT",
        "priority": "medium",
        "affected_components": ["skill_executor.py:69"],
    },
    {
        "id": "SE-006",
        "dimension": "skill_execution",
        "name": "并发 skill 调用资源竞争",
        "trigger": "两个 Agent 同时调用同一 skill，共享临时文件冲突",
        "test_blind_spot": "测试串行执行，不触发并发",
        "detection": "文件锁或 PID 检查",
        "prevention": "每个 skill 调用使用唯一临时目录",
        "priority": "high",
        "affected_components": ["skill_executor.py"],
    },

    # ── D. State Pollution ──
    {
        "id": "SP-001",
        "dimension": "state_pollution",
        "name": "SessionCache 跨请求残留",
        "trigger": "上一个 pipeline 的 session 数据未清理，污染新请求",
        "test_blind_spot": "测试每次创建新 SessionCache 实例",
        "detection": "session 开始时检查残留数据",
        "prevention": "SessionCache.clear() 在 pipeline 启动时调用",
        "priority": "critical",
        "affected_components": ["session_cache.py"],
    },
    {
        "id": "SP-002",
        "dimension": "state_pollution",
        "name": "PhaseTracker stale 状态与当前任务冲突",
        "trigger": "PhaseTracker 记录了上一个 pipeline 的 phase，新 pipeline 读到旧状态",
        "test_blind_spot": "测试用新 PhaseTracker 实例",
        "detection": "启动时检查 stale 状态 (>10min)",
        "prevention": "academic_loop.py 已有 stale 清理逻辑",
        "priority": "high",
        "affected_components": ["academic_loop.py"],
    },
    {
        "id": "SP-003",
        "dimension": "state_pollution",
        "name": "AgentRegistry skill 缓存不一致",
        "trigger": "agent-registry.md 更新后 SkillExecutor 仍用旧缓存",
        "test_blind_spot": "测试用固定 registry 文件",
        "detection": "文件 mtime 检查",
        "prevention": "_ensure_loaded 添加 mtime 比较",
        "priority": "medium",
        "affected_components": ["skill_executor.py:177-181"],
    },
    {
        "id": "SP-004",
        "dimension": "state_pollution",
        "name": "DualLLM 实例共享 token 计数器",
        "trigger": "多个 pipeline 共享同一 DualLLM，total_tokens 累加不准确",
        "test_blind_spot": "测试每次创建新 DualLLM",
        "detection": "TokenBudget 独立追踪",
        "prevention": "每个 pipeline 创建独立 DualLLM 实例",
        "priority": "low",
        "affected_components": ["llm_client.py:51-52"],
    },
    {
        "id": "SP-005",
        "dimension": "state_pollution",
        "name": "Redis pub/sub 消息丢失（无持久化）",
        "trigger": "Telegram bridge 断连期间发布的消息永久丢失",
        "test_blind_spot": "测试中 bridge 总是连接",
        "detection": "消息序号检查",
        "prevention": "关键消息同时写入 Redis stream (持久化)",
        "priority": "high",
        "affected_components": ["telegram_bridge.py", "event_system.py"],
    },

    # ── E. External Dependencies ──
    {
        "id": "ED-001",
        "dimension": "external_deps",
        "name": "Clash 代理瞬时断开",
        "trigger": "代理进程重启或网络波动，LLM API 调用超时",
        "test_blind_spot": "测试环境代理稳定",
        "detection": "连接失败时检查代理状态",
        "prevention": "llm_client.py 已有指数退避重试 (1s/2s/4s)",
        "priority": "critical",
        "affected_components": ["llm_client.py:27-34"],
    },
    {
        "id": "ED-002",
        "dimension": "external_deps",
        "name": "Telegram API 限流",
        "trigger": "短时间内发送过多消息，触发 429 Too Many Requests",
        "test_blind_spot": "测试发送少量消息",
        "detection": "HTTP 429 响应码",
        "prevention": "消息队列 + 速率限制 (30 msg/min)",
        "priority": "high",
        "affected_components": ["telegram_bridge.py"],
    },
    {
        "id": "ED-003",
        "dimension": "external_deps",
        "name": "Redis AOF 重写延迟峰值",
        "trigger": "BGREWRITEAOF 期间 Redis 响应变慢 (>100ms)",
        "test_blind_spot": "测试中 Redis 无 AOF 重写",
        "detection": "Redis SLOWLOG 检查",
        "prevention": "关键路径添加超时重试",
        "priority": "medium",
        "affected_components": ["所有 Redis 操作"],
    },
    {
        "id": "ED-004",
        "dimension": "external_deps",
        "name": "opencode CLI 版本不兼容",
        "trigger": "opencode 更新后 /skill_name 参数格式变化",
        "test_blind_spot": "测试用固定 opencode 版本",
        "detection": "opencode --version 检查",
        "prevention": "启动时验证 CLI 版本",
        "priority": "low",
        "affected_components": ["skill_executor.py:69"],
    },
    {
        "id": "ED-005",
        "dimension": "external_deps",
        "name": "systemd 服务重启导致状态丢失",
        "trigger": "systemctl restart 后内存中的 pipeline 状态丢失",
        "test_blind_spot": "测试不重启服务",
        "detection": "启动时检查 Redis 中的 pipeline 状态",
        "prevention": "AcademicLoop 启动时从 Redis 恢复状态",
        "priority": "high",
        "affected_components": ["academic_loop.py", "team_launcher.py"],
    },
]


class FaultCatalog:
    """Structured fault pattern catalog with search and expansion."""

    def __init__(self):
        self._patterns = list(BUILTIN_PATTERNS)

    def get_all(self) -> list[dict]:
        return self._patterns

    def get_by_priority(self, priority: str) -> list[dict]:
        return [p for p in self._patterns if p["priority"] == priority]

    def get_by_dimension(self, dimension: str) -> list[dict]:
        return [p for p in self._patterns if p["dimension"] == dimension]

    def get_by_id(self, pattern_id: str) -> Optional[dict]:
        for p in self._patterns:
            if p["id"] == pattern_id:
                return p
        return None

    def get_critical(self) -> list[dict]:
        return self.get_by_priority("critical")

    def summary(self) -> dict:
        by_dim = {}
        by_pri = {}
        for p in self._patterns:
            by_dim[p["dimension"]] = by_dim.get(p["dimension"], 0) + 1
            by_pri[p["priority"]] = by_pri.get(p["priority"], 0) + 1
        return {
            "total": len(self._patterns),
            "by_dimension": by_dim,
            "by_priority": by_pri,
            "dimensions": FAULT_DIMENSIONS,
        }

    def add_pattern(self, pattern: dict):
        if not pattern.get("id"):
            pattern["id"] = f"GEN-{len(self._patterns)+1:03d}"
        self._patterns.append(pattern)

    def expand_with_llm(self, pro_llm, recent_logs: str = "") -> list[dict]:
        """Call Pro model to discover new fault patterns from logs."""
        prompt = self._build_expansion_prompt(recent_logs)
        response = pro_llm.complete([
            {"role": "system", "content": (
                "你是系统可靠性工程师。分析多智能体学术系统的故障模式。"
                "返回 JSON 数组，每个元素包含: id, dimension, name, trigger, "
                "test_blind_spot, detection, prevention, priority"
            )},
            {"role": "user", "content": prompt},
        ], max_tokens=4000, temperature=0.2)

        new_patterns = self._parse_patterns(response)
        for p in new_patterns:
            if not self.get_by_id(p.get("id", "")):
                self.add_pattern(p)
        return new_patterns

    def save(self, path: str = "fault_catalog.json"):
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": self.summary(),
            "patterns": self._patterns,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "FaultCatalog":
        catalog = cls()
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            catalog._patterns = data.get("patterns", BUILTIN_PATTERNS)
        return catalog

    def _build_expansion_prompt(self, recent_logs: str) -> str:
        existing_ids = [p["id"] for p in self._patterns]
        return (
            f"当前已有 {len(self._patterns)} 个故障模式 (IDs: {', '.join(existing_ids[:10])}...)。\n\n"
            f"最近生产日志:\n{recent_logs[:5000]}\n\n"
            "请发现新的故障模式（不要重复已有的）。"
            "返回 JSON 数组。"
        )

    @staticmethod
    def _parse_patterns(response: str) -> list[dict]:
        import re
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
                if isinstance(result, list):
                    return [p for p in result if isinstance(p, dict)]
            except json.JSONDecodeError:
                pass
        return []
