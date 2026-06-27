#!/usr/bin/env python3
"""
Transformer Reproduction Experiment Runner.
Orchestrates the full experiment plan (M0-M4) with configurable milestones.
"""

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import torch

from config import TransformerConfig, build_parser, save_config


MILESTONES = {
    'sanity': {
        'd_model': 64, 'num_encoder_layers': 2, 'num_decoder_layers': 2,
        'num_epochs': 2, 'batch_size': 32, 'label_smoothing': 0.1,
        'warmup_steps': 400, 'max_seq_len': 64,
        'max_src_len': 64, 'max_tgt_len': 64,
    },
    'base': {
        'd_model': 512, 'num_encoder_layers': 6, 'num_decoder_layers': 6,
        'num_epochs': 10, 'batch_size': 128, 'label_smoothing': 0.1,
        'warmup_steps': 4000, 'num_heads': 8, 'd_ff': 2048,
    },
    'ablation_ls': {
        'd_model': 512, 'num_encoder_layers': 6, 'num_decoder_layers': 6,
        'num_epochs': 10, 'batch_size': 128, 'warmup_steps': 4000,
    },
    'ablation_warmup': {
        'd_model': 512, 'num_encoder_layers': 6, 'num_decoder_layers': 6,
        'num_epochs': 10, 'batch_size': 128, 'label_smoothing': 0.1,
    },
    'ablation_beam': {
        'd_model': 512, 'num_encoder_layers': 6, 'num_decoder_layers': 6,
        'num_epochs': 10, 'batch_size': 128, 'label_smoothing': 0.1,
        'warmup_steps': 4000, 'num_heads': 8, 'd_ff': 2048,
    },
}


def seed_everything(seed: int):
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def get_gpu_info():
    if not torch.cuda.is_available():
        return {'available': False, 'name': 'N/A', 'memory_gb': 0}
    name = torch.cuda.get_device_name(0)
    free, total = torch.cuda.mem_get_info(0)
    return {
        'available': True,
        'name': name,
        'total_memory_gb': round(total / 1024**3, 1),
        'free_memory_gb': round(free / 1024**3, 1),
    }


def run_experiment(args):
    """Run a single experiment: train + evaluate, save results."""
    cfg, overrides = TransformerConfig.from_args(args)

    seed_everything(cfg.seed)
    device = torch.device(cfg.device if torch.cuda.is_available() else 'cpu')
    cfg.device = str(device)

    print(f"\n{'='*60}")
    print(f"  Experiment: {args.run_id or 'unnamed'}")
    print(f"  Seed: {cfg.seed}, Device: {device}")
    print(f"  Config: d_model={cfg.d_model}, layers={cfg.num_encoder_layers}, "
          f"epochs={cfg.num_epochs}, batch={cfg.batch_size}")
    print(f"{'='*60}")

    from train import main as train_main
    from evaluate import main as eval_main

    start_time = time.time()
    model, src_vocab, tgt_vocab, train_results = train_main(config=cfg)
    train_time = time.time() - start_time

    eval_config_path = os.path.join(cfg.checkpoint_dir, 'eval_config.json')
    save_config(cfg, eval_config_path)

    eval_main(config=cfg)

    results_path = os.path.join(cfg.checkpoint_dir, 'evaluation_results.json')
    if os.path.exists(results_path):
        with open(results_path) as f:
            eval_results = json.load(f)
    else:
        eval_results = {'bleu_score': 0, 'error': 'evaluation did not produce results'}

    summary = {
        'run_id': args.run_id or 'unknown',
        'seed': cfg.seed,
        'config': {k: getattr(cfg, k) for k in dir(cfg) if not k.startswith('_')},
        'train_time_seconds': train_time,
        'best_val_loss': train_results.get('best_val_loss', -1),
        'best_val_ppl': train_results.get('best_val_ppl', -1),
        'model_params': train_results.get('model_params', 0),
        'bleu_score': eval_results.get('bleu_score', 0),
        'bleu_samples': eval_results.get('num_samples', 0),
        'gpu_info': get_gpu_info(),
    }

    os.makedirs('results', exist_ok=True)
    summary_path = f"results/{args.run_id}.json" if args.run_id else \
        f"results/experiment_seed{cfg.seed}.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"  Results saved to {summary_path}")
    print(f"  BLEU: {summary['bleu_score']:.2f}, "
          f"Val Loss: {summary['best_val_loss']:.4f}, "
          f"PPL: {summary['best_val_ppl']:.2f}")
    print(f"  Train time: {train_time:.0f}s ({train_time/60:.1f}min)")
    print(f"  GPU: {summary['gpu_info']['name']} "
          f"({summary['gpu_info']['free_memory_gb']}GB free)")
    print(f"{'='*60}")

    return summary


