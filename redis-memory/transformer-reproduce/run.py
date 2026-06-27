#!/usr/bin/env python3
"""
Transformer Reproduction: "Attention Is All You Need"
Run full pipeline: train → evaluate → visualize
"""

import os
import sys
import subprocess

PHASES = ['train', 'evaluate']


def run_phase(phase: str):
    print(f"\n{'='*60}")
    print(f"  Phase: {phase.upper()}")
    print(f"{'='*60}\n")

    if phase == 'train':
        from train import main as train_main
        model, src_vocab, tgt_vocab, results = train_main()
        return results

    elif phase == 'evaluate':
        from evaluate import main as eval_main
        eval_main()

    return None


def main():
    print("=" * 60)
    print("  Attention Is All You Need - Reproduction")
    print("  Vaswani et al. (2017) - Full PyTorch Implementation")
    print("=" * 60)

    for phase in PHASES:
        run_phase(phase)

    print(f"\n{'='*60}")
    print("  Pipeline complete!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
