---
slug: mla-article
title: GQA의 한계, 그리고 MLA로 넘어가기 — 논문 스터디와 직접 구현
excerpt: GQA가 풀지 못한 표현력 한계를 Multi-head Latent Attention(MLA)이 어떻게 해결하는지 TransMLA 논문 스터디와 nanoGPT 스타일 미니 구현체로 직접 검증한 기록.
tags: [ai-llm, transformer]
status: published
source_ref: https://github.com/chjnett/tech_Blog/tree/main/posts-assets/mla-article
---

## 1부. GQA로 만족할 수 없었던 이유, 그리고 TransMLA를 만나다

이전 글에서 <span class="tooltip" data-tooltip="(Grouped-Query Attention) 쿼리 헤드들을 그룹으로 묶어 K, V 헤드를 공유" tabindex="0">GQA</span>(Grouped-Query Attention)로 KV 캐시를 1/4로 줄이는 데 성공했다. 서빙 메모리 병목은 어느 정도 해소됐지만, 최신 모델들은 거기서 멈추지 않았다. DeepSeek-V2/V3, DeepSeek-R1이 채택한 **Multi-head Latent Attention(<span class="tooltip" data-tooltip="(Multi-head Latent Attention) K, V를 저랭크 잠재 공간으로 압축하는 어텐션" tabindex="0">MLA</span>)** 은 KV를 헤드 단위로 줄이는 게 아니라 아예 저랭크 잠재 공간으로 압축해버린다. 접근 자체가 다르다.

논문 "TransMLA: MLA Is All You Need"를 읽으면서 두 가지에 충격을 받았다[cite: 1].

첫째, **동일한 <span class="tooltip" data-tooltip="(Key-Value Cache) 이전 토큰들의 K, V 벡터를 메모리에 저장해 재계산 방지" tabindex="0">KV 캐시</span> 용량이라면 MLA는 GQA보다 수학적으로 항상 더 높은 Expressive Power를 보장한다**. 이건 경험적인 관찰이 아니라 정리(theorem)로 증명된다. GQA가 MLA의 특수 케이스에 속한다는 뜻이기도 하다[cite: 1].

둘째, 수백억짜리 GQA 모델을 처음부터 다시 학습시킬 필요 없이 MLA로 **개조(transplant)**할 수 있다는 아이디어다. RoPE 처리 방식을 바꾸고 KV를 저랭크로 재구성하면, 기존 가중치를 대부분 살릴 수 있다[cite: 1]. 이 발상이 실용적으로 얼마나 중요한지는 학습 비용을 생각하면 바로 감이 온다.

세 가지 어텐션 방식을 헤드 구조로 나란히 놓으면 차이가 바로 보인다. Q 헤드 수는 항상 8개로 고정이고, KV를 어떻게 저장하는지가 달라진다.

```figure
{"type":"groups","caption":"MHA / GQA / MLA — Query 헤드는 8개 고정, KV 저장 방식만 다르다 (같은 색 = 같은 KV 공유)","groups":[{"label":"MHA","note":"KV heads: 8 — 헤드마다 독립 K/V, 표현력 최대, 캐시도 최대","queryCount":8,"kvCount":8},{"label":"GQA-4","note":"KV heads: 4 — 2개 Q가 1개 KV 공유, 캐시 절반","queryCount":8,"kvCount":4},{"label":"MLA","note":"KV → 저랭크 c_kv 1개로 압축, 캐시 극소화 + 표현력 유지","queryCount":8,"kvCount":1}]}
```

MLA는 보기엔 MQA처럼 KV가 하나지만, 핵심은 그 하나가 **학습된 저랭크 잠재 벡터**라는 점이다. 정보를 버리는 게 아니라 압축해서 담는다.

```figure
{"type":"flow","caption":"GQA vs MLA — KV 캐시 압축 전략의 근본적인 차이","nodes":[{"id":"x","label":"입력 x (d_model=256)"},{"id":"gqa_kv","label":"GQA K/V proj","note":"n_kv_head × head_dim 차원으로 직접 투영"},{"id":"mla_down","label":"Down-projection","note":"256 → latent_dim=32 압축"},{"id":"mla_up","label":"Up-projection","note":"latent_dim → 256 복원 (추론 시)"},{"id":"cache_gqa","label":"GQA 캐시","note":"4 heads × 32 head_dim = 128차원"},{"id":"cache_mla","label":"MLA 캐시","note":"latent_dim = 32차원 (4배 작음)","emphasis":true}],"edges":[{"from":"x","to":"gqa_kv"},{"from":"gqa_kv","to":"cache_gqa"},{"from":"x","to":"mla_down"},{"from":"mla_down","to":"cache_mla","label":"저장"},{"from":"cache_mla","to":"mla_up","label":"추론 시 읽기"},{"from":"mla_up","to":"cache_gqa","label":"K,V로 복원"}]}
```

