"""AdversarialTestGenerator — Generate adversarial test cases for skill execution.

Calls Executor model to produce test cases targeting the gap between
"tests pass" and "production fails". Two modes:

1. Template-based: pre-defined adversarial inputs (works offline)
2. LLM-generated: calls Executor to discover new attack vectors

Usage:
    gen = AdversarialTestGenerator()
    cases = gen.generate_all()
    gen.save_as_pytest("tests/test_adversarial.py")
"""

import json
import os
import re
from typing import Optional


ADVERSARIAL_DIMENSIONS = {
    "input_toxicity": "输入毒性 — 格式错误的 LaTeX/公式/特殊标记",
    "context_pressure": "上下文压力 — 截断边界/超长输入",
    "temporal_disruption": "时序扰动 — Redis 延迟/stale 状态",
    "concurrent_ghost": "并发幽灵 — 多 Agent 同时调用",
    "model_deception": "模型欺骗 — 伪成功输出",
}

BUILTIN_CASES = [
    # ── Input Toxicity ──
    {
        "id": "AT-001",
        "dimension": "input_toxicity",
        "name": "未闭合 LaTeX 公式",
        "input": "The equation $\\frac{a}{b + \\frac{c}{d$ shows the relationship.",
        "target": "GateJudge._parse_response",
        "expected_behavior": "返回有效 verdict，不因 LaTeX 解析错误崩溃",
        "assertion": "result.get('verdict') in ('pass', 'revise', 'fail')",
    },
    {
        "id": "AT-002",
        "dimension": "input_toxicity",
        "name": "嵌套 JSON 代码块",
        "input": '```json\n{"verdict": "pass", "nested": ```json\n{"inner": true}\n```}',
        "target": "GateJudge._parse_response",
        "expected_behavior": "提取最外层 JSON，不因嵌套代码块崩溃",
        "assertion": "result.get('verdict') in ('pass', 'revise', 'fail')",
    },
    {
        "id": "AT-003",
        "dimension": "input_toxicity",
        "name": "零宽字符注入",
        "input": "This is a\u200Bvalid\u200Btext with\uFEFFzero-width chars.",
        "target": "LLMClient.complete",
        "expected_behavior": "正常处理，不因零宽字符崩溃或返回空",
        "assertion": "len(response.strip()) > 0",
    },
    {
        "id": "AT-004",
        "dimension": "input_toxicity",
        "name": "Unicode 代理对",
        "input": "Emoji test: \U0001F600 and math: \u221A\u221E",
        "target": "LLMClient.complete",
        "expected_behavior": "正常处理 Unicode 补充平面字符",
        "assertion": "len(response.strip()) > 0",
    },

    # ── Context Pressure ──
    {
        "id": "AT-005",
        "dimension": "context_pressure",
        "name": "恰好 30000 chars 截断边界",
        "input": "A" * 29990 + "CRITICAL_INFO_AT_END",
        "target": "GateJudge.evaluate (capped at 30000)",
        "expected_behavior": "不因截断丢失末尾关键信息",
        "assertion": "len(transcript) <= 30000",
    },
    {
        "id": "AT-006",
        "dimension": "context_pressure",
        "name": "恰好 30001 chars 触发截断",
        "input": "B" * 30001,
        "target": "GateJudge.evaluate",
        "expected_behavior": "截断后仍返回有效 verdict",
        "assertion": "result.get('verdict') in ('pass', 'revise', 'fail')",
    },
    {
        "id": "AT-007",
        "dimension": "context_pressure",
        "name": "极短输入 (1 char)",
        "input": "X",
        "target": "GateJudge.evaluate",
        "expected_behavior": "不因输入太短而崩溃",
        "assertion": "result.get('verdict') in ('pass', 'revise', 'fail')",
    },
    {
        "id": "AT-008",
        "dimension": "context_pressure",
        "name": "纯空白输入",
        "input": "   \n\n\t  \n",
        "target": "GateJudge.evaluate",
        "expected_behavior": "返回默认 verdict",
        "assertion": "result.get('verdict') in ('pass', 'revise', 'fail')",
    },

    # ── Temporal Disruption ──
    {
        "id": "AT-009",
        "dimension": "temporal_disruption",
        "name": "PhaseTracker stale 状态 (>10min)",
        "input": {"phase": 2, "timestamp_offset_minutes": 15},
        "target": "PhaseTracker.process_incoming",
        "expected_behavior": "自动清理 stale 状态，不污染新 pipeline",
        "assertion": "tracker.get_state() == 'idle' or tracker.get_state() is None",
    },
    {
        "id": "AT-010",
        "dimension": "temporal_disruption",
        "name": "快速连续 Phase 切换",
        "input": [{"phase": 1}, {"phase": 2}, {"phase": 3}],
        "target": "PhaseTracker",
        "expected_behavior": "正确处理快速切换，不丢失中间状态",
        "assertion": "tracker.current_phase == 3",
    },

    # ── Concurrent Ghost ──
    {
        "id": "AT-011",
        "dimension": "concurrent_ghost",
        "name": "两个 Agent 同时调用 suggest_skill",
        "input": {"role": "literature-researcher", "concurrent": 2},
        "target": "SkillExecutor.suggest_skill",
        "expected_behavior": "两个调用独立返回，不互相干扰",
        "assertion": "both results are not None",
    },

    # ── Model Deception ──
    {
        "id": "AT-012",
        "dimension": "model_deception",
        "name": "LLM 返回 [LLM error: ...] 被当正常输出",
        "input": "[LLM error: RateLimitError: 429]",
        "target": "下游处理 LLM 输出的代码",
        "expected_behavior": "检测到错误字符串，不传递给 GateJudge",
        "assertion": "not response.startswith('[LLM error:')",
    },
    {
        "id": "AT-013",
        "dimension": "model_deception",
        "name": "LLM 返回空 JSON {}",
        "input": "{}",
        "target": "GateJudge._parse_response",
        "expected_behavior": "返回默认 verdict=pass",
        "assertion": "result.get('verdict') == 'pass'",
    },
    {
        "id": "AT-014",
        "dimension": "model_deception",
        "name": "LLM 返回部分 JSON (截断)",
        "input": '{"verdict": "revise", "issues": ["issue1", "issu',
        "target": "GateJudge._parse_response",
        "expected_behavior": "fallback 解析提取 verdict",
        "assertion": "result.get('verdict') in ('pass', 'revise', 'fail')",
    },
    {
        "id": "AT-015",
        "dimension": "model_deception",
        "name": "LLM 返回非 JSON 纯文本",
        "input": "I think this paper should pass the review because it is novel.",
        "target": "GateJudge._parse_response",
        "expected_behavior": "从文本中提取 verdict",
        "assertion": "result.get('verdict') in ('pass', 'revise', 'fail')",
    },
    {
        "id": "AT-016",
        "dimension": "model_deception",
        "name": "LLM 返回矛盾 verdict",
        "input": '{"verdict": "pass_and_fail", "issues": []}',
        "target": "GateJudge._validate_result",
        "expected_behavior": "无效 verdict 被修正为 pass",
        "assertion": "result.get('verdict') == 'pass'",
    },

    # ── Edge Cases ──
    {
        "id": "AT-017",
        "dimension": "input_toxicity",
        "name": "shlex 特殊字符注入",
        "input": "test; rm -rf / #",
        "target": "SkillExecutor.run_skill (shlex.quote)",
        "expected_behavior": "shlex.quote 正确转义，不执行注入命令",
        "assertion": "result['status'] in ('ok', 'error') and 'rm -rf' not in result.get('output', '')",
    },
    {
        "id": "AT-018",
        "dimension": "input_toxicity",
        "name": "超长 skill 名称",
        "input": "a" * 500,
        "target": "SkillExecutor.run_skill",
        "expected_behavior": "返回 error，不因超长名称崩溃",
        "assertion": "result['status'] == 'error'",
    },
    {
        "id": "AT-019",
        "dimension": "context_pressure",
        "name": "HallucinationGuard 误报正常文本",
        "input": "I searched the literature and found relevant papers.",
        "target": "HallucinationGuard.check",
        "expected_behavior": "无 executed_tools 时检测到未验证声明",
        "assertion": "nudge is not None (Layer 2 triggers)",
    },
    {
        "id": "AT-020",
        "dimension": "model_deception",
        "name": "重复文本退化检测",
        "input": "The result is good. " * 50,
        "target": "EntropyMonitor",
        "expected_behavior": "检测到熵低于阈值",
        "assertion": "monitor.is_repetitive(text) == True",
    },
]


