import math
import json
import os
from collections import Counter

import torch
import torch.nn.functional as F

from config import TransformerConfig
from model import Transformer
from data import create_dataloaders


def compute_bleu(candidate: str, reference: str, max_n: int = 4) -> float:
    cand_tokens = candidate.split()
    ref_tokens = reference.split()

    if len(cand_tokens) == 0 or len(ref_tokens) == 0:
        return 0.0

    precisions = []
    for n in range(1, max_n + 1):
        cand_ngrams = Counter(
            tuple(cand_tokens[i:i + n]) for i in range(len(cand_tokens) - n + 1)
        )
        ref_ngrams = Counter(
            tuple(ref_tokens[i:i + n]) for i in range(len(ref_tokens) - n + 1)
        )

        matches = sum(min(count, ref_ngrams.get(ngram, 0))
                      for ngram, count in cand_ngrams.items())
        total = max(sum(cand_ngrams.values()), 1)
        precisions.append(matches / total if total > 0 else 0.0)

    bp = min(1.0, math.exp(1 - len(ref_tokens) / max(len(cand_tokens), 1)))

    if any(p == 0 for p in precisions):
        return 0.0

    geo_mean = math.exp(sum(math.log(p) for p in precisions) / max_n)
    return bp * geo_mean * 100


def evaluate_bleu(model, dataloader, src_vocab, tgt_vocab, config, max_samples=500):
    model.eval()
    bleu_scores = []
    hypotheses = []
    references = []
    count = 0

    with torch.no_grad():
        for src, tgt in dataloader:
            if count >= max_samples:
                break
            src = src.to(config.device)

            if config.beam_size > 1:
                output = model.beam_search(
                    src, max_len=config.max_tgt_len, beam_size=config.beam_size,
                    bos_idx=config.bos_idx, eos_idx=config.eos_idx,
                    pad_idx=config.pad_idx,
                )
            else:
                output = model.greedy_decode(
                    src, max_len=config.max_tgt_len,
                    bos_idx=config.bos_idx, eos_idx=config.eos_idx
                )

            for i in range(src.size(0)):
                if count >= max_samples:
                    break
                hyp = tgt_vocab.decode(output[i])
                ref = tgt_vocab.decode(tgt[i])

                # Remove special tokens for BLEU
                hyp_clean = ' '.join(w for w in hyp.split()
                                     if w not in {'<bos>', '<eos>', '<pad>', '<unk>'})
                ref_clean = ' '.join(w for w in ref.split()
                                     if w not in {'<bos>', '<eos>', '<pad>', '<unk>'})

                bleu = compute_bleu(hyp_clean, ref_clean)
                bleu_scores.append(bleu)
                hypotheses.append(hyp_clean)
                references.append(ref_clean)
                count += 1

    avg_bleu = sum(bleu_scores) / len(bleu_scores) if bleu_scores else 0.0
    return avg_bleu, bleu_scores, hypotheses, references


def show_translation_examples(model, dataloader, src_vocab, tgt_vocab, config, num_examples=5):
    model.eval()
    examples = []

    with torch.no_grad():
        for src, tgt in dataloader:
            src = src.to(config.device)
            if config.beam_size > 1:
                output = model.beam_search(
                    src, max_len=config.max_tgt_len, beam_size=config.beam_size,
                    bos_idx=config.bos_idx, eos_idx=config.eos_idx,
                    pad_idx=config.pad_idx,
                )
            else:
                output = model.greedy_decode(
                    src, max_len=config.max_tgt_len,
                    bos_idx=config.bos_idx, eos_idx=config.eos_idx
                )

            for i in range(min(num_examples, src.size(0))):
                src_text = src_vocab.decode(src[i])
                src_clean = ' '.join(w for w in src_text.split()
                                     if w not in {'<bos>', '<eos>', '<pad>', '<unk>'})
                ref_text = tgt_vocab.decode(tgt[i])
                ref_clean = ' '.join(w for w in ref_text.split()
                                     if w not in {'<bos>', '<eos>', '<pad>', '<unk>'})
                hyp_text = tgt_vocab.decode(output[i])
                hyp_clean = ' '.join(w for w in hyp_text.split()
                                     if w not in {'<bos>', '<eos>', '<pad>', '<unk>'})

                examples.append({
                    'source': src_clean,
                    'reference': ref_clean,
                    'hypothesis': hyp_clean,
                })

            break

    return examples


def main(config=None):
    if config is None:
        config = TransformerConfig()
    config.batch_size = 64

    print("Loading data...")
    train_loader, val_loader, test_loader, src_vocab, tgt_vocab = create_dataloaders(config)
    config.src_vocab_size = len(src_vocab)
    config.tgt_vocab_size = len(tgt_vocab)

    checkpoint_path = os.path.join(config.checkpoint_dir, 'best_model.pt')
    if not os.path.exists(checkpoint_path):
        print(f"Checkpoint not found at {checkpoint_path}")
        return

    print(f"Loading checkpoint from {checkpoint_path}...")
    checkpoint = torch.load(checkpoint_path, map_location=config.device)
    model = Transformer(config).to(config.device)
    model.load_state_dict(checkpoint['model_state_dict'])
    print(f"Loaded epoch {checkpoint['epoch']} (val_loss: {checkpoint['val_loss']:.4f})")

    print("\nComputing BLEU on test set...")
    avg_bleu, bleu_scores, hyps, refs = evaluate_bleu(model, test_loader, src_vocab, tgt_vocab, config)

    print(f"\n{'='*50}")
    print(f"Test BLEU Score: {avg_bleu:.2f}")
    print(f"Number of samples: {len(bleu_scores)}")
    print(f"{'='*50}")

    print("\nTranslation Examples:")
    print("-" * 50)
    examples = show_translation_examples(model, val_loader, src_vocab, tgt_vocab, config)
    for i, ex in enumerate(examples):
        print(f"\n  Example {i + 1}:")
        print(f"    Source:      {ex['source']}")
        print(f"    Reference:   {ex['reference']}")
        print(f"    Hypothesis:  {ex['hypothesis']}")

    results = {
        'bleu_score': avg_bleu,
        'num_samples': len(bleu_scores),
        'bleu_scores': bleu_scores[:20],
        'examples': examples,
    }
    with open(os.path.join(config.checkpoint_dir, 'evaluation_results.json'), 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {config.checkpoint_dir}/evaluation_results.json")


if __name__ == '__main__':
    main()