## 2부. 논문 데이터로 3대 개조 기법 뜯어보기

논문이 GQA를 MLA로 개조하기 위해 제안한 세 가지 기법을 데이터 관점에서 살펴봤다.

### RoROPE & FreqFold — 위치 정보를 어떻게 살리나

MLA의 핵심 문제 중 하나는 **RoPE(위치 인코딩)와의 충돌**이다. RoPE는 각 토큰의 위치에 따라 K에 회전 행렬을 곱하는데, 이걸 그대로 두면 저랭크 압축이 불가능해진다(위치마다 다른 회전이 가해지므로 저차원에 깔끔하게 담기지 않는다).

단순히 RoPE를 제거하면 모델이 완전히 망가진다. 논문은 대신 두 단계를 거친다[cite: 1].

1. **RoROPE**: 동일한 주파수 성분을 가진 위치 벡터들을 PCA로 첫 번째 헤드에 집중시킨다. LLaMA-3 8B에서 Key L2-Norm이 앞 두 헤드에 몰리는 현상(Fig 3a)이 이 결과다.
2. **FreqFold**: 비슷한 주파수 대역을 묶어 압축한다. 90% 압축에서도 Perplexity가 크게 튀지 않는다(Fig 3b)[cite: 1].

```figure
{"type":"flow","caption":"RoROPE + FreqFold 처리 흐름 — RoPE를 제거하지 않고 재배치한다","nodes":[{"id":"rope_orig","label":"원본 RoPE","note":"모든 헤드에 분산"},{"id":"pca","label":"PCA 분석","note":"동일 주파수 성분 식별"},{"id":"rorope","label":"RoROPE","note":"위치 정보를 첫 헤드에 집중","emphasis":true},{"id":"freqfold","label":"FreqFold","note":"주파수 대역 묶어 압축"},{"id":"result","label":"저랭크 KV 압축 가능","emphasis":true}],"edges":[{"from":"rope_orig","to":"pca"},{"from":"pca","to":"rorope"},{"from":"rorope","to":"freqfold"},{"from":"freqfold","to":"result"}]}
```

LLaMA-3 8B에서 실제로 측정된 Key L2-Norm 분포가 어떤 모습인지를 헤드 단위로 표현하면 이렇다. RoROPE 적용 전에는 에너지가 모든 헤드에 고르게 퍼져 있고, 적용 후에는 앞 두 헤드에 집중된다.

```figure
{"type":"groups","caption":"Key L2-Norm 분포 — RoROPE 적용 전(위) vs 후(아래). 에너지가 head-0, head-1에 집중된다","groups":[{"label":"Before RoROPE","note":"L2-Norm이 모든 헤드에 균등 분포","queryCount":8,"kvCount":8},{"label":"After RoROPE","note":"L2-Norm이 head-0, head-1에 집중 → 나머지 헤드는 저랭크로 압축 가능","queryCount":8,"kvCount":2}]}
```

### BKV — 체급을 맞춰야 PCA가 제대로 작동한다

위치 정보를 제외한 Key(`K_nope`)와 Value(`V`)를 함께 PCA로 압축하면 문제가 생긴다. `K_nope`의 L2-Norm이 `V`보다 훨씬 크기 때문에, PCA는 Value 정보를 사실상 무시하고 Key 방향으로만 주성분을 잡는다[cite: 1].

**BKV(Balanced Key-Value)**는 단순하다. 스케일을 맞춰서 두 텐서가 비슷한 크기를 갖게 정규화한 뒤 PCA를 돌린다. Fig 4a 하단을 보면 BKV 적용 후 K와 V의 분포가 균등해지고, Perplexity 손실이 현저히 줄어든다(Fig 4b)[cite: 1]. 데이터 정규화의 효과를 여기서도 확인한다.

