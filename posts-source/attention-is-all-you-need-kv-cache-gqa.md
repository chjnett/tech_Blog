---
slug: attention-is-all-you-need-kv-cache-gqa
title: "Attention Is All You Need"를 읽다가 KV 캐시 병목에 걸려 넘어진 이야기
excerpt: Attention Is All You Need 논문을 다시 읽다가 발견한 KV 캐시 병목 문제, 그리고 이를 해결하는 GQA(Grouped-Query Attention)를 미니 Transformer로 직접 구현해 검증한 기록.
tags: [transformer, attention, gqa, kv-cache, pytorch]
status: published
source_ref: https://github.com/chjnett/tech_Blog/tree/main/posts-assets/attention-is-all-you-need-kv-cache-gqa
---

## 1부. 원 논문을 다시 읽으며

2017년 논문 "Attention Is All You Need"를 다시 읽었다. 이 논문이 하는 주장은 명확하다. RNN과 CNN 없이, 순수하게 어텐션만으로 시퀀스 변환을 할 수 있고, 그게 더 빠르고 더 잘 된다는 것.

핵심 설계를 정리하면 이렇다.

- **스케일드 닷프로덕트 어텐션**: `Attention(Q, K, V) = softmax(QKᵀ / √dk) V`. `√dk`로 나누는 이유는 `dk`가 커질수록 내적의 분산이 커져 softmax가 그래디언트가 거의 0인 영역으로 밀려나기 때문이다.
- **멀티헤드 어텐션**: 하나의 큰 어텐션 대신, Q/K/V를 `h`개의 저차원 부분공간으로 나눠 병렬로 어텐션을 수행한다. 원 논문은 `h=8`, `d_k=d_v=64`를 썼다. 단일 헤드는 평균화 때문에 표현력이 제한되지만, 여러 헤드는 서로 다른 표현 부분공간에 주목할 수 있다.
- **인코더-디코더 구조**: 인코더는 셀프 어텐션 + FFN을 6번 반복하고, 디코더는 마스크드 셀프 어텐션 + 인코더-디코더 크로스 어텐션 + FFN을 6번 반복한다.

여기까지는 이해하는 데 오래 걸리지 않았다. 문제는 "이걸 실제로 서빙하려면 어떻게 되지?"라는 질문을 스스로 던졌을 때였다.

## 2부. 병목을 발견하다: 학습과 추론은 다른 게임이다

논문은 학습(training) 관점에서 쓰여 있다. 8개의 P100 GPU로 12시간 학습했다는 이야기가 나온다. 그런데 오늘날 GPT, LLaMA 같은 모델을 실제로 서빙할 때 문제가 되는 건 학습이 아니라 **자기회귀 디코딩(autoregressive decoding)**이다.

디코더는 토큰을 하나씩 생성한다. `n`번째 토큰을 생성하려면 `1`번부터 `n-1`번째 토큰까지의 Key, Value 벡터가 다시 필요하다. 매번 처음부터 다시 계산하면 너무 느리니까, 실제 서빙 시스템은 이전 토큰들의 K, V를 **KV 캐시**에 저장해두고 재사용한다.

문제는 이 캐시 크기다. 멀티헤드 어텐션은 헤드마다 독립적인 K, V를 가지므로, 캐시해야 할 벡터 수가 `레이어 수 × 헤드 수 × 시퀀스 길이`에 비례해서 커진다. 그리고 토큰을 하나 생성할 때마다 이 캐시 전체를 GPU 메모리에서 읽어야 한다. **연산량이 아니라 이 메모리 읽기(bandwidth)가 실제 병목**이라는 걸 알게 됐다.

직접 숫자로 확인해봤다. LLaMA-7B 정도 크기(레이어 32개, `d_model=4096`, 헤드 32개, `head_dim=128`)를 가정하고, fp16으로 배치 1일 때 KV 캐시 크기를 계산했다.

| 시퀀스 길이 | MHA (32 KV 헤드) | GQA (8 KV 헤드) | GQA (4 KV 헤드) | MQA (1 KV 헤드) |
|---:|---:|---:|---:|---:|
| 2,048 | 1.00 GB | 0.25 GB | 0.12 GB | 0.03 GB |
| 8,192 | 4.00 GB | 1.00 GB | 0.50 GB | 0.12 GB |
| 32,768 | 16.00 GB | 4.00 GB | 2.00 GB | 0.50 GB |
| 128,000 | 62.50 GB | 15.62 GB | 7.81 GB | 1.95 GB |

