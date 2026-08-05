"""
mla_train_sanity.py — GQA-4와 MLA(Pure)가 정확히 똑같은 KV 캐시 메모리를 쓰도록 설정한 뒤
300 스텝 학습을 돌려 Loss 수렴을 비교한다.

MLA는 KV를 저랭크 잠재 벡터(c_kv, latent_dim=32)로 압축하고
Up-projection으로 원래 차원으로 복원하는 구조다.
GQA-4는 n_kv_head=4로 설정해서 동일 캐시 크기를 맞춘다.
"""

import sys, os
sys.path.insert(0, '/Users/cheonhyeonjun/tech_blog')
os.chdir('/Users/cheonhyeonjun/tech_blog')

import random, time
import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass
from model import GPTConfig, MLP, Block, MiniGPT

torch.manual_seed(42)
random.seed(42)

# ─────────── MLA 어텐션 모듈 ───────────
@dataclass
class MLAConfig:
    vocab_size: int = 65
    block_size: int = 64
    n_layer: int = 4
    n_head: int = 8
    n_embd: int = 128
    latent_dim: int = 32   # c_kv 차원: GQA-4와 동일한 KV 캐시 용량이 되도록 설정
    dropout: float = 0.0
    bias: bool = False

class MLASelfAttention(nn.Module):
    def __init__(self, config: MLAConfig):
        super().__init__()
        self.n_head = config.n_head
        self.head_dim = config.n_embd // config.n_head
        self.latent_dim = config.latent_dim

        # Q projection
        self.q_proj = nn.Linear(config.n_embd, config.n_embd, bias=config.bias)
        # Down-projection: x → c_kv (저랭크 잠재 벡터)
        self.kv_down = nn.Linear(config.n_embd, config.latent_dim, bias=config.bias)
        # Up-projection: c_kv → K, V (원래 차원으로 복원)
        self.k_up = nn.Linear(config.latent_dim, config.n_embd, bias=config.bias)
        self.v_up = nn.Linear(config.latent_dim, config.n_embd, bias=config.bias)
        # Output
        self.out_proj = nn.Linear(config.n_embd, config.n_embd, bias=config.bias)
        self.resid_dropout = nn.Dropout(config.dropout)

    def forward(self, x, kv_cache=None, use_cache=False):
        B, T, C = x.shape
        q = self.q_proj(x).view(B, T, self.n_head, self.head_dim).transpose(1, 2)

        # ── 핵심: c_kv (저랭크 잠재 벡터) 만 캐시에 저장 ──
        c_kv = self.kv_down(x)                        # (B, T, latent_dim)
        if kv_cache is not None:
            c_kv = torch.cat([kv_cache, c_kv], dim=1) # 이전 잠재벡터 이어붙이기
        new_cache = c_kv if use_cache else None

        # Up-projection으로 K, V 복원
        k = self.k_up(c_kv).view(B, -1, self.n_head, self.head_dim).transpose(1, 2)
        v = self.v_up(c_kv).view(B, -1, self.n_head, self.head_dim).transpose(1, 2)

        is_causal = kv_cache is None
        y = F.scaled_dot_product_attention(q, k, v, is_causal=is_causal)
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        y = self.resid_dropout(self.out_proj(y))
        return y, new_cache

class MLABlock(nn.Module):
    def __init__(self, config: MLAConfig):
        super().__init__()
        self.ln1 = nn.LayerNorm(config.n_embd, bias=config.bias)
        self.attn = MLASelfAttention(config)
        self.ln2 = nn.LayerNorm(config.n_embd, bias=config.bias)
        self.fc   = nn.Linear(config.n_embd, 4 * config.n_embd, bias=config.bias)
        self.proj = nn.Linear(4 * config.n_embd, config.n_embd, bias=config.bias)
        self.drop = nn.Dropout(config.dropout)

    def forward(self, x, kv_cache=None, use_cache=False):
        a, new_cache = self.attn(self.ln1(x), kv_cache=kv_cache, use_cache=use_cache)
        x = x + a
        x = x + self.drop(self.proj(F.gelu(self.fc(self.ln2(x)))))
        return x, new_cache

class MiniMLA(nn.Module):
    def __init__(self, config: MLAConfig):
        super().__init__()
        self.config = config
        self.tok_emb = nn.Embedding(config.vocab_size, config.n_embd)
        self.pos_emb = nn.Embedding(config.block_size, config.n_embd)
        self.drop = nn.Dropout(config.dropout)
        self.blocks = nn.ModuleList([MLABlock(config) for _ in range(config.n_layer)])
        self.ln_f   = nn.LayerNorm(config.n_embd, bias=config.bias)
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size, bias=False)
        self.tok_emb.weight = self.lm_head.weight

    def forward(self, idx, targets=None, kv_caches=None, use_cache=False, start_pos=0):
        B, T = idx.shape
        pos = torch.arange(start_pos, start_pos + T, device=idx.device)
        x = self.drop(self.tok_emb(idx) + self.pos_emb(pos)[None])
        if kv_caches is None:
            kv_caches = [None] * len(self.blocks)
        new_caches = []
        for block, cache in zip(self.blocks, kv_caches):
            x, nc = block(x, kv_cache=cache, use_cache=use_cache)
            new_caches.append(nc)
        x = self.ln_f(x)
        logits = self.lm_head(x)
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
        return logits, loss, (new_caches if use_cache else None)

    def num_params(self):
        return sum(p.numel() for p in self.parameters())

