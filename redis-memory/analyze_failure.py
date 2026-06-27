#!/usr/bin/env python3
"""CLI 工具：分析生产环境失败根因（L4）。

Usage:
    python3 analyze_failure.py --timestamp "2026-06-27T10:00:00+00:00"
    python3 analyze_failure.py --latest
    python3 analyze_failure.py --health
    python3 analyze_failure.py --latest --llm
    python3 analyze_failure.py --config
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from redis import Redis

from log_analyzer import LogAnalyzer


def show_contract_config(r):
    config = r.hgetall("academic:contract:config")
    print("=== Contract Config ===")
    for k, v in config.items():
        print(f"  {k}: {v}")


def main():
    parser = argparse.ArgumentParser(description="Analyze production failures")
    parser.add_argument("--timestamp", help="Failure timestamp (ISO 8601)")
    parser.add_argument("--latest", action="store_true", help="Analyze latest entries")
    parser.add_argument("--health", action="store_true", help="Show system health")
    parser.add_argument("--llm", action="store_true", help="Use LLM for deep analysis")
    parser.add_argument("--config", action="store_true", help="Show contract config")
    parser.add_argument("--window", type=int, default=5, help="Time window in minutes")
    args = parser.parse_args()

    analyzer = LogAnalyzer(
        audit_log_path="/var/log/academic-team/audit.log",
        redis_client=None,
    )

    if args.config:
        try:
            r = Redis.from_url("redis://localhost:6379", decode_responses=True)
            show_contract_config(r)
            r.close()
        except Exception as e:
            print(f"Failed to connect to Redis: {e}")
        return

    if args.health:
        health = analyzer.get_system_health()
        print(json.dumps(health, indent=2, ensure_ascii=False))
        return

    timestamp = args.timestamp if args.timestamp else ""

    if args.llm:
        from llm_client import DualLLM
        dual = DualLLM()
        print("Calling Pro model for deep analysis...")
        report = analyzer.analyze_with_llm(dual.pro, timestamp, args.window)
    else:
        report = analyzer.analyze_local(timestamp, args.window)

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