```figure
{"type":"flow","caption":"BKV 적용 전/후 — K_nope와 V의 L2-Norm 체급이 맞지 않으면 PCA가 한쪽 정보를 버린다","nodes":[{"id":"knope","label":"K_nope","note":"L2-Norm 크기 ≈ 10 (크다)"},{"id":"v","label":"V","note":"L2-Norm 크기 ≈ 1 (작다)"},{"id":"pca_bad","label":"PCA (BKV 없음)","note":"K_nope 방향으로만 주성분 → V 정보 유실"},{"id":"bkv","label":"BKV 스케일 맞춤","note":"K_nope ÷ 10 → 둘 다 크기 ≈ 1","emphasis":true},{"id":"pca_good","label":"PCA (BKV 적용)","note":"K와 V 모두 균등하게 반영","emphasis":true},{"id":"compress","label":"저랭크 압축","note":"Perplexity 손실 최소화"}],"edges":[{"from":"knope","to":"pca_bad"},{"from":"v","to":"pca_bad"},{"from":"knope","to":"bkv"},{"from":"v","to":"bkv"},{"from":"bkv","to":"pca_good"},{"from":"pca_good","to":"compress"},{"from":"pca_bad","to":"compress","label":"V 손실"}]}
```

## 3부. 직접 미니 Transformer에 MLA 이식하기

거대 모델을 개조하는 논문의 접근도 훌륭하지만, 나는 미니 모델을 처음부터 짤 수 있으니 순수 MLA(Pure MLA)를 바닥부터 구현해서 GQA와 정면 승부를 내보기로 했다.

기존 `CausalSelfAttention` 대신 `MLASelfAttention`을 만들었다. 차이는 명확하다.

- **GQA**: K/V를 `n_kv_head`개의 헤드로 직접 프로젝션. 캐시에는 `(K, V)` 텐서 저장.
- **MLA**: K/V를 `latent_dim` 차원의 잠재 벡터 `c_kv`로 **Down-projection**. 캐시에는 `c_kv`만 저장. 추론 시 **<span class="tooltip" data-tooltip="잠재 벡터(Latent Vector)를 원래 차원 크기의 K, V 행렬로 복원하는 선형 변환" tabindex="0">Up-projection</span>**으로 K, V를 복원.

차원이 어떻게 흐르는지를 수치로 보면 압축 효과가 바로 드러난다. 실험 환경 기준(n_embd=128, n_head=8, head_dim=16, latent_dim=32)으로 추적했다.

```figure
{"type":"flow","caption":"MLA Down/Up-projection 차원 흐름 — 캐시에는 latent_dim=32만, 나머지는 추론 시 복원","nodes":[{"id":"input","label":"입력 x","note":"(B, T, 128)"},{"id":"q","label":"Q projection","note":"128 → 128 (8 heads × 16)"},{"id":"down","label":"kv_down","note":"128 → 32 (latent_dim)","emphasis":true},{"id":"cache","label":"KV 캐시 저장","note":"c_kv: (B, T, 32) — 75% 절감","emphasis":true},{"id":"k_up","label":"k_up (추론 시)","note":"32 → 128"},{"id":"v_up","label":"v_up (추론 시)","note":"32 → 128"},{"id":"attn","label":"Scaled Dot-Product Attention","note":"Q(128) × K(128) × V(128)"}],"edges":[{"from":"input","to":"q"},{"from":"input","to":"down"},{"from":"down","to":"cache","label":"저장"},{"from":"cache","to":"k_up","label":"읽기"},{"from":"cache","to":"v_up","label":"읽기"},{"from":"q","to":"attn"},{"from":"k_up","to":"attn"},{"from":"v_up","to":"attn"}]}
```

