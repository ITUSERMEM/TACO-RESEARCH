import argparse
import json
import os
from dataclasses import dataclass, field, fields
from typing import Optional


TYPE_MAP = {
    int: int,
    float: float,
    str: str,
    bool: lambda x: x.lower() in ('true', '1', 'yes'),
}


@dataclass
class TransformerConfig:
    # Model architecture
    d_model: int = 512
    d_ff: int = 2048
    num_heads: int = 8
    num_encoder_layers: int = 6
    num_decoder_layers: int = 6
    dropout: float = 0.1
    max_seq_len: int = 128

    # Vocabulary
    src_vocab_size: int = 10000
    tgt_vocab_size: int = 10000
    share_embedding: bool = True

    # Training
    batch_size: int = 128
    num_epochs: int = 40
    label_smoothing: float = 0.1
    warmup_steps: int = 4000
    lr_scale: float = 1.0
    beta1: float = 0.9
    beta2: float = 0.98
    eps: float = 1e-9
    clip_grad_norm: float = 5.0
    accumulation_steps: int = 1

    # Data
    dataset_name: str = "wmt14"
    dataset_config: str = "de-en"
    max_src_len: int = 128
    max_tgt_len: int = 128
    min_freq: int = 2

    # Evaluation
    eval_every: int = 500
    save_every: int = 2000
    bleu_max_n: int = 4
    beam_size: int = 1

    # Paths
    data_dir: str = "data"
    checkpoint_dir: str = "checkpoints"
    log_dir: str = "logs"
    device: str = "cuda"
    seed: int = 42

    # Special tokens
    pad_idx: int = 0
    bos_idx: int = 1
    eos_idx: int = 2
    unk_idx: int = 3

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> 'TransformerConfig':
        overrides = {}
        for f in fields(cls):
            key = f.name.replace('_', '-')
            val = getattr(args, key, None)
            if val is not None:
                converter = TYPE_MAP.get(f.type, str)
                overrides[f.name] = converter(val) if converter != bool else val
        cfg = cls(**overrides)

        if args.run_id:
            cfg.checkpoint_dir = os.path.join('checkpoints', args.run_id)
            cfg.log_dir = os.path.join('logs', args.run_id)

        return cfg, overrides


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Transformer Reproduction')
    parser.add_argument('--run-id', type=str, default=None, help='Run ID for output dirs')

    for f in fields(TransformerConfig):
        flag = '--' + f.name.replace('_', '-')
        kwargs = dict(default=None, help=f'{f.name} (default: {f.default})')
        if f.type == bool:
            kwargs['action'] = 'store_true'
            del kwargs['default']
            kwargs['help'] = f'enable {f.name}'
        parser.add_argument(flag, **kwargs)

    parser.add_argument('--sanity', action='store_true', help='Run sanity mode')
    parser.add_argument('--evaluate-only', action='store_true', help='Skip training, evaluate only')
    return parser


def save_config(cfg: TransformerConfig, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump({f.name: getattr(cfg, f.name) for f in fields(cfg)}, f, indent=2)
