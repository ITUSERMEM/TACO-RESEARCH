"""LogAnalyzer — Differential root cause analysis for production failures.

When tests pass but production fails, extracts audit logs and system state
to perform differential analysis: compare failure context vs last success.

Two modes:
1. Local analysis: pattern matching on log entries (no LLM needed)
2. LLM-assisted: calls Pro model for deep root cause hypothesis

Usage:
    analyzer = LogAnalyzer(audit_log_path="/var/log/academic-team/audit.log")

    # Local analysis
    report = analyzer.analyze_local(failure_timestamp)

    # LLM-assisted
    report = analyzer.analyze_with_llm(pro_llm, failure_timestamp)
"""

import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional


class LogAnalyzer:
    """Differential root cause analysis from audit logs."""

    def __init__(self, audit_log_path: str = "/var/log/academic-team/audit.log",
                 redis_client=None):
        self.log_path = audit_log_path
        self.r = redis_client

    def analyze_local(self, failure_timestamp: str = "",
                      window_minutes: int = 5) -> dict:
        """Analyze logs around a failure timestamp without LLM."""
        entries = self._load_entries()
        if not entries:
            return {"error": "No audit log entries found", "hypotheses": []}

        if failure_timestamp:
            window = self._extract_window(entries, failure_timestamp, window_minutes)
        else:
            window = entries[-20:]

        failure_entries = [e for e in window if e.get("event") == "error"]
        skill_entries = [e for e in window if e.get("event") == "tool_call"]
        phase_entries = [e for e in window if e.get("event") == "phase_transition"]

        hypotheses = []

        if failure_entries:
            for fe in failure_entries:
                details = fe.get("details", "")
                if "RateLimit" in details or "429" in details:
                    hypotheses.append({
                        "rank": 1,
                        "hypothesis": "API 速率限制 (429)",
                        "evidence": details[:200],
                        "verification": "检查 LLM API 配额和当前请求频率",
                        "fix": "增加指数退避重试间隔",
                    })
                elif "timeout" in details.lower() or "Timeout" in details:
                    hypotheses.append({
                        "rank": 2,
                        "hypothesis": "请求超时 (代理/网络)",
                        "evidence": details[:200],
                        "verification": "检查 Clash 代理状态: curl -x 127.0.0.1:7892 https://api.deepseek.com",
                        "fix": "增加超时时间或切换代理节点",
                    })
                elif "LLM error" in details:
                    hypotheses.append({
                        "rank": 3,
                        "hypothesis": "LLM 错误被传递到下游",
                        "evidence": details[:200],
                        "verification": "检查 complete() 返回值是否以 [LLM error: 开头",
                        "fix": "在调用 complete() 后添加错误检查",
                    })

        if skill_entries:
            hung_skills = [e for e in skill_entries if "hang" in str(e.get("output_summary", "")).lower()]
            if hung_skills:
                hypotheses.append({
                    "rank": 4,
                    "hypothesis": f"Skill 执行卡住: {hung_skills[0].get('tool', 'unknown')}",
                    "evidence": str(hung_skills[0].get("output_summary", ""))[:200],
                    "verification": "检查 opencode 进程: ps aux | grep opencode",
                    "fix": "减少 idle timeout 或增加 skill 超时",
                })

        if phase_entries:
            rapid = self._detect_rapid_transitions(phase_entries)
            if rapid:
                hypotheses.append({
                    "rank": 5,
                    "hypothesis": "Phase 快速切换导致状态不一致",
                    "evidence": f"{len(rapid)} 次快速切换",
                    "verification": "检查 PhaseTracker 状态: redis-cli HGETALL academic:phase:tracker",
                    "fix": "增加 Phase 切换间的最小间隔",
                })

        if not hypotheses:
            hypotheses.append({
                "rank": 1,
                "hypothesis": "未知故障 — 需要 LLM 深度分析",
                "evidence": f"窗口内 {len(window)} 条日志，无明显模式",
                "verification": "使用 analyze_with_llm() 进行深度分析",
                "fix": "收集更多日志后再分析",
            })

        return {
            "timestamp": failure_timestamp or "latest",
            "window_entries": len(window),
            "failure_entries": len(failure_entries),
            "skill_entries": len(skill_entries),
            "hypotheses": sorted(hypotheses, key=lambda h: h["rank"]),
        }

    def analyze_with_llm(self, pro_llm, failure_timestamp: str = "",
                         window_minutes: int = 10) -> dict:
        """Deep root cause analysis using Pro model."""
        local_result = self.analyze_local(failure_timestamp, window_minutes)

        entries = self._load_entries()
        if failure_timestamp:
            window = self._extract_window(entries, failure_timestamp, window_minutes)
        else:
            window = entries[-30:]

        success_entries = self._find_last_success(entries, failure_timestamp)

        log_text = json.dumps(window[-15:], indent=2, ensure_ascii=False)[:5000]
        success_text = json.dumps(success_entries[-5:], indent=2, ensure_ascii=False)[:2000]

        prompt = (
            f"本地分析结果:\n{json.dumps(local_result, indent=2, ensure_ascii=False)[:2000]}\n\n"
            f"失败窗口日志 (最近 {len(window)} 条):\n{log_text}\n\n"
            f"最近成功调用日志:\n{success_text}\n\n"
            "请执行差异根因分析，返回 JSON:\n"
            '{"hypotheses": [{"rank": 1, "hypothesis": "...", "evidence": "...", '
            '"verification": "...", "fix": "..."}], '
            '"root_cause_category": "rate_limit|timeout|state_pollution|model_behavior|unknown"}'
        )

        response = pro_llm.complete([
            {"role": "system", "content": (
                "你是系统调试专家。执行差异根因分析。"
                "对比失败日志和成功日志，找出根因。返回 JSON。"
            )},
            {"role": "user", "content": prompt},
        ], max_tokens=2000, temperature=0.2)

        llm_result = self._parse_analysis(response)
        llm_result["local_analysis"] = local_result
        return llm_result

    def get_system_health(self) -> dict:
        """Quick system health snapshot."""
        health = {
            "audit_log_exists": os.path.exists(self.log_path),
            "audit_log_size": 0,
            "recent_errors": 0,
            "redis_connected": False,
        }

        if health["audit_log_exists"]:
            health["audit_log_size"] = os.path.getsize(self.log_path)
            entries = self._load_entries()
            recent = entries[-50:] if entries else []
            health["recent_errors"] = len([e for e in recent if e.get("event") == "error"])
            health["total_entries"] = len(entries)

        if self.r:
            try:
                self.r.ping()
                health["redis_connected"] = True
            except Exception:
                pass

        return health

    def _load_entries(self) -> list[dict]:
        if not os.path.exists(self.log_path):
            return []
        entries = []
        try:
            with open(self.log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        return entries

    @staticmethod
    def _extract_window(entries: list[dict], timestamp: str,
                      window_minutes: int) -> list[dict]:
        try:
            target = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return entries[-20:]

        delta = timedelta(minutes=window_minutes)
        window = []
        for e in entries:
            try:
                ts = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
                if abs((ts - target).total_seconds()) <= delta.total_seconds():
                    window.append(e)
            except (KeyError, ValueError, TypeError):
                continue
        return window or entries[-20:]

    @staticmethod
    def _find_last_success(entries: list[dict], failure_timestamp: str) -> list[dict]:
        success = [e for e in entries
                   if e.get("event") not in ("error",) and e.get("approved", True)]
        return success[-10:] if success else []

    @staticmethod
    def _detect_rapid_transitions(phase_entries: list[dict],
                                  min_interval_sec: int = 5) -> list[dict]:
        if len(phase_entries) < 2:
            return []
        rapid = []
        for i in range(1, len(phase_entries)):
            try:
                t1 = datetime.fromisoformat(phase_entries[i-1]["timestamp"].replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(phase_entries[i]["timestamp"].replace("Z", "+00:00"))
                if (t2 - t1).total_seconds() < min_interval_sec:
                    rapid.append(phase_entries[i])
            except (KeyError, ValueError, TypeError):
                continue
        return rapid

    @staticmethod
    def _parse_analysis(response: str) -> dict:
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {
            "hypotheses": [{"rank": 1, "hypothesis": "LLM 分析失败", "evidence": response[:200]}],
            "root_cause_category": "unknown",
        }