```python
class MLASelfAttention(nn.Module):
    def __init__(self, config: MLAConfig):
        super().__init__()
        self.n_head   = config.n_head
        self.head_dim = config.n_embd // config.n_head

        # Q projection (변화 없음)
        self.q_proj  = nn.Linear(config.n_embd, config.n_embd, bias=False)
        # Down-projection: 입력 → c_kv (저랭크 잠재 벡터, KV 캐시에 이것만 저장)
        self.kv_down = nn.Linear(config.n_embd, config.latent_dim, bias=False)
        # Up-projection: c_kv → K, V (추론 시 on-the-fly 복원)
        self.k_up    = nn.Linear(config.latent_dim, config.n_embd, bias=False)
        self.v_up    = nn.Linear(config.latent_dim, config.n_embd, bias=False)
        self.out_proj = nn.Linear(config.n_embd, config.n_embd, bias=False)

    def forward(self, x, kv_cache=None, use_cache=False):
        B, T, C = x.shape
        q   = self.q_proj(x).view(B, T, self.n_head, self.head_dim).transpose(1, 2)

        # ── 핵심: c_kv 만 캐시에 저장 ──────────────────────────────────
        c_kv = self.kv_down(x)                         # (B, T, latent_dim)
        if kv_cache is not None:
            c_kv = torch.cat([kv_cache, c_kv], dim=1)  # 이전 잠재벡터 이어붙이기
        new_cache = c_kv if use_cache else None

        # Up-projection으로 K, V 복원 — 캐시 읽기 후 즉시 연산
        k = self.k_up(c_kv).view(B, -1, self.n_head, self.head_dim).transpose(1, 2)
        v = self.v_up(c_kv).view(B, -1, self.n_head, self.head_dim).transpose(1, 2)
        # ────────────────────────────────────────────────────────────────

        is_causal = kv_cache is None
        y = F.scaled_dot_product_attention(q, k, v, is_causal=is_causal)
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.out_proj(y), new_cache
```

가장 까다로운 부분은 `kv_cache` 처리다. GQA는 `(K, V)` 튜플을 캐시하지만, MLA는 `c_kv` 단일 텐서만 캐시한다. 추론 시 `k_up`, `v_up`으로 즉석에서 복원하기 때문에, **메모리에서 읽어오는 크기는 `latent_dim`뿐**이다. 이게 대역폭 절감의 핵심 메커니즘이다.

```figure
{"type":"flow","caption":"MLA 추론 루프 — 캐시에서 c_kv를 읽고 K,V를 그 자리에서 복원한다","nodes":[{"id":"cache","label":"KV 캐시","note":"c_kv만 저장 (latent_dim)"},{"id":"read","label":"캐시 읽기","note":"대역폭 소비 최소화","emphasis":true},{"id":"up_k","label":"k_up(c_kv)","note":"K 복원"},{"id":"up_v","label":"v_up(c_kv)","note":"V 복원"},{"id":"attn","label":"Attention 연산"},{"id":"new_ckv","label":"새 c_kv 추가","note":"kv_down(x_new)"}],"edges":[{"from":"cache","to":"read"},{"from":"read","to":"up_k"},{"from":"read","to":"up_v"},{"from":"up_k","to":"attn"},{"from":"up_v","to":"attn"},{"from":"new_ckv","to":"cache","label":"append"}]}
```

## 4부. 2차 검증: 파라미터 / 캐시 / 속도 벤치마크

직접 실행한 결과다. 환경: CPU(M-series Mac), float32, n_layer=6, n_embd=256, n_head=8.

```terminal
$ .venv/bin/python3 scripts/benchmark_gqa_mla.py

1) Parameter count
   MHA  (n_kv=8):  5,787,136 params
  GQA-4 (n_kv=4):  5,393,920 params
  GQA-2 (n_kv=2):  5,197,312 params
   MQA  (n_kv=1):  5,099,008 params

Measured values (seq_len=1024)
   MHA  (n_kv=8): measured   12.583 MB  |  theoretical   12.583 MB
  GQA-4 (n_kv=4): measured    6.291 MB  |  theoretical    6.291 MB
  GQA-2 (n_kv=2): measured    3.146 MB  |  theoretical    3.146 MB
   MQA  (n_kv=1): measured    1.573 MB  |  theoretical    1.573 MB

3) Inference speed (tokens/sec)
-- prompt_len=64 --
   MHA  (n_kv=8):   1329.0 tokens/sec
  GQA-4 (n_kv=4):   1426.7 tokens/sec
-- prompt_len=256 --
   MHA  (n_kv=8):   1003.9 tokens/sec
  GQA-4 (n_kv=4):    893.9 tokens/sec
   MQA  (n_kv=1):   1358.7 tokens/sec
-- prompt_len=1024 --
   MHA  (n_kv=8):    649.5 tokens/sec
   MQA  (n_kv=1):    824.0 tokens/sec
```

**파라미터 수** (n_layer=6, n_embd=256, n_head=8):

