"""
model.py — 작은 GPT 스타일 decoder-only Transformer.
"""

from dataclasses import dataclass
import torch
import torch.nn as nn
import torch.nn.functional as F

@dataclass
class GPTConfig:
    vocab_size: int = 65
    block_size: int = 256
    n_layer: int = 4
    n_head: int = 8          # 쿼리 헤드 수 (항상 고정)
    n_kv_head: int = 8       # K/V 헤드 수: n_head와 같으면 MHA, 작으면 GQA/MQA
    n_embd: int = 128
    dropout: float = 0.0
    bias: bool = False

def repeat_kv(x: torch.Tensor, n_rep: int) -> torch.Tensor:
    if n_rep == 1:
        return x
    b, n_kv, t, hd = x.shape
    x = x[:, :, None, :, :].expand(b, n_kv, n_rep, t, hd)
    return x.reshape(b, n_kv * n_rep, t, hd)

class CausalSelfAttention(nn.Module):
    def __init__(self, config: GPTConfig):
        super().__init__()
        assert config.n_embd % config.n_head == 0
        assert config.n_head % config.n_kv_head == 0, (
            "n_head는 n_kv_head로 나누어 떨어져야 한다 (그룹을 균등하게 나누기 위해)"
        )
        self.n_head = config.n_head
        self.n_kv_head = config.n_kv_head
        self.n_rep = config.n_head // config.n_kv_head
        self.head_dim = config.n_embd // config.n_head
        self.q_proj = nn.Linear(config.n_embd, config.n_head * self.head_dim, bias=config.bias)
        self.k_proj = nn.Linear(config.n_embd, config.n_kv_head * self.head_dim, bias=config.bias)
        self.v_proj = nn.Linear(config.n_embd, config.n_kv_head * self.head_dim, bias=config.bias)
        self.out_proj = nn.Linear(config.n_embd, config.n_embd, bias=config.bias)
        self.attn_dropout = nn.Dropout(config.dropout)
        self.resid_dropout = nn.Dropout(config.dropout)

    def forward(self, x: torch.Tensor, kv_cache: tuple | None = None, use_cache: bool = False):
        B, T, C = x.shape
        q = self.q_proj(x).view(B, T, self.n_head, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.n_kv_head, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.n_kv_head, self.head_dim).transpose(1, 2)
        if kv_cache is not None:
            past_k, past_v = kv_cache
            k = torch.cat([past_k, k], dim=2)
            v = torch.cat([past_v, v], dim=2)
        new_cache = (k, v) if use_cache else None
        k_rep = repeat_kv(k, self.n_rep)
        v_rep = repeat_kv(v, self.n_rep)
        is_causal = kv_cache is None
        y = F.scaled_dot_product_attention(
            q, k_rep, v_rep, dropout_p=self.attn_dropout.p if self.training else 0.0, is_causal=is_causal
        )
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        y = self.resid_dropout(self.out_proj(y))
        return y, new_cache

class MLP(nn.Module):
    def __init__(self, config: GPTConfig):
        super().__init__()
        self.fc = nn.Linear(config.n_embd, 4 * config.n_embd, bias=config.bias)
        self.proj = nn.Linear(4 * config.n_embd, config.n_embd, bias=config.bias)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x):
        return self.dropout(self.proj(F.gelu(self.fc(x))))

class Block(nn.Module):
    def __init__(self, config: GPTConfig):
        super().__init__()
        self.ln1 = nn.LayerNorm(config.n_embd, bias=config.bias)
        self.attn = CausalSelfAttention(config)
        self.ln2 = nn.LayerNorm(config.n_embd, bias=config.bias)
        self.mlp = MLP(config)

    def forward(self, x, kv_cache=None, use_cache=False):
        a, new_cache = self.attn(self.ln1(x), kv_cache=kv_cache, use_cache=use_cache)
        x = x + a
        x = x + self.mlp(self.ln2(x))
        return x, new_cache

class MiniGPT(nn.Module):
    def __init__(self, config: GPTConfig):
        super().__init__()
        self.config = config
        self.tok_emb = nn.Embedding(config.vocab_size, config.n_embd)
        self.pos_emb = nn.Embedding(config.block_size, config.n_embd)
        self.drop = nn.Dropout(config.dropout)
        self.blocks = nn.ModuleList([Block(config) for _ in range(config.n_layer)])
        self.ln_f = nn.LayerNorm(config.n_embd, bias=config.bias)
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size, bias=False)
        self.tok_emb.weight = self.lm_head.weight

    def forward(self, idx, targets=None, kv_caches=None, use_cache=False, start_pos=0):
        B, T = idx.shape
        pos = torch.arange(start_pos, start_pos + T, device=idx.device)
        x = self.drop(self.tok_emb(idx) + self.pos_emb(pos)[None, :, :])
        if kv_caches is None:
            kv_caches = [None] * len(self.blocks)
        new_caches = []
        for block, cache in zip(self.blocks, kv_caches):
            x, new_cache = block(x, kv_cache=cache, use_cache=use_cache)
            new_caches.append(new_cache)
        x = self.ln_f(x)
        logits = self.lm_head(x)
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
        return logits, loss, (new_caches if use_cache else None)

    def num_params(self):
        return sum(p.numel() for p in self.parameters())

    @torch.no_grad()
    def generate(self, idx, max_new_tokens):
        logits, _, kv_caches = self.forward(idx, use_cache=True, start_pos=0)
        pos = idx.shape[1]
        next_id = torch.argmax(logits[:, -1, :], dim=-1, keepdim=True)
        out = torch.cat([idx, next_id], dim=1)
        for _ in range(max_new_tokens - 1):
            logits, _, kv_caches = self.forward(next_id, use_cache=True, kv_caches=kv_caches, start_pos=pos)
            pos += 1
            next_id = torch.argmax(logits[:, -1, :], dim=-1, keepdim=True)
            out = torch.cat([out, next_id], dim=1)
        return out, kv_caches