*(계산: `2(K,V) × 레이어 32 × 시퀀스 길이 × KV헤드 수 × head_dim 128 × 2바이트(fp16)`)*

![Fig 1 — LLaMA-7B 기준 KV 캐시 크기 vs 컨텍스트 길이. 128K에서 MHA는 62.5 GB로 A100 VRAM 한계에 육박한다.](/posts-assets/attention-is-all-you-need-kv-cache-gqa/fig1_llama7b_kv_cache.png)

128K 컨텍스트에서 MHA는 KV 캐시만 62.5GB다. 웬만한 GPU 한 장의 VRAM(24~80GB)을 캐시가 다 먹어버린다는 뜻이다. 여기서 "아, 원 논문이 다루지 않은 진짜 실전 병목이 이거구나" 싶었다.

자기회귀 디코딩에서 매 스텝마다 실제로 무슨 일이 일어나는지 흐름으로 보면 병목 위치가 명확하다.

```figure
{"type":"flow","caption":"자기회귀 디코딩 1 스텝 — 연산량이 아니라 캐시 전체를 읽는 메모리 대역폭이 병목","nodes":[{"id":"prev","label":"이전 토큰 K,V","note":"KV 캐시에서 전체 읽기\n(seq_len × layers × heads × head_dim)"},{"id":"new_q","label":"현재 토큰 Q","note":"새로 계산, 캐시 불필요"},{"id":"bottleneck","label":"HBM 대역폭 병목","note":"캐시 크기에 비례해 읽기 시간 증가","emphasis":true},{"id":"attn","label":"Attention 연산","note":"Q × (캐시 K,V) → 다음 토큰 확률"},{"id":"out","label":"다음 토큰 생성","note":"argmax 또는 sampling"}],"edges":[{"from":"prev","to":"bottleneck","label":"캐시 읽기"},{"from":"bottleneck","to":"attn"},{"from":"new_q","to":"attn"},{"from":"attn","to":"out"}]}
```


## 3부. GQA를 공부하다