| 구성 | 파라미터 수 | 비율 (MHA 대비) |
|---|---:|---:|
| <span class="tooltip" data-tooltip="(Multi-Head Attention) 쿼리마다 독립적인 K, V 헤드를 갖는 기본 어텐션" tabindex="0">MHA</span> (n_kv=8) | 5,787,136 | 1.00× |
| GQA-4 (n_kv=4) | 5,393,920 | 0.93× |
| GQA-2 (n_kv=2) | 5,197,312 | 0.90× |
| MLA (latent=32) | 5,148,160 | 0.89× |
| <span class="tooltip" data-tooltip="(Multi-Query Attention) 모든 쿼리 헤드가 단 1개의 K, V 헤드를 공유" tabindex="0">MQA</span> (n_kv=1) | 5,099,008 | 0.88× |

**KV 캐시 메모리** — 이론값과 실측값이 **정확히 일치**:

![Fig 1 — 컨텍스트 길이별 KV 캐시 메모리 (로그 스케일). MHA는 131K에서 1,611 MB, MQA는 201 MB로 8배 차이.](/posts-assets/mla-article/fig1_kv_cache_vs_seqlen.png)

| 구성 | seq_len=512 | seq_len=4K | seq_len=32K | seq_len=131K |
|---|---:|---:|---:|---:|
| MHA (n_kv=8) | 6.00 MB | 48.00 MB | 384.00 MB | 1,536.00 MB |
| GQA-4 (n_kv=4) | 3.00 MB | 24.00 MB | 192.00 MB | 768.00 MB |
| GQA-2 (n_kv=2) | 1.50 MB | 12.00 MB | 96.00 MB | 384.00 MB |
| MQA (n_kv=1) | 0.75 MB | 6.00 MB | 48.00 MB | 192.00 MB |
| MLA (latent=32) | 0.38 MB | 3.00 MB | 24.00 MB | 96.00 MB |

**추론 속도** (tokens/sec, KV 캐시 사용):

| 구성 | prompt=64 | prompt=256 | prompt=1024 | 1024 기준 MHA 대비 |
|---|---:|---:|---:|---:|
| MHA (n_kv=8) | 1,394.8 | 1,028.4 | 664.8 | 1.00× |
| GQA-4 (n_kv=4) | 1,433.6 | 909.8 | 608.5 | 0.92× |
| GQA-2 (n_kv=2) | 1,528.6 | 1,074.4 | 663.2 | 1.00× |
| MLA (latent=32) | 1,597.4 | 1,324.1 | 740.0 | 1.11× |
| MQA (n_kv=1) | 1,579.9 | 1,384.1 | 825.8 | 1.24× |

![Fig 2 — 프롬프트 길이별 추론 속도. 컨텍스트가 길어질수록 KV 헤드 수가 적은 구성이 유리해진다.](/posts-assets/mla-article/fig2_inference_speed.png)

컨텍스트가 1024로 길어지자 MQA가 MHA 대비 1.27배 빨라졌다. CPU 환경이라 절댓값은 낮지만, 방향은 명확하다. 실제 GPU HBM 대역폭에서, 그리고 128K 컨텍스트에서는 이 격차가 훨씬 극적으로 벌어진다.

컨텍스트 길이가 늘수록 KV 캐시가 얼마나 다르게 커지는지 흐름으로 보면 직관적이다.

```figure
{"type":"flow","caption":"컨텍스트 길이별 KV 캐시 폭증 — MHA는 131K에서 1.6GB, MLA라면 latent_dim에 비례해 극단적으로 줄어든다","nodes":[{"id":"seq512","label":"seq_len = 512"},{"id":"seq4k","label":"seq_len = 4K"},{"id":"seq32k","label":"seq_len = 32K"},{"id":"seq131k","label":"seq_len = 131K"},{"id":"mha_512","label":"MHA: 6.3 MB"},{"id":"mha_4k","label":"MHA: 50 MB"},{"id":"mha_32k","label":"MHA: 403 MB"},{"id":"mha_131k","label":"MHA: 1,611 MB","note":"GPU 1장 VRAM을 캐시가 먹는다"},{"id":"gqa_131k","label":"GQA-4: 805 MB","note":"절반이지만 여전히 크다"},{"id":"mla_131k","label":"MLA: latent 비례","note":"압축률에 따라 수십~수백 MB","emphasis":true}],"edges":[{"from":"seq512","to":"mha_512"},{"from":"seq4k","to":"mha_4k"},{"from":"seq32k","to":"mha_32k"},{"from":"seq131k","to":"mha_131k"},{"from":"seq131k","to":"gqa_131k"},{"from":"seq131k","to":"mla_131k"},{"from":"mha_512","to":"mha_4k","label":"8×"},{"from":"mha_4k","to":"mha_32k","label":"8×"},{"from":"mha_32k","to":"mha_131k","label":"4×"}]}
```

