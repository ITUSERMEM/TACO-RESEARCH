#!/usr/bin/env python3
"""用 Executor 模型生成对抗性测试 (L2)。

Usage:
    python3 expand_adversarial_tests.py
    python3 expand_adversarial_tests.py --save tests/test_adversarial_expanded.py
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from adversarial_test_generator import AdversarialTestGenerator
from llm_client import DualLLM


def main():
    parser = argparse.ArgumentParser(
        description="Expand adversarial tests with Executor model"
    )
    parser.add_argument("--save", default="tests/test_adversarial_expanded.py",
                        help="Output pytest file path")
    args = parser.parse_args()

    gen = AdversarialTestGenerator()
    dual = DualLLM()

    skill_flow = """
    1. Agent 从 agent-registry.md 读取 skill 列表
    2. 调用 opencode run /skill_name
    3. skill_executor 使用 select.select 非阻塞读 stdout，30s idle 自动终止
    4. 输出经 GateJudge 评判 (G1/G3/G4/G6→glm-5.2, G2/G5/G7→deepseek-v4-pro)
    """

    print(f"Current cases: {len(gen.get_all())}")
    print("Calling Executor model to generate adversarial cases...")

    new_cases = gen.generate_with_llm(dual.executor, skill_flow)

    if new_cases:
        print(f"\nGenerated {len(new_cases)} new cases:")
        for c in new_cases:
            print(f"  [{c.get('dimension', '?')}] {c.get('id', '?')}: {c.get('name', '?')}")
            inp = str(c.get('input', ''))[:80]
            if inp:
                print(f"    Input: {inp}")
    else:
        print("\nNo new cases generated (LLM returned no valid cases)")

    output_dir = os.path.dirname(args.save)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    gen.save_as_pytest(args.save)
    print(f"\nSaved to {args.save}")
    print(f"Total cases: {len(gen.get_all())}")

    print("\nRun tests with:")
    print(f"  python3 -m pytest {args.save} -v")


if __name__ == "__main__":
    main()