# ─────────── 학습 설정 ───────────
VOCAB = list("abcdefghij")
STOI  = {ch: i for i, ch in enumerate(VOCAB)}
VOCAB_SIZE = len(VOCAB)
BLOCK_SIZE, BATCH_SIZE, N_STEPS, LR = 64, 32, 300, 3e-3

def make_corpus(n=20000):
    out = []
    while len(out) < n:
        period = random.choice([2,3,4,5])
        pat = [random.choice(VOCAB) for _ in range(period)]
        out.extend(pat * random.randint(5, 15))
    return "".join(out[:n])

def get_batch(data, bs, bl):
    ix = torch.randint(0, len(data)-bl-1, (bs,))
    x = torch.stack([data[i:i+bl] for i in ix])
    y = torch.stack([data[i+1:i+bl+1] for i in ix])
    return x, y

def train(model, data, n_steps=N_STEPS, lr=LR):
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    losses = []
    for _ in range(n_steps):
        x, y = get_batch(data, BATCH_SIZE, BLOCK_SIZE)
        _, loss, _ = model(x, targets=y)
        opt.zero_grad(); loss.backward(); opt.step()
        losses.append(loss.item())
    return losses

data = torch.tensor([STOI[c] for c in make_corpus()], dtype=torch.long)

# GQA-4 (n_kv=4, KV 캐시 차원 = 4 * head_dim = 4 * 16 = 64)
from model import GPTConfig as GQACfg
gqa_cfg = GQACfg(vocab_size=VOCAB_SIZE, block_size=BLOCK_SIZE, n_layer=4,
                  n_head=8, n_kv_head=4, n_embd=128, dropout=0.0)
gqa_model = MiniGPT(gqa_cfg)

# MLA (latent_dim=32 -> c_kv 캐시 크기 = 32 ≈ GQA-4의 KV 차원과 맞춤)
mla_cfg = MLAConfig(vocab_size=VOCAB_SIZE, block_size=BLOCK_SIZE, n_layer=4,
                     n_head=8, n_embd=128, latent_dim=32, dropout=0.0)
mla_model = MiniMLA(mla_cfg)

# KV 캐시 크기 계산 (seq_len=64 기준)
def kv_cache_bytes(model_name, n_kv_head=None, latent_dim=None,
                   n_layer=4, seq_len=64, head_dim=16, bpv=4):
    if n_kv_head:
        return 2 * n_layer * seq_len * n_kv_head * head_dim * bpv
    else:
        return n_layer * seq_len * latent_dim * bpv

gqa_cache = kv_cache_bytes("GQA-4", n_kv_head=4, n_layer=4, seq_len=64, head_dim=16)
mla_cache = kv_cache_bytes("MLA",   latent_dim=32, n_layer=4, seq_len=64)

print("=== KV 캐시 크기 비교 (seq_len=64) ===")
print(f"  GQA-4 캐시: {gqa_cache} bytes")
print(f"  MLA   캐시: {mla_cache} bytes")
print(f"  GQA-4 파라미터: {gqa_model.num_params():,}")
print(f"  MLA   파라미터: {mla_model.num_params():,}")

print("\n=== 학습 시작 ===")
gqa_losses = train(gqa_model, data)
mla_losses = train(mla_model, data)

gqa_final = sum(gqa_losses[-30:])/30
mla_final = sum(mla_losses[-30:])/30
gqa_init  = sum(gqa_losses[:30])/30
mla_init  = sum(mla_losses[:30])/30

print(f"\n  GQA-4: 초반 Loss {gqa_init:.4f} → 최종 Loss {gqa_final:.4f}")
print(f"  MLA:   초반 Loss {mla_init:.4f} → 최종 Loss {mla_final:.4f}")

# 100-step 구간별 출력 (표 용도)
print("\n=== 구간별 Loss (100스텝 평균) ===")
for label, losses in [("GQA-4", gqa_losses), ("MLA", mla_losses)]:
    s1 = sum(losses[0:100])/100
    s2 = sum(losses[100:200])/100
    s3 = sum(losses[200:300])/100
    print(f"  {label}: step1-100={s1:.4f}, step101-200={s2:.4f}, step201-300={s3:.4f}")