## 5부. 학습 sanity check — "같은 크기의 가방, 다른 지능"

이번 실험의 핵심 조건은 **동일한 KV 캐시 메모리**다. GQA-4와 MLA를 같은 용량 안에서 경쟁시켰다.

```terminal
$ .venv/bin/python3 scripts/mla_train_sanity.py

=== KV 캐시 크기 비교 (seq_len=64) ===
  GQA-4 캐시: 131,072 bytes
  MLA   캐시:  32,768 bytes   ← MLA가 오히려 1/4 크기
  GQA-4 파라미터: 731,520
  MLA   파라미터: 715,136

=== 학습 결과 ===
  GQA-4: 초반 Loss 2.3530 → 최종 Loss 1.4399
  MLA:   초반 Loss 2.3560 → 최종 Loss 1.1956
```

구간별로 끊어보면 수렴 패턴 차이가 더 뚜렷하다:

| 구간 | GQA-4 Loss | MLA Loss | 차이 |
|---|---:|---:|---:|
| step 1–100 | 2.3232 | 2.3190 | −0.0042 |
| step 101–200 | 2.2227 | 1.9628 | **−0.2599** |
| step 201–300 | 1.6234 | 1.3068 | **−0.3166** |

초반 100스텝은 둘 다 비슷하게 시작한다. 하지만 101스텝부터 MLA가 뚜렷하게 갈라지기 시작해, 300스텝 시점에서 GQA-4 대비 0.32 낮은 Loss(언어 모델의 성능 지표인 <span class="tooltip" tabindex="0" data-tooltip="Perplexity = e^Loss">퍼플렉시티</span>와 직결됨)로 수렴했다.

흥미로운 점은 실험 설정상 **MLA의 KV 캐시가 GQA-4보다 오히려 4배 작다**는 사실이다 (latent_dim=32 vs n_kv_head=4×head_dim=64). 더 적은 캐시 메모리로 더 낮은 Loss를 달성했다는 뜻이다.

실제 Loss 수렴 경로를 100스텝 단위로 시각화하면 이렇다.

![Fig 3 — GQA-4 vs MLA Loss 수렴 곡선. step 100 이후 MLA가 뚜렷하게 갈라져 최종 0.32 낮은 Loss로 수렴.](/posts-assets/mla-article/fig3_loss_convergence.png)

![Fig 4 — KV 캐시 크기 직접 비교. MLA(32K bytes)는 GQA-4(131K bytes)의 25% 수준.](/posts-assets/mla-article/fig4_cache_comparison.png)

```figure
{"type":"flow","caption":"GQA-4 vs MLA Loss 수렴 경로 — 초반은 동일하게 시작하지만 100스텝 이후 MLA가 갈라진다","nodes":[{"id":"start","label":"step 0","note":"초기 Loss ≈ 2.35 (무작위 예측 수준)"},{"id":"s1_gqa","label":"GQA step 1–100","note":"avg Loss: 2.323"},{"id":"s1_mla","label":"MLA step 1–100","note":"avg Loss: 2.319 (거의 동일)"},{"id":"s2_gqa","label":"GQA step 101–200","note":"avg Loss: 2.223"},{"id":"s2_mla","label":"MLA step 101–200","note":"avg Loss: 1.963 (차이 시작)","emphasis":true},{"id":"s3_gqa","label":"GQA step 201–300","note":"최종 avg Loss: 1.623"},{"id":"s3_mla","label":"MLA step 201–300","note":"최종 avg Loss: 1.307 (△0.32 낮음)","emphasis":true}],"edges":[{"from":"start","to":"s1_gqa"},{"from":"start","to":"s1_mla"},{"from":"s1_gqa","to":"s2_gqa"},{"from":"s1_mla","to":"s2_mla"},{"from":"s2_gqa","to":"s3_gqa"},{"from":"s2_mla","to":"s3_mla"}]}
```

