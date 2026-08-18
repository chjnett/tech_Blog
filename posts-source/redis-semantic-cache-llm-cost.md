---
slug: redis-semantic-cache-llm-cost
title: LLM 서빙 비용을 줄이는 Semantic Cache — Redis Vector Search로 유사 질문 응답 캐싱하기
excerpt: 같은 의미를 가진 다른 말로 질문해도 LLM을 새로 호출하는 낭비를, 질문을 임베딩 벡터로 바꿔 Redis HNSW 인덱스로 유사 캐시를 찾는 Semantic Cache로 줄이는 구조. Redis 8의 Vector Set과 기존 FT.CREATE HNSW를 모두 정리한다.
tags: [ai-llm, redis]
status: draft
---

LLM을 프러덕션에 올리고 한 달쯤 지나면 어김없이 마주치는 값비싼 사실이 있다. **사용자들은 비슷한 말을 계속 묻는다.** "결제가 안 돼요", "결제 오류가 났는데요", "지불이 실패했어요" — 의미는 같지만 텍스트는 다른 질문들이 매번 LLM을 새로 호출하고, 그때마다 토큰 비용이 쌓인다. 이 글은 이 낭비를 **Semantic Cache**로 줄이는 방법이다.

이 글은 방금 다룬 [Redis를 서버리스 블로그에](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-serverless-the-role-of-key-value-store) 이어지는 내용이다. 저기서 "Redis는 원자 카운터·TTL·자료구조가 빛나는 곳"이라고 했는데, 여기서는 그 연장선으로 **Redis가 벡터 검색까지 할 수 있다는 것**을 보여준다.

```figure
{"type":"flow","caption":"LLM 직접 호출 vs Semantic Cache","nodes":[{"id":"q","label":"사용자 질문"},{"id":"emb","label":"임베딩","note":"텍스트 → 벡터"},{"id":"redis","label":"Redis Vector Search","note":"유사 질문 조회(HNSW)","emphasis":true},{"id":"hit","label":"유사 답변 발견","note":"캐시 히트 — LLM 스킵"},{"id":"llm","label":"LLM 호출","note":"미스 — 새 생성"},{"id":"store","label":"답변 저장","note":"임베딩+답변 캐싱"}],"edges":[{"from":"q","to":"emb"},{"from":"emb","to":"redis"},{"from":"redis","to":"hit","label":"≥ 0.93"},{"from":"redis","to":"llm","label":"< 0.93"},{"from":"llm","to":"store"},{"from":"store","to":"redis"}]}
```

## 1. 문제 — "같은 뜻"이 다른 텍스트라 캐시가 안 걸린다

일반 캐시는 `key = 질문 원문`이다. 그런데 "결제 오류"와 "지불 실패"는 문자열이 다르므로 완전히 다른 key가 되고 **캐시 미스**가 난다. LLM 호출을 줄이려면 "문자열 일치"가 아니라 **"의미 일치"** 로 캐시를 찾아야 한다.

이걸 가능하게 하는 게 **임베딩(embedding)** 이다. 문장을 고정 차원(예: 1536차원)의 벡터로 변환하면, 의미가 비슷한 문장은 벡터 공간에서 가까운 위치에 온다. 그러면 "벡터 유사도가 높은 저장된 질문 → 그때 저장한 답변"을 재사용할 수 있다.

```
"결제가 안 돼요"  →  [0.12, -0.31, ...]   (임베딩)
"지불이 실패했어요" → [0.13, -0.29, ...]   거의 같은 방향 → 유사
```

## 2. Redis가 벡터를 검색하는 두 가지 방식

### 2a. 전통적 — Redis Stack의 FT.CREATE + HNSW (지금도 표준)

Redis Stack의 검색 인덱스에 벡터 필드를 만들고 **HNSW**(계층적 탐색 가능한 작은 세계 그래프) 인덱스를 건다. `KNN` 쿼리로 유사 벡터를 찾는다.

```
FT.CREATE cache_idx ON HASH PREFIX 1 "sem:" SCHEMA
  question TEXT
  embedding VECTOR HNSW 6 TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE
```

`HNSW`(Hierarchical Navigable Small World)는 **대략적 최근접 이웃(ANN) 알고리즘**으로, 고차원 벡터를 모든 점과 비교하지 않고 계층적 그래프로 탐색해 **정확도는 거의 유지하면서 검색 시간을 크게 줄인다.** 대규모 캐시에서 중요하다.

쿼리는 텍스트 + 벡터 하이브리드로:

```
FT.SEARCH cache_idx "*=>[KNN 10 @embedding $vec AS score]"
    PARAMS 2 vec "0.13,-0.29,..." DIALECT 2
```

유사도 점수(`score`, 코사인 거리)가 임계값(예: 0.93) 밖이면 캐시 히트로 보고, 저장된 답변을 그대로 반환한다.

### 2b. 신규 — Redis 8의 Vector Set + Query Engine (한결 가벼움)

Redis 8부터는 검색 인덱스 없이 **벡터 집합(Vector Set)** 을 만들어 쿼리 엔진으로 직접 검색할 수 있다. 별도 스키마/FT.CREATE가 필요 없어서 Semantic Cache처럼 단순 용도에 더 적합하다.

```
VS.CREATE vs_embedding TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE

VS.COPY /sem:결제가안돼요 destination $ to vs_embedding
...
VS.QUERY vs_embedding K 5 "0.13,-0.29,..."
```