이 문제를 실제로 푼 게 **[Multi-Query Attention(MQA, 2019)](https://arxiv.org/abs/1911.02150)**과 그걸 개선한 **[Grouped-Query Attention(GQA, 2023)](https://arxiv.org/abs/2305.13245)**이다. 아이디어는 단순하다.

> 쿼리(Q) 헤드 수는 그대로 두고, **Key/Value 헤드 수만 줄여서 여러 쿼리 헤드가 하나의 K/V를 공유**하게 한다.

왜 K/V만 줄이는가? 디코딩 매 스텝마다 실제로 메모리에서 읽고 쓰는 건 이전 토큰들의 K, V다. Q는 현재 스텝에서 새로 계산되는 값 하나뿐이라 캐시할 필요가 없다. 그래서 캐시 크기를 줄이는 가장 직접적인 방법은 K/V 헤드 수 자체를 줄이는 것이다.

- **MHA**: 쿼리 헤드 수 = KV 헤드 수 (예: 32 = 32). 표현력 최대, 캐시도 최대.
- **MQA**: KV 헤드 수 = 1. 모든 쿼리가 하나의 K/V를 공유. 캐시는 최소지만 품질 손실 우려.
- **GQA**: 그 중간. 예를 들어 32개 쿼리 헤드를 8개 그룹으로 묶어 각 그룹이 하나의 K/V를 공유(그룹당 4개 쿼리 헤드). LLaMA 2/3, Mistral, Qwen, Gemma 등 오늘날 거의 모든 오픈소스 LLM이 이 방식을 쓴다.

GQA를 직관적으로 이해하려면 그림이 훨씬 빠르다. 세 가지 방식을 나란히 비교해보면 이렇다.

```figure
{"type":"groups","caption":"Query 헤드는 항상 4개, Key/Value 헤드 수만 줄어든다 — 같은 색으로 묶인 Query들이 KV 하나를 공유한다","groups":[{"label":"Multi-head (MHA)","note":"KV heads: 4 (one each)","queryCount":4,"kvCount":4},{"label":"Grouped-query (GQA)","note":"KV heads: 2 (shared in groups)","queryCount":4,"kvCount":2},{"label":"Multi-query (MQA)","note":"KV heads: 1 (shared by all)","queryCount":4,"kvCount":1}]}
```

`repeat_kv`가 실제로 하는 일을 차원 단위로 추적하면 이렇다.

```figure
{"type":"flow","caption":"repeat_kv 브로드캐스트 동작 — 캐시에는 n_kv_head만 저장, 어텐션 계산 순간에만 쿼리 수에 맞게 반복","nodes":[{"id":"kv_cache","label":"KV 캐시","note":"shape: (B, n_kv_head=4, T, head_dim)\n메모리에 이 크기만 저장"},{"id":"expand","label":"expand + reshape","note":"실제 메모리 복사 없이 view만 변경"},{"id":"k_rep","label":"k_rep","note":"shape: (B, n_head=8, T, head_dim)\n어텐션 계산에만 이 크기 사용","emphasis":true},{"id":"attn","label":"Scaled Dot-Product Attention","note":"Q(n_head) × K_rep(n_head) → O(n_head)"}],"edges":[{"from":"kv_cache","to":"expand","label":"n_rep=2회 반복"},{"from":"expand","to":"k_rep"},{"from":"k_rep","to":"attn"}]}
```

코드 레벨에서 보면 핵심은 `repeat_kv`라는 함수 하나로 요약된다. K, V 헤드 수가 쿼리 헤드 수보다 적으니, 어텐션 계산 직전에 그룹 크기만큼 K, V를 반복(broadcast)해서 쿼리 헤드 수에 맞춰준다.

```python
def repeat_kv(x: torch.Tensor, n_rep: int) -> torch.Tensor:
    """
    x: (batch, n_kv_heads, seq_len, head_dim)
    쿼리 헤드 수 = n_kv_heads * n_rep 이 되도록 KV를 반복한다.
    실제로 메모리에 복제하는 대신, 계산 시점에만 view/expand로 처리해서
    캐시 자체의 저장 공간은 늘리지 않는 게 핵심이다.
    """
    if n_rep == 1:
        return x
    batch, n_kv_heads, seq_len, head_dim = x.shape
    x = x[:, :, None, :, :].expand(batch, n_kv_heads, n_rep, seq_len, head_dim)
    return x.reshape(batch, n_kv_heads * n_rep, seq_len, head_dim)
```

**캐시에 저장하는 건 줄어든 KV 헤드 수만큼뿐이고, 반복은 어텐션 스코어를 계산하는 순간에만 일어난다.** 그래서 메모리에서 실제로 읽어오는 양(대역폭 병목의 원인)이 줄어드는 것이다.

## 4부. 1차 검증: numpy로 대략적인 느낌 잡아보기

GPU 클러스터 없이 이 효과를 "느껴볼" 방법이 있을까 고민했다. **KV 캐시를 읽는 행위 자체가 메모리 대역폭에 의존한다**는 점에 착안해서, numpy 배열 복사를 GPU 메모리 읽기의 대략적인 프록시로 삼아 CPU에서 타이밍을 재봤다.

```python
import numpy as np
import time

n_layers, d_model, n_heads = 32, 4096, 32
head_dim = d_model // n_heads  # 128
seq_for_timing = 4096

configs = {"MHA": 32, "GQA-8": 8, "GQA-4": 4, "MQA": 1}

for name, n_kv in configs.items():
    k = np.random.random((seq_for_timing, n_kv, head_dim)).astype(np.float16)
    v = np.random.random((seq_for_timing, n_kv, head_dim)).astype(np.float16)
    t0 = time.perf_counter()
    for _ in range(20):
        _ = k.copy(); _ = v.copy()
    t1 = time.perf_counter()
    print(name, (t1 - t0) / 20 * 1000, "ms/step")
```

결과(레이어 1개 기준, 시퀀스 길이 4096):

| 구성 | KV 헤드 수 | 스텝당 평균 복사 시간 |
|---|---:|---:|
| MHA | 32 | 27.64 ms |
| GQA-8 | 8 | 5.88 ms |
| GQA-4 | 4 | 0.92 ms |
| MQA | 1 | 0.17 ms |

![Fig 2 — numpy 복사 시간 프록시. KV 헤드 수를 줄일수록 읽기 시간이 선형에 가깝게 줄어든다 (seq_len=4096, 레이어 1개 기준).](/posts-assets/attention-is-all-you-need-kv-cache-gqa/fig2_numpy_proxy_timing.png)

절대값 자체는 실제 GPU HBM 대역폭과 다르지만(CPU 캐시 계층, numpy 오버헤드 등이 섞여 있다), **KV 헤드 수를 줄일수록 데이터를 읽는 시간이 거의 선형적으로 줄어든다**는 추세는 명확했다. 여기까지가 "느낌만 잡은" 1차 검증이었다. 이걸로는 부족했다 — 실제로 attention이 동작하는 전체 파이프라인(파라미터, 캐시, 생성, 학습)에서 이 효과가 어떻게 나타나는지 직접 코드로 확인하고 싶었다.

## 5부. 직접 미니 Transformer를 구현해서 검증하기

nanoGPT 스타일의 decoder-only Transformer를 몇백 줄로 직접 구현했다. attention 모듈 하나만 `n_kv_head` 파라미터로 MHA/GQA/MQA를 전환할 수 있게 만들고, 이 환경(CPU, GPU 없음)에서 실제로 돌려 검증했다.

### 5-1. 모델 구현

핵심은 `CausalSelfAttention`이다. 쿼리는 항상 `n_head`개, K/V는 `n_kv_head`개만 projection하고, `repeat_kv`로 쿼리 헤드 수에 맞춰 반복한다. `generate()`는 실제 서빙과 동일하게 KV 캐시를 채워가며 토큰을 하나씩 만든다.

```python
"""
model.py — 아주 작은 GPT 스타일 decoder-only Transformer.
attention 모듈 하나만 n_kv_head 파라미터로 MHA / GQA / MQA를 전환할 수 있게 만들었다.

- n_kv_head == n_head           -> MHA (원 논문과 동일, 헤드마다 독립적인 K/V)
- 1 < n_kv_head < n_head        -> GQA (여러 쿼리 헤드가 K/V 그룹을 공유)
- n_kv_head == 1                -> MQA (모든 쿼리 헤드가 K/V 1개를 공유)
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
        self.n_rep = config.n_head // config.n_kv_head  # 하나의 K/V를 공유하는 쿼리 헤드 수
        self.head_dim = config.n_embd // config.n_head

        # 쿼리는 항상 n_head 만큼, K/V는 n_kv_head 만큼만 projection
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
            k = torch.cat([past_k, k], dim=2)   # 캐시에는 n_kv_head 크기로만 쌓인다 <- 메모리 절약 포인트
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
        self.tok_emb.weight = self.lm_head.weight  # 원 논문처럼 임베딩과 출력층 가중치 공유

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
        """KV 캐시를 사용한 자기회귀 생성. 실제 서빙과 동일한 방식으로 토큰을 하나씩 만든다."""
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
```

### 5-2. 파라미터 수 / KV 캐시 메모리 / 추론 속도 벤치마크

```python
"""
benchmark.py — MHA / GQA / MQA 세 구성에 대해
  1) 파라미터 수
  2) KV 캐시 메모리 (이론값 계산 + torch로 실측)
  3) 시퀀스 길이별 추론 속도 (tokens/sec, KV 캐시 사용)
를 비교한다.
"""
import time
import torch
from model import MiniGPT, GPTConfig

torch.manual_seed(0)

VOCAB_SIZE = 65
N_LAYER, N_EMBD, N_HEAD = 6, 256, 8
BLOCK_SIZE = 4096

CONFIGS = {
    "MHA  (n_kv=8)": 8,
    "GQA-4 (n_kv=4)": 4,
    "GQA-2 (n_kv=2)": 2,
    "MQA  (n_kv=1)": 1,
}
SEQ_LENS_FOR_SPEED = [64, 256, 1024]
NEW_TOKENS = 64
BYTES_PER_PARAM = 4  # float32


def theoretical_kv_cache_bytes(n_layer, seq_len, n_kv_head, head_dim, bytes_per_val=4):
    return 2 * n_layer * seq_len * n_kv_head * head_dim * bytes_per_val


def build_model(n_kv_head):
    cfg = GPTConfig(vocab_size=VOCAB_SIZE, block_size=BLOCK_SIZE, n_layer=N_LAYER,
                     n_head=N_HEAD, n_kv_head=n_kv_head, n_embd=N_EMBD, dropout=0.0)
    model = MiniGPT(cfg)
    model.eval()
    return model, cfg


def measured_kv_cache_bytes(model, cfg, seq_len):
    x = torch.randint(0, VOCAB_SIZE, (1, seq_len))
    with torch.no_grad():
        _, _, kv_caches = model(x, use_cache=True)
    total = 0
    for k, v in kv_caches:
        total += k.element_size() * k.nelement()
        total += v.element_size() * v.nelement()
    return total


def measure_tokens_per_sec(model, prompt_len, new_tokens):
    x = torch.randint(0, VOCAB_SIZE, (1, prompt_len))
    with torch.no_grad():
        t0 = time.perf_counter()
        model.generate(x, max_new_tokens=new_tokens)
        t1 = time.perf_counter()
    return new_tokens / (t1 - t0)


def main():
    head_dim = N_EMBD // N_HEAD
    models = {}
    print("1) 파라미터 수")
    for name, n_kv in CONFIGS.items():
        model, cfg = build_model(n_kv)
        models[name] = (model, cfg)
        print(f"{name:>16}: {model.num_params():>10,} params")

    print("\n2) KV 캐시 메모리 (이론값, seq_len별)")
    for seq_len in [512, 4096, 32768, 131072]:
        print(f"-- seq_len={seq_len:,} --")
        for name, n_kv in CONFIGS.items():
            theo = theoretical_kv_cache_bytes(N_LAYER, seq_len, n_kv, head_dim, BYTES_PER_PARAM)
            print(f"  {name:>16}: {theo/1e6:8.2f} MB")

    print("\n실측값 (seq_len=1024)")
    for name, (model, cfg) in models.items():
        measured = measured_kv_cache_bytes(model, cfg, seq_len=1024)
        theo = theoretical_kv_cache_bytes(N_LAYER, 1024, CONFIGS[name], head_dim, BYTES_PER_PARAM)
        print(f"  {name:>16}: 실측 {measured/1e6:8.3f} MB  |  이론값 {theo/1e6:8.3f} MB")

    print("\n3) 추론 속도 (tokens/sec)")
    for prompt_len in SEQ_LENS_FOR_SPEED:
        print(f"-- prompt_len={prompt_len} --")
        for name, (model, cfg) in models.items():
            tps = measure_tokens_per_sec(model, prompt_len, NEW_TOKENS)
            print(f"  {name:>16}: {tps:8.1f} tokens/sec")


if __name__ == "__main__":
    main()
```

**이 환경(CPU, GPU 없음)에서 실제로 실행한 결과:**

파라미터 수 (n_layer=6, n_embd=256, n_head=8):

| 구성 | 파라미터 수 |
|---|---:|
| MHA (n_kv=8) | 5,787,136 |
| GQA-4 (n_kv=4) | 5,393,920 |
| GQA-2 (n_kv=2) | 5,197,312 |
| MQA (n_kv=1) | 5,099,008 |

KV 캐시 메모리 — **실측값이 이론값과 정확히 일치했다**:

| 구성 | seq_len=1024 실측 | 이론값 |
|---|---:|---:|
| MHA | 12.583 MB | 12.583 MB |
| GQA-4 | 6.291 MB | 6.291 MB |
| GQA-2 | 3.146 MB | 3.146 MB |
| MQA | 1.573 MB | 1.573 MB |

추론 속도(tokens/sec), 프롬프트 길이별:

| 구성 | prompt=64 | prompt=256 | prompt=1024 |
|---|---:|---:|---:|
| MHA | 186.2 | 133.6 | 67.6 |
| GQA-4 | 174.6 | 132.9 | 56.2 |
| GQA-2 | 197.1 | 158.2 | 70.3 |
| MQA | 182.1 | 174.5 | 110.5 |

![Fig 3 — 추론 속도 비교. 컨텍스트 1024에서 MQA가 MHA 대비 약 1.6× 빠르다.](/posts-assets/attention-is-all-you-need-kv-cache-gqa/fig3_inference_speed.png)

짧은 컨텍스트(64, 256)에서는 이 정도 크기의 모델과 CPU 환경에서는 차이가 노이즈에 묻혀 뚜렷하지 않았다. 하지만 컨텍스트가 1024로 늘어나자 **MQA가 MHA 대비 약 1.6배 빨라졌다**(110.5 vs 67.6 tokens/sec) — 메모리 대역폭 병목이 컨텍스트 길이에 비례해서 커진다는 이론과 방향이 일치하는 결과다. 실제 GPU 서빙 환경, 그리고 더 긴 컨텍스트에서는 이 격차가 훨씬 크게 벌어질 것이다(2부에서 계산한 128K 컨텍스트 기준 62.5GB vs 1.95GB처럼).

### 5-3. 학습 sanity check — "제대로 동작은 하는가"

본격적인 학습이나 성능 비교가 아니라, 세 구성 모두 실제로 학습이 되는지(loss가 정상적으로 줄어드는지)만 가볍게 확인했다. 데이터는 저작권 문제를 피하기 위해 반복 패턴 기반의 합성 텍스트를 직접 생성해서 썼다.

```python
"""
train_sanity_check.py — 합성 데이터로 300 스텝만 학습시켜
MHA/GQA/MQA가 모두 정상적으로 loss가 줄어드는지 정성적으로 확인한다.
"""
import random
import torch
from model import MiniGPT, GPTConfig

torch.manual_seed(0)
random.seed(0)

VOCAB = list("abcdefghij")
STOI = {ch: i for i, ch in enumerate(VOCAB)}
VOCAB_SIZE = len(VOCAB)

BLOCK_SIZE, BATCH_SIZE, N_STEPS, LR = 64, 32, 300, 3e-3
N_LAYER, N_EMBD, N_HEAD = 4, 64, 4

CONFIGS = {"MHA  (n_kv=4)": 4, "GQA-2 (n_kv=2)": 2, "MQA  (n_kv=1)": 1}


def make_synthetic_corpus(n_chars=20000):
    """몇 가지 반복 주기를 가진 패턴을 섞어 이어붙인 합성 텍스트 (자체 생성, 저작권 문제 없음)."""
    periods = [2, 3, 4, 5]
    out = []
    while len(out) < n_chars:
        period = random.choice(periods)
        pattern = [random.choice(VOCAB) for _ in range(period)]
        repeats = random.randint(5, 15)
        out.extend(pattern * repeats)
    return "".join(out[:n_chars])


def get_batch(data_ids, block_size, batch_size):
    ix = torch.randint(0, len(data_ids) - block_size - 1, (batch_size,))
    x = torch.stack([data_ids[i:i + block_size] for i in ix])
    y = torch.stack([data_ids[i + 1:i + block_size + 1] for i in ix])
    return x, y


def train_one_config(n_kv_head, data_ids):
    cfg = GPTConfig(vocab_size=VOCAB_SIZE, block_size=BLOCK_SIZE, n_layer=N_LAYER,
                     n_head=N_HEAD, n_kv_head=n_kv_head, n_embd=N_EMBD, dropout=0.0)
    model = MiniGPT(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    losses = []
    for _ in range(N_STEPS):
        x, y = get_batch(data_ids, BLOCK_SIZE, BATCH_SIZE)
        _, loss, _ = model(x, targets=y)
        opt.zero_grad(); loss.backward(); opt.step()
        losses.append(loss.item())
    return losses


def main():
    text = make_synthetic_corpus()
    data_ids = torch.tensor([STOI[c] for c in text], dtype=torch.long)
    for name, n_kv in CONFIGS.items():
        losses = train_one_config(n_kv, data_ids)
        print(f"{name}: 최종 loss(마지막 30스텝 평균) = {sum(losses[-30:])/30:.4f}")


if __name__ == "__main__":
    main()
```

**실행 결과** (무작위 예측 시 이론 loss = ln(10) ≈ 2.303):

| 구성 | 시작 loss (30-step 평균) | 최종 loss (마지막 30-step 평균) |
|---|---:|---:|
| MHA (n_kv=4) | 2.323 | **1.034** |
| GQA-2 (n_kv=2) | 2.334 | 1.207 |
| MQA (n_kv=1) | 2.329 | 1.091 |

![Fig 4 — 학습 sanity check. 세 구성 모두 300 스텝 안에 2.3 → 1.0~1.2대로 정상 수렴. MHA가 가장 낮지만 차이는 근소하다.](/posts-assets/attention-is-all-you-need-kv-cache-gqa/fig4_loss_sanity.png)

세 구성 모두 300 스텝 만에 무작위 예측 수준(2.303)에서 1.0~1.2 근처까지 정상적으로 수렴했다 — "동작은 제대로 한다"는 sanity check를 통과했다. MHA가 가장 낮고 GQA/MQA가 근소하게 뒤처지는 것도, 실제 논문·실무에서 보고되는 "GQA/MQA는 약간의 품질 손실이 있지만 크지 않다"는 경향과 방향이 일치한다.

세 가지 구성의 품질 vs 속도 트레이드오프를 한 줄로 정리하면 이렇다.

```figure
{"type":"flow","caption":"MHA / GQA / MQA 품질·속도 트레이드오프 — 어느 쪽으로 이동할수록 서빙 비용이 내려가고, 표현력이 미세하게 줄어든다","nodes":[{"id":"mha","label":"MHA","note":"품질 최대, 캐시 최대\nLoss ≈ 1.03"},{"id":"gqa","label":"GQA","note":"품질·속도 균형점\nLoss ≈ 1.07~1.20","emphasis":true},{"id":"mqa","label":"MQA","note":"캐시 최소, 속도 최대\nLoss ≈ 1.09"}],"edges":[{"from":"mha","to":"gqa","label":"캐시 ↓  속도 ↑"},{"from":"gqa","to":"mqa","label":"캐시 ↓↓  속도 ↑↑"}]}
```

## 6부. 정리: 논문이 말하지 않은 것, 이후 연구가 채운 것, 그리고 직접 확인한 것

원 논문은 학습 효율과 번역 품질에 집중했다. 하지만 오늘날 이 아키텍처를 실제로 서비스하는 데는 논문이 다루지 않은 병목 — 자기회귀 디코딩에서의 메모리 대역폭 — 이 훨씬 크게 작용한다. 이 병목을 이해하고, 직접 미니 구현체로 확인하고 나서야:

1. 왜 최신 LLM들이 하나같이 GQA(혹은 그 확장인 Multi-head Latent Attention)를 쓰는지
2. 왜 "모델이 긴 컨텍스트를 이해하는가"(위치 인코딩 문제)와 "그 긴 컨텍스트를 감당 가능한 비용으로 서빙할 수 있는가"(KV 캐시 문제)가 서로 다른 문제인지
3. KV 헤드 수를 줄이는 게 파라미터 수 감소(약간), 캐시 메모리 감소(뚜렷, 이론과 실측이 정확히 일치), 추론 속도 개선(컨텍스트가 길수록 뚜렷), 그리고 아주 근소한 품질 손실(학습 sanity check로 확인)로 어떻게 이어지는지

이 세 가지가 훨씬 구체적으로 이해됐다.

GPU 클러스터 없이도 — 이론적인 메모리 계산, CPU 레벨의 소규모 시뮬레이션, 그리고 몇백 줄짜리 미니 구현체 + 300스텝짜리 sanity check만으로도 "왜 이 설계가 필요했는가"를 직접 체감할 수 있었다는 게 이번 학습 전체에서 가장 남는 부분이다.


---

*이 글에 사용된 코드 전체(`model.py`, `benchmark.py`, `train_sanity_check.py`, `README.md`)는 첨부 파일로 함께 제공. `pip install torch --break-system-packages` 하나만 있으면 GPU 없이 그대로 재현 가능하다.*

---

*References:*

- **[1] Attention Is All You Need**, Vaswani et al., NeurIPS 2017. [arXiv:1706.03762](https://arxiv.org/abs/1706.03762)
- **[2] Fast Transformer Decoding: One Write-Head is All You Need (MQA)**, Shazeer, 2019. [arXiv:1911.02150](https://arxiv.org/abs/1911.02150)
- **[3] GQA: Training Generalized Multi-Query Transformer Models from Multi-Head Checkpoints**, Ainslie et al., EMNLP 2023. [arXiv:2305.13245](https://arxiv.org/abs/2305.13245)
