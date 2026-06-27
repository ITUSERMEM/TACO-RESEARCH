# Research Review Request: Transformer Reproduction (Phase 2 方案设计)

## Project Overview
Full reproduction of "Attention Is All You Need" (Vaswani et al., 2017) in PyTorch. 
Target: WMT 2014 EN-DE (Base & Big) and EN-FR (Big) — BLEU 27.3 / 28.4 / 38.1.
Actual compute: 1× RTX 5090 (vs original 8× P100).
Scale-down: Multi30k + WMT14 small sample (vs full 4.5M pairs).

## Current Status
- Full Transformer implementation done (model.py: Encoder/Decoder, multi-head attention, positional encoding, label smoothing, beam search)
- Training pipeline complete (train.py, data.py, evaluate.py with BLEU computation)
- Experiment runner framework (experiment_runner.py with M0-M4 milestones)
- Config system (config.py with dataclass + argparse)
- **Only sanity check (M0) has been run** — tiny d_model=64, 2 layers, 2 epochs
- No WMT results yet. Environment is offline — data loading falls back to synthetic data.

## The User's Request (Phase 2 方案设计 — Methodologist Contribution)

The user is asking to review their Phase 2 design plan for the Transformer reproduction. The key aspects:

### 1. Reproduction Scope & Targets
- Core reproduce: WMT 2014 EN-DE (Base: BLEU 27.3, Big: BLEU 28.4) and EN-FR (Big: BLEU 38.1)
- Architecture: Full Transformer (d_model=512, h=8, N=6, d_ff=2048, dropout=0.1, label_smoothing=0.1)
- Training: Adam (β₁=0.9, β₂=0.98, ε=1e-9), warmup 4000 steps, sqrt decay schedule
- Compute: single RTX 5090, target ~2h training

### 2. Methodology Concerns
- Scale mismatch: original used 8× P100 for 12h on 4.5M pairs; this project uses 1× RTX 5090 on Multi30k (30k pairs)
- Data: falls back to **synthetic data** when HuggingFace datasets unavailable — this invalidates any BLEU comparison
- Only sanity check (tiny config) has been executed
- No Big model config defined
- No EN-FR data path at all

### 3. The Broader Context (P2-P5 Infrastructure)
This project is embedded in a larger autonomous research system (academic_loop.py + P2-P5 plan):
- P2: Meta-learning layer (review calibration, cross-project knowledge, analytics, skill versioning, trend monitoring)
- P3-P5: Long-running autonomy, cross-team collaboration, full autonomy
- These infrastructure modules and the Transformer reproduction seem to be in different directories with unclear relationship

## Key Questions for Reviewer

1. **Reproduction validity**: Is it meaningful to claim "reproducing Transformer" with synthetic data and 30k sentence pairs? What's the minimum data/scale to make this scientifically valid?

2. **Methodology gaps**: What are the critical missing pieces between current state (sanity check only) and a credible reproduction?

3. **Experiment design**: Are the M0-M4 milestones sufficient? What's missing?

4. **Architecture correctness**: Review model.py: any implementation bugs? (Pre-LN vs Post-LN? Label smoothing implementation? BLEU computation correctness?)

5. **Strategic advice**: Given compute constraints (1× RTX 5090, offline), what's the most impactful path forward?

## Files to Review

| File | Path | Purpose |
|------|------|---------|
| model.py | transformer-reproduce/model.py | Transformer model (Encoder/Decoder/MHA/FFN) |
| train.py | transformer-reproduce/train.py | Training loop, RateScheduler, LabelSmoothing |
| data.py | transformer-reproduce/data.py | Data loading (WMT → synthetic fallback) |
| evaluate.py | transformer-reproduce/evaluate.py | BLEU evaluation, translation examples |
| config.py | transformer-reproduce/config.py | Config dataclass & CLI parser |
| experiment_runner.py | transformer-reproduce/experiment_runner.py | M0-M4 milestone orchestration |
| IDEA_REPORT.md | transformer-reproduce/idea-stage/IDEA_REPORT.md | Original reproduction plan |
| EXPERIMENT_PLAN.md | transformer-reproduce/refine-logs/EXPERIMENT_PLAN.md | Experiment plan (M0-M4) |
| P2_P3_P4_P5_PLAN.md | redis-memory/P2_P3_P4_P5_PLAN.md | Broader infrastructure plan |
| P2_P5_REQUIREMENTS.md | redis-memory/P2_P5_REQUIREMENTS.md | P2-P5 requirements document |

## Specific Technical Concerns (for code review)

1. **Pre-LN vs Post-LN**: model.py uses Pre-LN (norm before attention/ffn). Original Transformer used Post-LN. This is a known architectural difference that affects training stability.

2. **Label smoothing**: train.py defines custom LabelSmoothing but also passes `label_smoothing=config.label_smoothing` to `nn.CrossEntropyLoss`. **Double smoothing** — this is almost certainly a bug.

3. **BLEU implementation**: Custom BLEU in evaluate.py — doesn't use sacrebleu. May not match original paper's BLEU computation.

4. **Data fallback**: `load_wmt_data()` silently falls back to synthetic random word sequences. Tests would pass but results are meaningless.

5. **No Big model config**: Experiment milestones only define "base" and "ablation_*". No "big" (d_model=1024, d_ff=4096, h=16) config.

6. **No EN-FR support**: Only EN-DE dataset_config="de-en". No FR path.

7. **GPU memory**: RTX 5090 has ~24GB VRAM. Big model may not fit at batch_size=128.

Please provide a thorough, brutally honest review.
