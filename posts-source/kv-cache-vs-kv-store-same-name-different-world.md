---
slug: kv-cache-vs-kv-store-same-name-different-world
title: "Transformer의 KV Cache vs 데이터베이스의 KV Store: 이름만 같고 뭐가 다를까"
excerpt: 어텐션 추론의 VRAM을 점유하는 KV Cache와 백엔드 분산 KV Store(Redis 등)가 "Key-Value"라는 이름만 같고 구조·목적·수명이 어떻게 다른지, 기존 GQA/MLA 글과 이어지는 CS+AI 융합 대조 분석.
tags: [ai-llm, transformer, redis]
status: draft
---

딥러닝을 하다 백엔드로 넘어오면, 어디선가 TV 본 "KV"라는 단어를 두 번째 만난다. 어텐션에서는 **KV Cache**(Key-Value Cache)가 GPU VRAM을 잡아먹어 메모리가 터지고, 백엔드에서는 **KV Store**(Redis 같은 Key-Value 스토어)가 실제 서비스를 가볍게 만든다. 이름이 같아서 헷갈리지만, 사실 **둘은 "Key-Value"라는 낱말 외에 거의 공유하는 게 없다.**

이 글은 이 블로그 두 개의 축 — [GQA/MLA 어텐션 시리즈](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/mla-article)와 [Redis/KV 시리즈](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-serverless-the-role-of-key-value-store) — 를 **한 자리에서 대조**한다.

```figure
{"type":"compare","caption":"둘 다 'Key-Value'지만 세계가 다르다","nodes":[{"id":"attn","label":"KV Cache","note":"GPU VRAM · 어텐션 추론"},{"id":"db","label":"KV Store","note":"분산 서버 · Redis/RocksDB"}],"edges":[{"from":"attn","to":"db"}]}
```

## 1. 어텐션의 KV Cache — "재계산을 피하려는" 생성기 무기

Transformer 디코더는 토큰을 하나씩 생성한다. `n`번째 토큰을 만들려면 이전 `1..n-1` 토큰의 **Key/Value 벡터가 다시 필요**하다. 매 토큰마다 전부 재계산하면 비용이 제곱으로 늘어나서, 실제 서빙 시스템은 이 K/V를 **GPU 메모리에 저장**해두고 재사용한다. [GQA/MLA 글](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/mla-article)에서 다룬 어텐션 최적화들이 바로 이 KV Cache의 크기를 줄이는 싸움이다.

```python
# 어텐션 KV Cache: GPU VRAM에 저장되는 텐서 (Key, Value)
# shape: [batch, num_heads, seq_len, head_dim] — 시퀀스가 길어질수록 커짐
cache_k.populate(seq_len=n)   # 새 토큰의 K
cache_v.populate(seq_len=n)   # 새 토큰의 V
```

핵심 특징: **짧은 수명(한 세션이 끝나면 버림), 매우 큰 단위(수 GB 텐서), 하드웨어(GPU) 밀착.**

## 2. 데이터베이스의 KV Store — "빠른 읽기/쓰기"를 위한 영속 스토어

반면 Redis 같은 KV Store는 **디스크/네트워크 위에서 key→value를 빠르게 조회**하려는 목적이다. "이 query에 이 답변" 같은 **(문자열, 문자열)** 쌍을 저장해 읽기 지연을 낮춘다. 앞선 [Semantic Cache 글](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-semantic-cache-llm-cost)처럼, 심지어 벡터까지 저장해 유사 검색에도 쓴다.

```terminal
$ redis-cli
127.0.0.1:6379> SET "greeting:en" "hello"
OK
127.0.0.1:6379> GET "greeting:en"
"hello"
```

핵심 특징: **수명이 길고(영속 가능), 단위가 작고(문자열/벡터), CPU/메모리(호스트) 밀착, 동시성/원자성이 중요.**

## 3. 같은 이름, 다른 세계 — 대조표

| 축 | Transformer KV Cache | DB KV Store (Redis) |
|---|---|---|
| **내용물** | 고차원 텐서 (K/V 벡터) | 문자열·해시·벡터 (실제 서비스 데이터) |
| **어디서** | GPU VRAM | 호스트 RAM/디스크 (분산) |
| **크기** | 한 계층이 수 GB | 항목이 작음 (수십 B~수 KB) |
| **수명** | 한 추론 세션(짧음) | 영속/장기 (TTL로 제어) |
| **필요 조건** | 시퀀스 길이/헤드 | 일관성/원자성/지연 |
| **"캐시"인가?** | 재계산 방지용 캐시 | 기본은 스토어 (캐시도 됨) |
| **최적화 목표** | 메모리 압축 (GQA/MLA) | 낮은 지연·높은 처리량 |

## 4. 그래서 왜 이렇게 다른가 — 근본은 "제거 대상"이 다르다

두 캐시가 다른 이유는 한 문장으로 요약된다. 어텐션 KV Cache는 **"재계산 비용"** 을 없애고, DB KV Store는 **"디스크/네트워크 접근 비용"** 을 없앤다. 즉:

- KV Cache: **계산(compute)** 이 병목 → 메모리에 텐서를 잡아 재계산을 피한다. 문제는 "얼마나 많은 텐서를 얼마나 오래 들고 있느냐".
- KV Store: **접근(latency/I/O)** 이 병목 → 메모리에 데이터를 올려 디스크/네트워크를 피한다. 문제는 "얼마나 일관되고 원자적으로 읽고 쓰느냐".

같은 "캐시"라는 단어여도, 이것이 **컴퓨트 캐시**냐 **데이터 캐시**냐에 따라 해결해야 할 구조가 정반대가 된다.

```figure
{"type":"flow","caption":"각자 푸는 병목이 다르다","nodes":[{"id":"attn","label":"KV Cache","note":"재계산(compute) 병목 → 메모리에 텐서 유지"},{"id":"db","label":"KV Store","note":"접근(latency) 병목 → 메모리에 데이터 유지"},{"id":"goal","label":"최적화 방향","note":"압축(GQA/MLA) vs 분산·원자성"}]}
```

## 5. 실제로 섞이는 곳 — Semantic Cache는 두 세계의 교차점

흥미로운 건, [Semantic Cache](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-semantic-cache-llm-cost)는 **두 개념이 만나는 지점**이라는 점이다. LLM이 만들어낸 "산출물"을 Redis(KV Store)에 저장해, LLM을 다시 안 돌린다. 이는:

- KV Cache가 "다음 토큰 재계산을 피하는" 것과 유사한 발상이되,
- 저장 매체는 GPU 텐서가 아니라 **Redis의 문자열/벡터**

즉 **컴퓨트 캐시의 아이디어를 데이터 캐시의 저장소로 구현**한 셈이다. 이 대조가 가능해진 건 "KV"라는 개념이 두 축에서 모두 쓰이기 때문이다.

## 마무리

"KV"라는 세 글자에 두 개의 완전히 다른 시스템이 숨어 있다. 어느 쪽을 하든, **자기가 다루는 KV가 컴퓨트 캐시인지 데이터 캐시인지**를 먼저 구분해야 한다. 그래야:

- 어텐션 KV Cache는 **메모리 압축**(GQA/MLA)으로
- DB KV Store는 **지연/원자성**(Redis)으로
- 그리고 그 사이의 LLM서빙 최적화는 **Semantic Cache**로

각자 올바른 최적화를 고를 수 있다. 이 글로 이 블로그의 두 시리즈(어텐션 최적화 + 서버리스 저장소)가 하나로 이어진다.
