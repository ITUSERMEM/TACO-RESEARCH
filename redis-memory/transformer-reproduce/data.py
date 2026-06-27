import os
import random
from collections import Counter

import torch
from torch.utils.data import Dataset, DataLoader


class Vocab:
    def __init__(self, max_size: int = 10000, min_freq: int = 2):
        self.max_size = max_size
        self.min_freq = min_freq
        self.stoi = {'<pad>': 0, '<bos>': 1, '<eos>': 2, '<unk>': 3}
        self.itos = ['<pad>', '<bos>', '<eos>', '<unk>']

    def build(self, sentences):
        counter = Counter()
        for sent in sentences:
            counter.update(sent.split())

        most_common = counter.most_common(self.max_size - 4)
        for word, freq in most_common:
            if freq >= self.min_freq:
                self.itos.append(word)
                self.stoi[word] = len(self.itos) - 1

    def __len__(self):
        return len(self.itos)

    def encode(self, sentence: str, max_len: int) -> torch.Tensor:
        tokens = [self.stoi.get(w, self.stoi['<unk>']) for w in sentence.split()]
        tokens = [self.stoi['<bos>']] + tokens[:max_len - 2] + [self.stoi['<eos>']]
        tokens = tokens + [self.stoi['<pad>']] * (max_len - len(tokens))
        return torch.tensor(tokens, dtype=torch.long)

    def decode(self, tokens: torch.Tensor) -> str:
        return ' '.join(self.itos[t] for t in tokens if t not in {0, 1, 2})


WORDS = [
    'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
    'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
    'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
    'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what',
    'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go', 'me',
    'when', 'make', 'can', 'like', 'time', 'no', 'just', 'him', 'know', 'take',
    'people', 'into', 'year', 'your', 'good', 'some', 'could', 'them', 'see', 'other',
    'than', 'then', 'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also',
    'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first', 'well', 'way',
    'even', 'new', 'want', 'because', 'any', 'these', 'give', 'day', 'most', 'us',
    'groß', 'und', 'die', 'der', 'das', 'ist', 'nicht', 'ein', 'eine', 'sich',
    'auch', 'auf', 'für', 'mit', 'im', 'den', 'dem', 'des', 'an', 'werden',
    'haben', 'sind', 'oder', 'von', 'aus', 'es', 'wird', 'dass', 'sie', 'nach',
    'bei', 'um', 'am', 'noch', 'schon', 'bis', 'aber', 'vor', 'durch', 'alle',
    'dann', 'wir', 'sein', 'zur', 'zum', 'kann', 'nur', 'über', 'war', 'muss',
]

def generate_synthetic_data(num_pairs: int, src_words: list, tgt_words: list,
                            min_len: int = 5, max_len: int = 20):
    data = []
    for _ in range(num_pairs):
        src_len = random.randint(min_len, max_len)
        tgt_len = random.randint(min_len, max_len)
        src = ' '.join(random.choices(src_words, k=src_len))
        tgt = ' '.join(random.choices(tgt_words, k=tgt_len))
        data.append({'translation': {'en': src, 'de': tgt}})
    return data


