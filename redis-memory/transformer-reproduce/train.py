import os
import sys
import math
import time
import json
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter

from config import TransformerConfig
from model import Transformer, count_parameters
from data import create_dataloaders


class LabelSmoothing(nn.Module):
    def __init__(self, smoothing: float, pad_idx: int):
        super().__init__()
        self.smoothing = smoothing
        self.pad_idx = pad_idx

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        vocab_size = pred.size(-1)
        confidence = 1.0 - self.smoothing
        smooth_target = pred.new_zeros(pred.size())
        smooth_target.fill_(self.smoothing / (vocab_size - 2))
        smooth_target.scatter_(-1, target.unsqueeze(-1), confidence)
        smooth_target[:, :, self.pad_idx] = 0

        mask = (target != self.pad_idx).unsqueeze(-1)
        smooth_target = smooth_target * mask.float()

        return -torch.sum(smooth_target * F.log_softmax(pred, dim=-1), dim=-1).mean()


class RateScheduler:
    def __init__(self, d_model: int, warmup_steps: int, scale: float = 1.0):
        self.d_model = d_model
        self.warmup_steps = warmup_steps
        self.scale = scale
        self.step_num = 0

    def step(self):
        self.step_num += 1
        return self.get_lr()

    def get_lr(self):
        arg1 = self.step_num ** (-0.5)
        arg2 = self.step_num * (self.warmup_steps ** (-1.5))
        return self.scale * (self.d_model ** (-0.5)) * min(arg1, arg2)


def train_epoch(model, dataloader, optimizer, criterion, scheduler, config, writer, epoch):
    model.train()
    total_loss = 0
    total_tokens = 0
    start_time = time.time()
    batch_count = len(dataloader)

    for batch_idx, (src, tgt) in enumerate(dataloader):
        global_step = epoch * batch_count + batch_idx
        src, tgt = src.to(config.device), tgt.to(config.device)
        tgt_input = tgt[:, :-1]
        tgt_output = tgt[:, 1:]

        lr = scheduler.step()
        for param_group in optimizer.param_groups:
            param_group['lr'] = lr

        logits = model(src, tgt_input)
        loss = criterion(logits.reshape(-1, logits.size(-1)), tgt_output.reshape(-1))

        loss.backward()
        if config.clip_grad_norm > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.clip_grad_norm)
        optimizer.step()
        optimizer.zero_grad()

        total_loss += loss.item()
        num_tokens = (tgt_output != config.pad_idx).sum().item()
        total_tokens += num_tokens

        if batch_idx % 100 == 0:
            elapsed = time.time() - start_time
            tokens_per_sec = total_tokens / elapsed if elapsed > 0 else 0
            avg_loss = total_loss / (batch_idx + 1)
            writer.add_scalar('Loss/train', loss.item(), global_step)
            writer.add_scalar('LR', lr, global_step)
            writer.add_scalar('Speed/tokens_per_sec', tokens_per_sec, global_step)
            writer.add_scalar('Perplexity/train', math.exp(min(avg_loss, 10)), global_step)

            print(f"  [Epoch {epoch}, Batch {batch_idx}/{batch_count}] "
                  f"Loss: {loss.item():.4f}, PPL: {math.exp(min(loss.item(), 10)):.2f}, "
                  f"LR: {lr:.6e}, Speed: {tokens_per_sec:.0f} tok/s")

        if global_step > 0 and global_step % config.eval_every == 0:
            val_loss = evaluate(model, dataloader, criterion, config)
            writer.add_scalar('Loss/val', val_loss, global_step)
            writer.add_scalar('Perplexity/val', math.exp(min(val_loss, 10)), global_step)
            print(f"  📊 Validation Loss: {val_loss:.4f}, PPL: {math.exp(min(val_loss, 10)):.2f}")
            model.train()

    return total_loss / batch_count