class AdversarialTestGenerator:
    """Generate adversarial test cases for skill execution pipeline."""

    def __init__(self):
        self._cases = list(BUILTIN_CASES)

    def get_all(self) -> list[dict]:
        return self._cases

    def get_by_dimension(self, dimension: str) -> list[dict]:
        return [c for c in self._cases if c["dimension"] == dimension]

    def generate_with_llm(self, executor_llm, skill_flow: str = "") -> list[dict]:
        """Call Executor model to generate additional adversarial cases."""
        prompt = self._build_prompt(skill_flow)
        response = executor_llm.complete([
            {"role": "system", "content": (
                "你是对抗性测试工程师。生成能触发'测试通过但生产失败'的测试用例。"
                "返回 JSON 数组，每个元素: id, dimension, name, input, target, "
                "expected_behavior, assertion"
            )},
            {"role": "user", "content": prompt},
        ], max_tokens=3000, temperature=0.3)

        new_cases = self._parse_cases(response)
        for c in new_cases:
            if not any(existing["id"] == c.get("id") for existing in self._cases):
                self._cases.append(c)
        return new_cases

    def save_as_pytest(self, path: str = "tests/test_adversarial.py"):
        """Generate a pytest test file from all adversarial cases."""
        lines = [
            '"""Adversarial tests — boundary conditions that pass unit tests',
            'but fail in production.',
            '',
            'Auto-generated by adversarial_test_generator.py.',
            '"""',
            '',
            'import os',
            'import sys',
            'import json',
            'import pytest',
            '',
            'sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))',
            '',
        ]

        for case in self._cases:
            func_name = f"test_{case['id'].lower().replace('-', '_')}_{self._slugify(case['name'])}"
            lines.extend(self._generate_test_function(case, func_name))
            lines.append("")

        with open(path, "w") as f:
            f.write("\n".join(lines))

    def summary(self) -> dict:
        by_dim = {}
        for c in self._cases:
            by_dim[c["dimension"]] = by_dim.get(c["dimension"], 0) + 1
        return {
            "total": len(self._cases),
            "by_dimension": by_dim,
            "dimensions": ADVERSARIAL_DIMENSIONS,
        }

    def _build_prompt(self, skill_flow: str) -> str:
        existing_ids = [c["id"] for c in self._cases]
        return (
            f"已有 {len(self._cases)} 个对抗测试 (IDs: {', '.join(existing_ids[:5])}...)。\n\n"
            f"Skill 执行流程:\n{skill_flow or '(standard flow)'}\n\n"
            "生成新的对抗性测试用例（不重复已有的）。\n"
            "重点覆盖: 输入毒性、上下文压力、时序扰动、并发幽灵、模型欺骗。\n"
            "返回 JSON 数组。"
        )

    @staticmethod
    def _parse_cases(response: str) -> list[dict]:
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
                if isinstance(result, list):
                    return [c for c in result if isinstance(c, dict)]
            except json.JSONDecodeError:
                pass
        return []

    @staticmethod
    def _slugify(name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "_", name)
        slug = re.sub(r"_+", "_", slug).strip("_")
        return slug[:40]

    @staticmethod
    def _generate_test_function(case: dict, func_name: str) -> list[str]:
        input_val = case.get("input", "")
        if isinstance(input_val, dict):
            input_repr = repr(input_val)
        elif isinstance(input_val, list):
            input_repr = repr(input_val)
        else:
            input_repr = repr(str(input_val))

        dim = case["dimension"]
        lines = [
            f"class Test{case['id'].replace('-', '')}:",
            f'    """{case["name"]} — {ADVERSARIAL_DIMENSIONS.get(dim, dim)}"""',
            "",
        ]

        if dim == "input_toxicity" and isinstance(input_val, str):
            lines.extend([
                f"    def {func_name}(self):",
                f"        from gate_judge import GateJudge",
                f"        gj = GateJudge()",
                f"        result = gj.evaluate(1, {input_repr})",
                f"        assert result.get('verdict') in ('pass', 'revise', 'fail')",
            ])
        elif dim == "context_pressure" and isinstance(input_val, str):
            lines.extend([
                f"    def {func_name}(self):",
                f"        from gate_judge import GateJudge",
                f"        gj = GateJudge()",
                f"        text = {input_repr}",
                f"        result = gj.evaluate(1, text)",
                f"        assert result.get('verdict') in ('pass', 'revise', 'fail')",
            ])
        elif dim == "model_deception":
            lines.extend([
                f"    def {func_name}(self):",
                f"        from gate_judge import GateJudge",
                f"        gj = GateJudge()",
                f"        result = gj._parse_response({input_repr})",
                f"        gj._validate_result(result)",
                f"        assert result.get('verdict') in ('pass', 'revise', 'fail')",
            ])
        elif dim == "input_toxicity" and "shlex" in case.get("name", ""):
            lines.extend([
                f"    def {func_name}(self):",
                f"        import shlex",
                f"        args = {input_repr}",
                f"        safe = shlex.quote(args[:300]) if args else ''",
                f"        assert 'rm -rf' not in safe",
            ])
        elif dim == "model_deception" and "重复" in case.get("name", ""):
            lines.extend([
                f"    def {func_name}(self):",
                f"        from skill_contract import EntropyMonitor",
                f"        monitor = EntropyMonitor()",
                f"        text = {input_repr}",
                f"        assert monitor.is_repetitive(text)",
            ])
        else:
            lines.extend([
                f"    def {func_name}(self):",
                f"        from gate_judge import GateJudge",
                f"        gj = GateJudge()",
                f"        result = gj.evaluate(1, {input_repr})",
                f"        assert result.get('verdict') in ('pass', 'revise', 'fail')",
            ])

        return lines