def load_wmt_data(config):
    src_words = [w for w in WORDS if w.isascii()]
    tgt_words = [w for w in WORDS if not w.isascii()] or src_words

    # Try loading from HuggingFace first, fall back to synthetic
    try:
        from datasets import load_dataset
        print(f"Loading {config.dataset_name} ({config.dataset_config})...")
        dataset = load_dataset(config.dataset_name, config.dataset_config)

        def prepare_sentence(example):
            en = example.get('translation', {}).get('en', '') or \
                 example.get('en', '')
            de = example.get('translation', {}).get('de', '') or \
                 example.get('de', '')
            return en.lower().strip(), de.lower().strip()

        train_data = dataset['train'].select(range(30000))
        val_data = dataset.get('validation', dataset['train'].select(range(30000, 33000)))
        test_data = dataset.get('test', dataset['train'].select(range(33000, 36000)))
        print(f"  Train: {len(train_data)} pairs")
        print(f"  Val:   {len(val_data)} pairs")
        print(f"  Test:  {len(test_data)} pairs")

        en_sentences = []
        de_sentences = []
        for split_data in [train_data, val_data, test_data]:
            for example in split_data:
                en, de = prepare_sentence(example)
                en_sentences.append(en)
                de_sentences.append(de)

    except Exception as e:
        print(f"HuggingFace datasets unavailable ({e}), using synthetic data...")
        train_data = generate_synthetic_data(3000, src_words, tgt_words)
        val_data = generate_synthetic_data(300, src_words, tgt_words)
        test_data = generate_synthetic_data(300, src_words, tgt_words)
        print(f"  Train: {len(train_data)} (synthetic)")
        print(f"  Val:   {len(val_data)} (synthetic)")
        print(f"  Test:  {len(test_data)} (synthetic)")

        en_sentences = [d['translation']['en'] for d in train_data + val_data + test_data]
        de_sentences = [d['translation']['de'] for d in train_data + val_data + test_data]

    src_vocab = Vocab(config.src_vocab_size, config.min_freq)
    tgt_vocab = Vocab(config.tgt_vocab_size, config.min_freq)
    src_vocab.build(en_sentences)
    tgt_vocab.build(de_sentences)

    print(f"  Source vocab: {len(src_vocab)}")
    print(f"  Target vocab: {len(tgt_vocab)}")

    return {'train': train_data, 'validation': val_data, 'test': test_data}, src_vocab, tgt_vocab


class TranslationDataset(Dataset):
    def __init__(self, data, src_vocab, tgt_vocab, max_src_len, max_tgt_len, split='train'):
        self.pairs = []
        self.src_vocab = src_vocab
        self.tgt_vocab = tgt_vocab
        self.max_src_len = max_src_len
        self.max_tgt_len = max_tgt_len
        self.split = split

        for example in data:
            en = example.get('translation', {}).get('en', '') or example.get('en', '')
            de = example.get('translation', {}).get('de', '') or example.get('de', '')
            en, de = en.lower().strip(), de.lower().strip()
            if en and de:
                self.pairs.append((en, de))

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, idx):
        en, de = self.pairs[idx]
        src = self.src_vocab.encode(en, self.max_src_len)
        tgt = self.tgt_vocab.encode(de, self.max_tgt_len)
        return src, tgt


def _subset(data, indices):
    if hasattr(data, 'select'):
        return data.select(indices)
    return [data[i] for i in indices]


def create_dataloaders(config):
    dataset, src_vocab, tgt_vocab = load_wmt_data(config)

    train_dataset = TranslationDataset(
        _subset(dataset['train'], range(min(30000, len(dataset['train'])))), src_vocab, tgt_vocab,
        config.max_src_len, config.max_tgt_len, 'train'
    )
    val_data = dataset.get('validation', dataset['train'])
    val_dataset = TranslationDataset(
        _subset(val_data, range(min(3000, len(val_data)))),
        src_vocab, tgt_vocab, config.max_src_len, config.max_tgt_len, 'val'
    )
    test_data = dataset.get('test', dataset['train'])
    test_dataset = TranslationDataset(
        _subset(test_data, range(min(3000, len(test_data)))),
        src_vocab, tgt_vocab, config.max_src_len, config.max_tgt_len, 'test'
    )

    train_loader = DataLoader(
        train_dataset, batch_size=config.batch_size, shuffle=True,
        num_workers=2, pin_memory=True
    )
    val_loader = DataLoader(
        val_dataset, batch_size=config.batch_size, shuffle=False,
        num_workers=2, pin_memory=True
    )
    test_loader = DataLoader(
        test_dataset, batch_size=config.batch_size, shuffle=False,
        num_workers=2, pin_memory=True
    )

    return train_loader, val_loader, test_loader, src_vocab, tgt_vocab