def list_experiments():
    """List all saved experiment results."""
    results_dir = Path('results')
    if not results_dir.exists():
        print("No results found.")
        return

    files = sorted(results_dir.glob('*.json'))
    if not files:
        print("No results found.")
        return

    print(f"\n{'='*70}")
    print(f"  Completed Experiments ({len(files)} total)")
    print(f"{'='*70}")
    print(f"  {'Run ID':<20} {'BLEU':<8} {'Loss':<8} {'PPL':<8} {'Params':<10}")
    print(f"  {'-'*54}")
    for f in files:
        with open(f) as fh:
            data = json.load(fh)
        print(f"  {data.get('run_id', '?'):<20} "
              f"{data.get('bleu_score', 0):<8.2f} "
              f"{data.get('best_val_loss', 0):<8.4f} "
              f"{data.get('best_val_ppl', 0):<8.2f} "
              f"{data.get('model_params', 0):<10,}")


def run_milestone(name: str, extra_args: list = None):
    """Run a predefined milestone."""
    if name not in MILESTONES:
        print(f"Unknown milestone: {name}")
        print(f"Available: {list(MILESTONES.keys())}")
        return

    milestone_args = MILESTONES[name]
    arg_list = []
    for k, v in milestone_args.items():
        arg_list.append(f'--{k.replace("_", "-")}')
        arg_list.append(str(v))

    if extra_args:
        arg_list.extend(extra_args)

    print(f"\n{'#'*60}")
    print(f"  Running milestone: {name}")
    print(f"  Args: {' '.join(arg_list)}")
    print(f"{'#'*60}")

    parser = build_parser()
    parsed = parser.parse_args(arg_list)
    return run_experiment(parsed)


def main():
    parser = argparse.ArgumentParser(description='Transformer Experiment Runner')
    subparsers = parser.add_subparsers(dest='command', help='Command')

    run_parser = subparsers.add_parser('run', help='Run a single experiment', add_help=False)
    for action in build_parser()._actions:
        if action.option_strings and '--help' not in action.option_strings:
            run_parser.add_argument(*action.option_strings, **{
                k: v for k, v in vars(action).items()
                if k in ('type', 'default', 'help', 'action', 'dest')
                and v is not None
            })

    milestone_parser = subparsers.add_parser('milestone', help='Run a predefined milestone')
    milestone_parser.add_argument('name', type=str, choices=list(MILESTONES.keys()),
                                  help='Milestone name')
    milestone_parser.add_argument('--seeds', type=int, nargs='+', default=[42],
                                  help='Random seeds')
    milestone_parser.add_argument('--extra', type=str, nargs='*', default=[],
                                  help='Extra CLI args')

    list_parser = subparsers.add_parser('list', help='List completed experiments')

    subparsers.add_parser('all', help='Run the full experiment plan (M0→M4)')

    args = parser.parse_args()

    if args.command == 'run':
        run_experiment(args)
    elif args.command == 'milestone':
        for seed in args.seeds:
            extra = list(args.extra) + ['--seed', str(seed),
                                        '--run-id', f"{args.name}_seed{seed}"]
            run_milestone(args.name, extra)
    elif args.command == 'list':
        list_experiments()
    elif args.command == 'all':
        run_full_plan()
    else:
        parser.print_help()


