#!/usr/bin/env python3
"""用 Pro 模型扩展故障目录 (L1)。

Usage:
    python3 expand_fault_catalog.py
    python3 expand_fault_catalog.py --save fault_catalog_expanded.json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from fault_catalog import FaultCatalog
from llm_client import DualLLM


def main():
    parser = argparse.ArgumentParser(description="Expand fault catalog with Pro model")
    parser.add_argument("--save", default="fault_catalog_expanded.json",
                        help="Output path")
    parser.add_argument("--load", help="Load existing catalog from file")
    args = parser.parse_args()

    if args.load and os.path.exists(args.load):
        catalog = FaultCatalog.load(args.load)
    else:
        catalog = FaultCatalog()

    dual = DualLLM()

    recent_logs = ""
    log_path = "/var/log/academic-team/audit.log"
    if os.path.exists(log_path):
        with open(log_path) as f:
            lines = f.readlines()
            recent_logs = "".join(lines[-50:])
    else:
        print("No audit log found, using empty context")

    print(f"Current patterns: {len(catalog.get_all())}")
    print("Calling Pro model to discover new patterns...")

    new_patterns = catalog.expand_with_llm(dual.pro, recent_logs)

    if new_patterns:
        print(f"\nDiscovered {len(new_patterns)} new patterns:")
        for p in new_patterns:
            print(f"  [{p.get('priority', '?')}] {p.get('id', '?')}: {p.get('name', '?')}")
            trigger = p.get('trigger', '')[:80]
            if trigger:
                print(f"    Trigger: {trigger}")
    else:
        print("\nNo new patterns discovered (LLM returned no valid patterns)")

    catalog.save(args.save)
    print(f"\nSaved to {args.save}")
    print(f"Total patterns: {len(catalog.get_all())}")


if __name__ == "__main__":
    main()