둘 다 목적은 같다: **"이 질문과 의미가 가까운 저장된 질문이 있나?"** 를 벡터로 답한다.

## 3. 파이썬으로 만든 Semantic Cache (개념 구현)

실제 흐름은 이렇게 된다.

```python
import redis
from sentence_transformers import SentenceTransformer

r = redis.Redis(credentials=...)
model = SentenceTransformer("BAAI/bge-m3")   # 임베딩 모델

def chat(question: str) -> str:
    vec = model.encode(question).astype("float32").tobytes()

    # 1) 유사 질문이 캐시에 있는지
    res = r.ft("cache_idx").search(
        Query("*=>[KNN 5 @embedding $vec AS score]")
        .params(vec=vec).dialect(2)
    )
    if res.docs and float(res.docs[0].score) >= 0.93:
        return res.docs[0].answer            # 캐시 히트 — LLM 안 부름

    # 2) 미스 → LLM 호출
    answer = llm_complete(question)

    # 3) 결과 캐싱 (동일 질문 재사용 + 임베딩 저장)
    r.hset(f"sem:{question}", mapping={"question": question, "answer": answer})
    r.hset("sem:" + question, "embedding", vec)
    return answer
```

임계값(0.93)이 성능-비용 트레이드오프의 핵심이다. 낮추면 히트율↑(비용↓)이지만 엉뚱한 답을 줄 위험이, 높이면 정확하지만 히트율이 떨어진다. **도메인·QA페어로 실측해서 튜닝**해야 한다.

## 4. 트레이드오프 — 함부로 "80%"라고 못 박지 말자

"80% 비용 절감"은 자주 인용되지만 **모든 케이스에 성립하진 않는다.** 히트율이 그만큼 나오려면:

- **질문 분포가 반복적**(QA/고객센터/FAQ)이어야 한다. 매번 새로운 질문만 오면 캐시 이점이 없다.
- **답변이 질문에만 결정**돼야 한다. 사용자별 컨텍스트가 답을 바꾸면 캐시가 유해할 수 있다.
- 임베딩 호출 비용도 포함해야 한다. `bge-m3` 같은 오픈 모델은 로컬이니 싸지만, 클라우드 임베딩 API는 토큰 비용이 든다.

실측 예시로, **반복 질문이 60% 이상인 QA 도메인**에서 임계값 0.93을 쓰면 히트율 50~70% → **LLM 호출 감소로 토큰 비용 50~80% 절감**이 나올 수 있다. 다만 이 수치는 자기 데이터로 측정했을 때만 신뢰할 수 있다.

## 5. TTL — 캐시가 오래되면 자동으로 버리자

답변이 영원히 유효하진 않다(제품 정책이 바뀌면 답이 달라진다). 그래서 Semantic Cache는 **TTL과 결합**해야 한다.

```python
r.expire(f"sem:{question}", 86400)   # 24시간 뒤 자동 삭제
```

이렇게 하면 "Redis의 핵심 장점 = TTL 자동 만료"까지 Semantic Cache에서 그대로 쓸 수 있다. 캐시가 낡아 틀린 답을 주는 문제를 방지한다.

## 6. 이 블로그(RAG 시리즈)에서의 위치

이전 [industrial 멀티모달 RAG](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/industrial-rag-multimodal)는 "검색 → 증강"을, 이 글은 **"반복 질문을 얼마나 안 부르게 하느냐"** 를 다룬다. 흐름으로 보면:

```figure
{"type":"flow","caption":"RAG → 캐싱 → 최적화","nodes":[{"id":"rag","label":"RAG","note":"문서 검색+증강"},{"id":"sc","label":"Semantic Cache","note":"유사 질문 재사용","emphasis":true},{"id":"kv","label":"KV/TTL","note":"핫 응답 트래픽 분산"}],"edges":[{"from":"rag","to":"sc"},{"from":"sc","to":"kv"}]}
```

RAG가 **정확도를** 높인다면, Semantic Cache는 **비용·지연을** 줄인다. 둘은 같은 팀이다.

## 마무리

Semantic Cache는 "같은 의미의 다른 질문"이라는 **LLM 서빙의 기술적 특징**과 Redis의 **벡터 검색(HNSW) + TTL**을 붙인, 아주 자연스러운 최적화다. 핵심은:

- 질문을 **임베딩 벡터**로 바꿔 의미 유사도를 캐시 키로 쓴다
- Redis가 **HNSW ANN 검색**으로 유사 질문을 빠르게 찾고, TTL로 낡은 답을 버린다
- **"80% 절감"은 도메인이 반복적일 때** 실측으로만 신뢰 가능하다

다음 글에서 이어질 자연스러운 주제는 **Transformer의 KV Cache vs 데이터베이스 KV Store** — 이름은 같지만 구조가 완전히 다른 두 "캐시"를 대조하는 CS 기반 포스팅이 될 수 있다. [GQA/MLA 글](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/mla-article)과 짝을 이룬다.

> 참고 자료: [Redis Vector Search getting-started](https://redis.io/tutorials/howtos/solutions/vector/getting-started-vector.md) · [Redis 8 Vector Sets](https://redis.io/blog/redis-8-brings-vector-sets-and-is-now-in-preview-on-redis-cloud-essentials.md) · [Redis Stack Vectors](https://redis-stack.io/docs/interact/search-and-query/advanced-concepts/vectors/)