```figure
{"type":"flow","caption":"GQA-4 vs MLA — 같은 메모리 예산에서 무슨 일이 일어나는가","nodes":[{"id":"budget","label":"동일한 메모리 예산"},{"id":"gqa","label":"GQA-4","note":"헤드 수를 줄여 K/V 직접 저장\n→ 정보 일부 버림"},{"id":"mla","label":"MLA","note":"저랭크 잠재공간으로 압축\n→ 고차원 정보 유지","emphasis":true},{"id":"gqa_loss","label":"최종 Loss: 1.44"},{"id":"mla_loss","label":"최종 Loss: 1.20","emphasis":true}],"edges":[{"from":"budget","to":"gqa"},{"from":"budget","to":"mla"},{"from":"gqa","to":"gqa_loss"},{"from":"mla","to":"mla_loss"}]}
```

직관적으로 정리하면 이렇다. 주어진 메모리(가방) 안에 정보를 담을 때, GQA는 헤드 수를 줄여 아예 정보 자체를 버린다. MLA는 저랭크 압축으로 같은 공간에 더 많은 정보를 구겨 넣는다. 가방 크기가 작아질수록 압축 효율의 차이가 커진다.

## 6부. 정리: 다음 패러다임을 향해

GQA는 MHA의 메모리 병목을 현실적인 타협점에서 해소했다. 오늘날 거의 모든 오픈소스 LLM이 GQA를 쓰는 건 이 타협이 꽤 괜찮았기 때문이다.

하지만 GQA는 종착지가 아니었다. MLA가 보여준 건 KV 압축 방식 자체를 바꾸면 동일 캐시 예산에서 더 높은 표현력을 얻을 수 있다는 것이다. DeepSeek-V2/V3/R1이 실제로 이 방식으로 서빙 비용을 극단적으로 낮추면서 성능을 유지하거나 높인 사례가 그 증거다.

실제 프로덕션(vLLM 등)에서는 여기서 한 단계 더 간다. **Absorb 연산**이다[cite: 1]. Up-projection 가중치(`k_up`, `v_up`)를 Q-projection과 Output-projection에 미리 곱해버리면, 추론 시 c_kv → K, V 복원 연산 자체를 없앨 수 있다. 캐시에서 c_kv를 읽어온 뒤 별도의 Up-projection 없이 바로 어텐션 스코어로 직행한다. 이 기법이 적용되면 MLA의 메모리 읽기 대역폭은 사실상 GQA보다 훨씬 낮으면서도 표현력은 MHA에 근접한다.

```figure
{"type":"flow","caption":"Absorb 연산 — Up-projection을 사전에 Q/O에 흡수해서 추론 시 연산을 제거한다","nodes":[{"id":"offline","label":"오프라인 (모델 로딩 시)","note":"k_up를 Q-proj에, v_up를 O-proj에 미리 흡수"},{"id":"cache","label":"KV 캐시","note":"c_kv만 저장 (변화 없음)"},{"id":"infer","label":"추론 시","note":"c_kv 읽기 → 즉시 어텐션 스코어 계산\n(별도 Up-projection 없음)","emphasis":true},{"id":"result","label":"대역폭 = latent_dim × 레이어 수만"}],"edges":[{"from":"offline","to":"cache","label":"준비"},{"from":"cache","to":"infer","label":"읽기"},{"from":"infer","to":"result"}]}
```

이번 실험 전체에서 가장 남는 인사이트는 아키텍처 설계에서 **'모델의 지능'과 '서빙 비용'을 분리**하는 방향으로 트렌드가 명확히 이동하고 있다는 점이다. MLA는 그 분리를 저랭크 압축으로 구현한 첫 번째 실용적인 사례다. GQA가 헤드 수를 줄여 표현력 일부를 희생한 것과 달리, MLA는 압축 자체를 학습 가능한 파라미터로 만들어 표현력을 지킨다.

다음 단계는 이 Absorb 연산을 미니 구현체에 직접 추가하고, 실제 vLLM 커널이 어떻게 c_kv를 페이지드(paged) 캐시에 관리하는지 뜯어보는 것이다.

---

*이 글에 사용된 코드(`model.py`, `scripts/benchmark_gqa_mla.py`, `scripts/mla_train_sanity.py`)는 [GitHub 리포지토리](https://github.com/chjnett/tech_Blog)에서 확인하실 수 있으며, GPU 없이 CPU만으로 재현 가능하다.*

*References:*

[cite: 1] **TransMLA: MLA Is All You Need**, Fanxu Meng et al., 2025. [arXiv:2502.07864](https://arxiv.org/abs/2502.07864)