def evaluate(model, dataloader, criterion, config):
    model.eval()
    total_loss = 0
    total_tokens = 0

    with torch.no_grad():
        for src, tgt in dataloader:
            src, tgt = src.to(config.device), tgt.to(config.device)
            tgt_input = tgt[:, :-1]
            tgt_output = tgt[:, 1:]

            logits = model(src, tgt_input)
            loss = criterion(logits.reshape(-1, logits.size(-1)), tgt_output.reshape(-1))

            total_loss += loss.item()
            total_tokens += (tgt_output != config.pad_idx).sum().item()

    return total_loss / len(dataloader)


def main(config=None):
    if config is None:
        config = TransformerConfig()
    os.makedirs(config.checkpoint_dir, exist_ok=True)
    os.makedirs(config.log_dir, exist_ok=True)
    writer = SummaryWriter(config.log_dir)

    torch.manual_seed(config.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(config.seed)

    print("=" * 60)
    print("Loading data...")
    train_loader, val_loader, test_loader, src_vocab, tgt_vocab = create_dataloaders(config)

    config.src_vocab_size = len(src_vocab)
    config.tgt_vocab_size = len(tgt_vocab)
    print(f"Source vocab size: {config.src_vocab_size}")
    print(f"Target vocab size: {config.tgt_vocab_size}")

    print("\nBuilding model...")
    model = Transformer(config).to(config.device)
    print(f"Model parameters: {count_parameters(model):,}")

    criterion = nn.CrossEntropyLoss(ignore_index=config.pad_idx, label_smoothing=config.label_smoothing)
    optimizer = optim.Adam(model.parameters(), lr=0, betas=(config.beta1, config.beta2), eps=config.eps)
    scheduler = RateScheduler(config.d_model, config.warmup_steps, config.lr_scale)

    print("\nStarting training...")
    print(f"  Batch size: {config.batch_size}")
    print(f"  Max epochs: {config.num_epochs}")
    print(f"  Warmup steps: {config.warmup_steps}")
    print(f"  Label smoothing: {config.label_smoothing}")
    print(f"  Device: {config.device}")
    print("=" * 60)

    best_val_loss = float('inf')
    start_time = time.time()

    for epoch in range(1, config.num_epochs + 1):
        epoch_start = time.time()
        print(f"\n{'='*40}")
        print(f"Epoch {epoch}/{config.num_epochs}")
        print(f"{'='*40}")

        train_loss = train_epoch(model, train_loader, optimizer, criterion, scheduler, config, writer, epoch)
        val_loss = evaluate(model, val_loader, criterion, config)

        epoch_time = time.time() - epoch_start
        writer.add_scalar('Loss/train_epoch', train_loss, epoch)
        writer.add_scalar('Loss/val_epoch', val_loss, epoch)
        writer.add_scalar('Perplexity/val_epoch', math.exp(min(val_loss, 10)), epoch)

        print(f"\n  Epoch {epoch} completed in {epoch_time:.0f}s")
        print(f"  Train Loss: {train_loss:.4f}, PPL: {math.exp(min(train_loss, 10)):.2f}")
        print(f"  Val Loss: {val_loss:.4f}, PPL: {math.exp(min(val_loss, 10)):.2f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            checkpoint = {
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'config': config,
                'val_loss': val_loss,
            }
            torch.save(checkpoint, os.path.join(config.checkpoint_dir, 'best_model.pt'))
            print(f"  ✅ New best model saved (val_loss: {val_loss:.4f})")

        if epoch % 10 == 0:
            torch.save(checkpoint, os.path.join(config.checkpoint_dir, f'checkpoint_epoch_{epoch}.pt'))

    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"Training complete! Total time: {total_time:.0f}s ({total_time/60:.1f}min)")
    print(f"Best val loss: {best_val_loss:.4f}")
    print(f"Best val PPL: {math.exp(min(best_val_loss, 10)):.2f}")

    writer.close()

    results = {
        'best_val_loss': best_val_loss,
        'best_val_ppl': math.exp(min(best_val_loss, 10)),
        'total_time': total_time,
        'model_params': count_parameters(model),
    }
    with open(os.path.join(config.checkpoint_dir, 'training_results.json'), 'w') as f:
        json.dump(results, f, indent=2)

    return model, src_vocab, tgt_vocab, results


if __name__ == '__main__':
    import torch.nn.functional as F
    main()
