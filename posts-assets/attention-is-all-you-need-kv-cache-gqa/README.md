# Attention Is All You Need: KV Cache & GQA

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-red.svg)

**Blog Post**: [chjnett.dev/posts/attention-is-all-you-need-kv-cache-gqa](https://chjnett.dev/posts/attention-is-all-you-need-kv-cache-gqa)

Transformer의 자기회귀(autoregressive) 디코딩에서 KV 캐시 병목을 직관적으로 이해하고, Multi-Head Attention(MHA), Grouped-Query Attention(GQA), Multi-Query Attention(MQA)을 실제로 비교 검증하는 미니 Transformer 구현체입니다.

## Overview

이 프로젝트는 다음 세 가지 질문에 답합니다:

1. **왜 KV 캐시가 병목인가?** — 디코딩 매 스텝마다 읽어야 하는 캐시 크기가 추론 속도를 결정한다
2. **GQA가 어떻게 다른가?** — 파라미터와 캐시 메모리를 줄이면서도 성능을 유지한다
3. **실제로 얼마나 차이가 나는가?** — 이론값과 실측값의 정확한 비교

## Key Features

- ✅ **MHA/GQA/MQA 완전 구현** — `n_kv_head` 파라미터 하나로 세 아키텍처 전환 가능
- ✅ **KV 캐시 지원** — 실제 서빙처럼 자기회귀 생성 구현
- ✅ **벤치마크 3종** — 파라미터 수, 캐시 메모리, 추론 속도 실측
- ✅ **CPU에서 재현 가능** — GPU 없이 완전한 검증
- ✅ **학습 sanity check** — 합성 데이터로 수렴성 확인

## Architecture

### Attention Variants

| 구성 | Query Heads | KV Heads | 특징 |
|------|------------|----------|------|
| **MHA** | 8 | 8 | 표현력 최대, 캐시도 최대 |
| **GQA** | 8 | 2~4 | 최적 트레이드오프 (LLaMA 2/3, Mistral 표준) |
| **MQA** | 8 | 1 | 캐시 최소, 품질 손실 우려 |

### Model Diagram

```
Input Sequence
     ↓
[Token Embedding + Positional Encoding]
     ↓
┌──────────────────────────────────┐
│  Decoder Block (6 layers)        │
│  ├─ CausalSelfAttention         │
│  │  ├─ Q: n_head projection     │
│  │  ├─ K: n_kv_head projection  │ ← 핵심: K/V 헤드 수만 줄임
│  │  └─ repeat_kv() broadcast    │
│  └─ MLP (FFN)                   │
└──────────────────────────────────┘
     ↓
[LayerNorm + LM Head]
     ↓
Output Logits
```

## Installation

### Requirements
- Python 3.8+
- PyTorch 2.0+ (CPU or GPU)

### Setup

```bash
# Clone or download this directory
cd attention-is-all-you-need-kv-cache-gqa

# Install PyTorch
pip install torch

# (Optional) For GPU support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## Usage

### 1. Benchmark (Parameter / Cache Memory / Inference Speed)

파라미터 수, KV 캐시 메모리 크기, 추론 속도를 MHA/GQA/MQA 간 비교합니다.

```bash
python benchmark.py
```

**Output Example:**
```
1) 파라미터 수
        MHA  (n_kv=8): 5,787,136 params
      GQA-4 (n_kv=4): 5,393,920 params
      GQA-2 (n_kv=2): 5,197,312 params
        MQA  (n_kv=1): 5,099,008 params

2) KV 캐시 메모리 (이론값, seq_len별)
-- seq_len=131072 --
        MHA  (n_kv=8):   262.14 MB
      GQA-4 (n_kv=4):   131.07 MB
      GQA-2 (n_kv=2):    65.54 MB
        MQA  (n_kv=1):    32.77 MB

3) 추론 속도 (tokens/sec)
-- prompt_len=1024 --
        MHA  (n_kv=8):    67.6 tokens/sec
      GQA-4 (n_kv=4):    56.2 tokens/sec
      GQA-2 (n_kv=2):    70.3 tokens/sec
        MQA  (n_kv=1):   110.5 tokens/sec