def run_full_plan():
    """Run the complete experiment plan: M0 → M1 → M2 → M3 → M4."""
    total_start = time.time()
    all_results = []

    parser = build_parser()

    # M0: Sanity Check
    print("\n" + "★" * 60)
    print("  MILESTONE 0: SANITY CHECK")
    print("★" * 60)
    sanity_args = MILESTONES['sanity'].copy()
    sanity_args['run_id'] = 'M0_sanity'
    sanity_args['seed'] = 42
    arg_list = []
    for k, v in sanity_args.items():
        arg_list.append(f'--{k.replace("_", "-")}')
        arg_list.append(str(v))
    parsed = parser.parse_args(arg_list)
    result = run_experiment(parsed)
    all_results.append(result)

    if result.get('bleu_score', 0) <= 0:
        print("\n⚠️  Sanity check BLEU is 0 — but that's expected for random init on tiny data.")
        print("   Check: loss decreased and no NaN → proceed to M1.")
    else:
        print(f"\n  Sanity BLEU: {result['bleu_score']:.2f}")

    # M1: Base Model (3 seeds)
    print("\n" + "★" * 60)
    print("  MILESTONE 1: BASE MODEL CONVERGENCE (3 seeds)")
    print("★" * 60)
    for seed in [42, 43, 44]:
        m1_args = MILESTONES['base'].copy()
        m1_args['run_id'] = f'M1_base_seed{seed}'
        m1_args['seed'] = seed
        arg_list = []
        for k, v in m1_args.items():
            arg_list.append(f'--{k.replace("_", "-")}')
            arg_list.append(str(v))
        parsed = parser.parse_args(arg_list)
        result = run_experiment(parsed)
        all_results.append(result)

    # M2: Label Smoothing Ablation
    print("\n" + "★" * 60)
    print("  MILESTONE 2: ABLATION — LABEL SMOOTHING")
    print("★" * 60)
    for ls in [0.0, 0.1]:
        m2_args = MILESTONES['ablation_ls'].copy()
        m2_args['label_smoothing'] = ls
        m2_args['run_id'] = f'M2_ls_{ls}_seed42'
        m2_args['seed'] = 42
        arg_list = []
        for k, v in m2_args.items():
            arg_list.append(f'--{k.replace("_", "-")}')
            arg_list.append(str(v))
        parsed = parser.parse_args(arg_list)
        result = run_experiment(parsed)
        all_results.append(result)

    # M3: Warmup Steps Ablation
    print("\n" + "★" * 60)
    print("  MILESTONE 3: ABLATION — WARMUP STEPS")
    print("★" * 60)
    for ws in [2000, 8000]:
        m3_args = MILESTONES['ablation_warmup'].copy()
        m3_args['warmup_steps'] = ws
        m3_args['run_id'] = f'M3_warmup_{ws}_seed42'
        m3_args['seed'] = 42
        arg_list = []
        for k, v in m3_args.items():
            arg_list.append(f'--{k.replace("_", "-")}')
            arg_list.append(str(v))
        parsed = parser.parse_args(arg_list)
        result = run_experiment(parsed)
        all_results.append(result)

    # M4: Beam Search Ablation
    print("\n" + "★" * 60)
    print("  MILESTONE 4: ABLATION — BEAM SEARCH vs GREEDY")
    print("★" * 60)
    for beam_size in [2, 4, 8]:
        m4_args = MILESTONES['ablation_beam'].copy()
        m4_args['run_id'] = f'M4_beam_{beam_size}_seed42'
        m4_args['seed'] = 42
        arg_list = []
        for k, v in m4_args.items():
            arg_list.append(f'--{k.replace("_", "-")}')
            arg_list.append(str(v))
        arg_list.extend(['--beam-size', str(beam_size)])
        parsed = parser.parse_args(arg_list)
        result = run_experiment(parsed)
        all_results.append(result)

    total_time = time.time() - total_start

    # Generate summary report
    print("\n" + "=" * 70)
    print("  EXPERIMENT PLAN COMPLETE")
    print("=" * 70)
    print(f"  Total time: {total_time:.0f}s ({total_time/60:.1f}min)")
    print(f"\n  {'Run':<22} {'BLEU':<8} {'Val Loss':<10} {'PPL':<8}")
    print(f"  {'-'*48}")
    for r in all_results:
        print(f"  {r.get('run_id', '?'):<22} "
              f"{r.get('bleu_score', 0):<8.2f} "
              f"{r.get('best_val_loss', 0):<10.4f} "
              f"{r.get('best_val_ppl', 0):<8.2f}")

    summary = {
        'total_time_seconds': total_time,
        'num_experiments': len(all_results),
        'results': all_results,
        'gpu': get_gpu_info(),
    }
    with open('results/full_plan_summary.json', 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n  Full summary saved to results/full_plan_summary.json")


if __name__ == '__main__':
    main()
