#!/usr/bin/env python3
"""Monitor SkillContract violations — CLI monitoring tool.

Usage:
    python3 monitor_contract.py
    python3 monitor_contract.py --clear
    python3 monitor_contract.py --watch   # live tail
"""

import argparse
import json
import time
from collections import Counter

from redis import Redis


def show_config(r):
    config = r.hgetall("academic:contract:config")
    print("=== SkillContract Config ===")
    for k, v in config.items():
        print(f"  {k}: {v}")
    print()


def show_violations(r, last_n=20):
    violations = r.lrange("academic:contract:violations", 0, -1)
    total = len(violations)
    print(f"=== Violations ({total} total) ===")

    for v in reverse(violations[-last_n:]):
        try:
            data = json.loads(v)
            ts = data.get("timestamp", "?")[:19]
            skill = data.get("skill", "?")
            stage = data.get("stage", "?")
            issues = data.get("issues", [])
            print(f"  [{ts}] {skill} | {stage}")
            for issue in issues:
                print(f"    - {issue}")
        except (json.JSONDecodeError, KeyError):
            print(f"  (malformed): {v[:100]}")

    return total, violations


def show_statistics(violations):
    if not violations:
        return

    by_skill = Counter()
    by_stage = Counter()
    for v in violations:
        try:
            data = json.loads(v)
            by_skill[data.get("skill", "unknown")] += 1
            by_stage[data.get("stage", "unknown")] += 1
        except (json.JSONDecodeError, KeyError):
            pass

    print("\n=== Statistics ===")
    print("By skill:")
    for skill, count in sorted(by_skill.items(), key=lambda x: -x[1]):
        bar = "█" * min(count, 40)
        print(f"  {bar} {skill}: {count}")
    print("By stage:")
    for stage, count in sorted(by_stage.items(), key=lambda x: -x[1]):
        bar = "█" * min(count, 40)
        print(f"  {bar} {stage}: {count}")


def reverse(lst):
    return list(reversed(lst))


def main():
    parser = argparse.ArgumentParser(description="Monitor SkillContract violations")
    parser.add_argument("--clear", action="store_true", help="Clear violation log")
    parser.add_argument("--watch", action="store_true", help="Live tail violations")
    parser.add_argument("--last", type=int, default=20, help="Show last N violations")
    args = parser.parse_args()

    r = Redis.from_url("redis://localhost:6379", decode_responses=True)

    if args.clear:
        r.delete("academic:contract:violations")
        print("Cleared violation log")
        return

    if args.watch:
        print("Watching violations (Ctrl+C to stop)...")
        last_count = 0
        try:
            while True:
                violations = r.lrange("academic:contract:violations", 0, -1)
                current_count = len(violations)
                if current_count > last_count:
                    for v in reverse(violations[: current_count - last_count]):
                        try:
                            data = json.loads(v)
                            ts = data.get("timestamp", "?")[:19]
                            skill = data.get("skill", "?")
                            stage = data.get("stage", "?")
                            issues = ", ".join(data.get("issues", []))
                            print(f"  [{ts}] {skill} | {stage} | {issues}")
                        except (json.JSONDecodeError, KeyError):
                            print(f"  (malformed): {v[:100]}")
                    last_count = current_count
                time.sleep(2)
        except KeyboardInterrupt:
            print("\nStopped")
        return

    show_config(r)
    total, violations = show_violations(r, args.last)
    show_statistics(violations)


if __name__ == "__main__":
    main()