```

### 2. Training Sanity Check

합성 데이터로 MHA/GQA/MQA 모두 정상적으로 학습되는지 확인합니다.

```bash
python train_sanity_check.py
```

**Output Example:**
```
MHA  (n_kv=4): 최종 loss(마지막 30스텝 평균) = 1.0341
GQA-2 (n_kv=2): 최종 loss(마지막 30스텝 평균) = 1.2074
MQA  (n_kv=1): 최종 loss(마지막 30스텝 평균) = 1.0906
```

### 3. Custom Model Creation

```python
from model import MiniGPT, GPTConfig

# GQA 4개 그룹으로 구성
config = GPTConfig(
    vocab_size=65,
    n_layer=6,
    n_head=8,
    n_kv_head=4,      # ← n_head와 다르면 GQA / 같으면 MHA
    n_embd=256,
)

model = MiniGPT(config)
model.eval()

# 추론 (KV 캐시 사용)
prompt = torch.randint(0, 65, (1, 32))
output, kv_caches = model.generate(prompt, max_new_tokens=64)
```

## File Structure

```
.
├── model.py                  # Transformer 구현 (CausalSelfAttention, MiniGPT)
├── benchmark.py              # 파라미터/캐시/속도 벤치마크
├── train_sanity_check.py     # 합성 데이터 학습 검증
└── README.md                 # 이 파일
```

### model.py 핵심 클래스

```python
class CausalSelfAttention(nn.Module):
    """
    n_kv_head 파라미터로 MHA/GQA/MQA 전환 가능
    
    - n_kv_head == n_head:  MHA (원 Transformer)
    - n_kv_head < n_head:   GQA (그룹별 K/V 공유)
    - n_kv_head == 1:       MQA (전체 K/V 공유)
    """
```

## Results Summary

### KV Cache Memory Savings
LLaMA-7B 기준 (seq_len=128K, fp16):
- MHA: 62.50 GB
- GQA (8 heads): 15.62 GB (**75% 절감**)
- MQA: 1.95 GB (**97% 절감**)

### Inference Speed (Long Context)
프롬프트 길이 1024 토큰 생성 시:
- MHA: 67.6 tokens/sec
- MQA: 110.5 tokens/sec (**1.6배 개선**)

### Training Convergence
모든 구성이 정상적으로 수렴 (무작위 기준 loss 2.303 → ~1.0):
- MHA: 1.034 ✓
- GQA-2: 1.207 ✓
- MQA: 1.091 ✓

## Key References

| Paper | Year | Link | Topic |
|-------|------|------|-------|
| Attention Is All You Need | 2017 | [arXiv:1706.03762](https://arxiv.org/abs/1706.03762) | Transformer 원본 |
| Fast Transformer Decoding | 2019 | [arXiv:1911.02150](https://arxiv.org/abs/1911.02150) | Multi-Query Attention (MQA) |
| GQA: Training from Multi-Head | 2023 | [arXiv:2305.13245](https://arxiv.org/abs/2305.13245) | Grouped-Query Attention (GQA) |
| LLaMA 2: Open Foundation and Fine-Tuned Chat Models | 2023 | [arXiv:2307.09288](https://arxiv.org/abs/2307.09288) | GQA 채택 |

## Related Projects

- **[Llama.cpp](https://github.com/ggerganov/llama.cpp)** — Efficient LLM inference (KV cache optimization)
- **[HuggingFace Transformers](https://github.com/huggingface/transformers)** — GQA 구현 참고
- **[nanoGPT](https://github.com/karpathy/nanoGPT)** — 이 프로젝트의 영감

## Requirements

- Python 3.8+
- PyTorch 2.0+
- NumPy (for numpy timing proxy)
- ~100MB 디스크 공간

CPU에서 전체 실행: 3~5분
GPU 있을 경우: < 1분

## License

MIT License — 자유롭게 사용, 수정, 배포 가능합니다.

## Citation

이 코드를 인용하려면:

```bibtex
@misc{chjnett2024gqa,
  author = {Cheon, Hyeon-Jun},
  title = {Attention Is All You Need: KV Cache and GQA},
  year = {2024},
  howpublished = {Personal tech blog},
  url = {https://chjnett.dev/posts/attention-is-all-you-need-kv-cache-gqa}
}
```

## Contact & Discussion

- **Blog Post**: [chjnett.dev](https://chjnett.dev)
- **GitHub**: [github.com/chjnett](https://github.com/chjnett)
- **Email**: cheonhyeonjun583@gmail.com

---

**Last Updated**: 2024-08-05  
**Status**: Actively maintained
