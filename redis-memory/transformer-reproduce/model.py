import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2, dtype=torch.float) *
                             (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        self.register_buffer('pe', pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)


class MultiHeadAttention(nn.Module):
    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % num_heads == 0
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads

        self.W_q = nn.Linear(d_model, d_model, bias=False)
        self.W_k = nn.Linear(d_model, d_model, bias=False)
        self.W_v = nn.Linear(d_model, d_model, bias=False)
        self.W_o = nn.Linear(d_model, d_model, bias=False)
        self.dropout = nn.Dropout(dropout)

    def forward(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor,
                mask: torch.Tensor = None) -> torch.Tensor:
        batch_size = query.size(0)

        Q = self.W_q(query).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        K = self.W_k(key).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        V = self.W_v(value).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)

        attn_scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.d_k)

        if mask is not None:
            attn_scores = attn_scores.masked_fill(mask == 0, float('-inf'))

        attn_weights = F.softmax(attn_scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        output = torch.matmul(attn_weights, V)
        output = output.transpose(1, 2).contiguous().view(batch_size, -1, self.d_model)
        output = self.W_o(output)
        return output


class PositionwiseFFN(nn.Module):
    def __init__(self, d_model: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.w_1 = nn.Linear(d_model, d_ff)
        self.w_2 = nn.Linear(d_ff, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.w_2(self.dropout(F.relu(self.w_1(x))))


class EncoderLayer(nn.Module):
    def __init__(self, d_model: int, num_heads: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.self_attn = MultiHeadAttention(d_model, num_heads, dropout)
        self.ffn = PositionwiseFFN(d_model, d_ff, dropout)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
        x = x + self.dropout1(self.self_attn(self.norm1(x), self.norm1(x), self.norm1(x), mask))
        x = x + self.dropout2(self.ffn(self.norm2(x)))
        return x


class DecoderLayer(nn.Module):
    def __init__(self, d_model: int, num_heads: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.self_attn = MultiHeadAttention(d_model, num_heads, dropout)
        self.cross_attn = MultiHeadAttention(d_model, num_heads, dropout)
        self.ffn = PositionwiseFFN(d_model, d_ff, dropout)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.norm3 = nn.LayerNorm(d_model)
        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)
        self.dropout3 = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, encoder_output: torch.Tensor,
                src_mask: torch.Tensor = None, tgt_mask: torch.Tensor = None) -> torch.Tensor:
        x = x + self.dropout1(self.self_attn(self.norm1(x), self.norm1(x), self.norm1(x), tgt_mask))
        x = x + self.dropout2(self.cross_attn(self.norm2(x), self.norm2(encoder_output),
                                              self.norm2(encoder_output), src_mask))
        x = x + self.dropout3(self.ffn(self.norm3(x)))
        return x


class Encoder(nn.Module):
    def __init__(self, vocab_size: int, d_model: int, num_layers: int,
                 num_heads: int, d_ff: int, max_len: int, dropout: float = 0.1):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.pos_encoding = PositionalEncoding(d_model, max_len, dropout)
        self.layers = nn.ModuleList([
            EncoderLayer(d_model, num_heads, d_ff, dropout)
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(d_model)

    def forward(self, x: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
        x = self.embedding(x) * math.sqrt(self.embedding.embedding_dim)
        x = self.pos_encoding(x)
        for layer in self.layers:
            x = layer(x, mask)
        return self.norm(x)


class Decoder(nn.Module):
    def __init__(self, vocab_size: int, d_model: int, num_layers: int,
                 num_heads: int, d_ff: int, max_len: int, dropout: float = 0.1):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.pos_encoding = PositionalEncoding(d_model, max_len, dropout)
        self.layers = nn.ModuleList([
            DecoderLayer(d_model, num_heads, d_ff, dropout)
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(d_model)
        self.output_proj = nn.Linear(d_model, vocab_size)

    def forward(self, x: torch.Tensor, encoder_output: torch.Tensor,
                src_mask: torch.Tensor = None, tgt_mask: torch.Tensor = None) -> torch.Tensor:
        x = self.embedding(x) * math.sqrt(self.embedding.embedding_dim)
        x = self.pos_encoding(x)
        for layer in self.layers:
            x = layer(x, encoder_output, src_mask, tgt_mask)
        x = self.norm(x)
        return self.output_proj(x)


class Transformer(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.encoder = Encoder(
            vocab_size=config.src_vocab_size,
            d_model=config.d_model,
            num_layers=config.num_encoder_layers,
            num_heads=config.num_heads,
            d_ff=config.d_ff,
            max_len=config.max_seq_len,
            dropout=config.dropout,
        )
        self.decoder = Decoder(
            vocab_size=config.tgt_vocab_size,
            d_model=config.d_model,
            num_layers=config.num_decoder_layers,
            num_heads=config.num_heads,
            d_ff=config.d_ff,
            max_len=config.max_seq_len,
            dropout=config.dropout,
        )

        if config.share_embedding and config.src_vocab_size == config.tgt_vocab_size:
            self.encoder.embedding.weight = self.decoder.embedding.weight

        self._init_parameters()

    def _init_parameters(self):
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)

    def make_src_mask(self, src: torch.Tensor, pad_idx: int) -> torch.Tensor:
        return (src != pad_idx).unsqueeze(1).unsqueeze(2)

    def make_tgt_mask(self, tgt: torch.Tensor, pad_idx: int) -> torch.Tensor:
        pad_mask = (tgt != pad_idx).unsqueeze(1).unsqueeze(2)
        seq_len = tgt.size(1)
        causal_mask = torch.tril(torch.ones(seq_len, seq_len, device=tgt.device)).bool()
        causal_mask = causal_mask.unsqueeze(0).unsqueeze(0)
        return pad_mask & causal_mask

    def forward(self, src: torch.Tensor, tgt: torch.Tensor) -> torch.Tensor:
        src_mask = self.make_src_mask(src, 0)
        tgt_mask = self.make_tgt_mask(tgt, 0)
        encoder_output = self.encoder(src, src_mask)
        return self.decoder(tgt, encoder_output, src_mask, tgt_mask)

    @torch.no_grad()
    def greedy_decode(self, src: torch.Tensor, max_len: int, bos_idx: int, eos_idx: int):
        self.eval()
        src_mask = self.make_src_mask(src, 0)
        encoder_output = self.encoder(src, src_mask)

        batch_size = src.size(0)
        tgt = torch.full((batch_size, 1), bos_idx, dtype=torch.long, device=src.device)

        for _ in range(max_len):
            tgt_mask = self.make_tgt_mask(tgt, 0)
            logits = self.decoder(tgt, encoder_output, src_mask, tgt_mask)
            next_token = logits[:, -1, :].argmax(dim=-1, keepdim=True)
            tgt = torch.cat([tgt, next_token], dim=1)
            if (next_token == eos_idx).all():
                break

        return tgt

    @torch.no_grad()
    def beam_search(self, src: torch.Tensor, max_len: int, beam_size: int,
                    bos_idx: int, eos_idx: int, pad_idx: int):
        self.eval()
        src_mask = self.make_src_mask(src, pad_idx)
        encoder_output = self.encoder(src, src_mask)
        batch_size = src.size(0)

        all_sequences = []

        for i in range(batch_size):
            enc_out = encoder_output[i:i + 1]
            src_msk = src_mask[i:i + 1]

            sequences = [[bos_idx]]
            scores = [0.0]

            for _ in range(max_len):
                candidates = []
                for seq, score in zip(sequences, scores):
                    if seq[-1] == eos_idx:
                        candidates.append((seq, score))
                        continue

                    tgt_tensor = torch.tensor([seq], dtype=torch.long, device=src.device)
                    tgt_mask = self.make_tgt_mask(tgt_tensor, pad_idx)
                    logits = self.decoder(tgt_tensor, enc_out, src_msk, tgt_mask)
                    log_probs = F.log_softmax(logits[:, -1, :], dim=-1)

                    topk_scores, topk_tokens = log_probs.topk(beam_size, dim=-1)

                    for k in range(beam_size):
                        new_seq = seq + [topk_tokens[0, k].item()]
                        new_score = score + topk_scores[0, k].item()
                        candidates.append((new_seq, new_score))

                candidates.sort(key=lambda x: x[1], reverse=True)
                sequences = [c[0] for c in candidates[:beam_size]]
                scores = [c[1] for c in candidates[:beam_size]]

            best_seq = sequences[0]
            if eos_idx in best_seq:
                best_seq = best_seq[:best_seq.index(eos_idx) + 1]
            all_sequences.append(best_seq)

        max_seq_len = max(len(s) for s in all_sequences)
        result = torch.full((batch_size, max_seq_len), pad_idx, dtype=torch.long, device=src.device)
        for i, seq in enumerate(all_sequences):
            result[i, :len(seq)] = torch.tensor(seq, dtype=torch.long, device=src.device)

        return result


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
