# Experiment Plan: Transformer Reproduction

**Project**: Attention Is All You Need (Vaswani et al., 2017)
**Date**: 2026-06-27
**Environment**: Offline (synthetic data), 1x RTX 5090 (expected)
**Status**: Phase 3 实验验证

## Overview

Reproduce the Transformer base model (d_model=512, h=8, N=6) and verify:
1. Model architecture correctness (forward pass, gradient flow)
2. Training convergence on synthetic translation data
3. BLEU evaluation pipeline
4. Multi-seed robustness

## Milestones

### M0: Sanity Check (MUST-RUN)
Verify core pipeline end-to-end with tiny config.

| Run | Config | GPU hours | Seeds |
|-----|--------|-----------|-------|
| R000 | d_model=64, num_layers=2, epochs=2, batch_size=32 | 0.02h | [42] |

Success: Training loss decreases, no NaN, BLEU > 0

### M1: Base Model Convergence (MUST-RUN)
Full architecture on synthetic data with original hyperparams.

| Run | Config | GPU hours | Seeds |
|-----|--------|-----------|-------|
| R001-R003 | Base (d_model=512, h=8, N=6), epochs=10, batch_size=128 | 1.5h | [42, 43, 44] |

Success: Loss < 1.0, PPL < 3.0, BLEU > 10

### M2: Ablation: Label Smoothing (NICE-TO-HAVE)
| Run | Config | GPU hours | Seeds |
|-----|--------|-----------|-------|
| R004-R005 | label_smoothing=0.0 vs 0.1 | 0.5h | [42] |

Success: Smoothing improves BLEU by > 1.0

### M3: Ablation: Warmup Steps (NICE-TO-HAVE)
| Run | Config | GPU hours | Seeds |
|-----|--------|-----------|-------|
| R006-R007 | warmup_steps=2000 vs 8000 | 0.5h | [42] |

Success: Warmup=4000 is near-optimal

### M4: Ablation: Beam Search vs Greedy (NICE-TO-HAVE)
| Run | Config | GPU hours | Seeds |
|-----|--------|-----------|-------|
| R008-R010 | beam_size=2, 4, 8 | 0.3h | [42] |

Success: Beam search improves BLEU > greedy

## Total Budget
- Must-run: ~1.5 GPU hours
- Nice-to-have: ~1.3 GPU hours
- Total: ~2.8 GPU hours on 1x GPU

## Metrics
- Primary: Loss, Perplexity, BLEU
- Secondary: Parameter count, tokens/sec
- Logging: TensorBoard, JSON results
