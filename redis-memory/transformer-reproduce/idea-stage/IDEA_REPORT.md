# Transformer Reproduction Plan

**Project**: Attention Is All You Need (Vaswani et al., 2017) Full Reproduction
**Date**: 2026-06-27
**Status**: Approved

## Core Claims to Reproduce

1. Transformer outperforms recurrent/convolutional baselines on WMT 2014 English-German translation
2. Multi-head attention captures diverse representation subspaces
3. Self-attention layers enable parallel computation and faster training
4. The architecture generalizes to English-French translation

## Reproduction Scope (Adjusted)

Given the compute constraints (single RTX 5090), we scale down but preserve the essential architecture:

| Original | Our Reproduction |
|----------|-----------------|
| WMT 2014 EN-DE (4.5M sentence pairs) | Multi30k EN-DE (30k) + WMT14 small sample |
| 8× P100 GPUs, 12h training | 1× RTX 5090, ~2h training |
| Base model: d_model=512, h=8 | Same architecture (d_model=512, h=8) |
| BLEU: 27.3 (EN-DE base) | Target: ~25+ on Multi30k |

## Key Metrics

- **Primary**: BLEU score on test set
- **Secondary**: Training loss convergence, attention visualization, translation speed
- **Target**: Reproduce the core architectural components and show the Transformer's effectiveness

## Architecture (Full Reproduction)

- Encoder: 6 layers, each with multi-head self-attention + FFN
- Decoder: 6 layers, each with masked self-attention + cross-attention + FFN
- d_model = 512, d_ff = 2048, h = 8 attention heads
- Dropout = 0.1, Label smoothing = 0.1
- Adam: β₁=0.9, β₂=0.98, ε=1e-9
- Warmup steps: 4000, Learning rate schedule with sqrt decay
- Sinusoidal positional encoding

## Deliverables

- [x] Complete Transformer implementation in PyTorch
- [x] Training pipeline with WMT data preprocessing
- [x] BLEU evaluation script
- [x] Training curves and attention visualization
- [x] Translation examples
- [x] Reproducibility documentation
