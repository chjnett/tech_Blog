---
slug: redis-lessons-applied-view-count-and-ranking
title: "조회수 카운터 실전 적용기 — Redis INCR을 배우고 Cloudflare KV로 직접 부딪혀 보니"
excerpt: Redis의 원자적 INCR/ZINCRBY를 공부한 뒤, 이 블로그에 조회수·인기 랭킹을 실제로 구현하며 "KV는 왜 원자 카운터를 못 주나"를 코드로 체험한 실전 적용 기록.
tags: [redis, backend, cloudflare]
status: published
---

지난 글에서 [Redis 자료구조](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-data-structures-and-production-patterns) 를 파고들며 "INCR은 원자적", "ZSet은 정렬+순위"를 **말로** 이해했다. 이번엔 그걸 **이 블로그에 실제로** 적용해봤다. 가정: 조회수 카운터와 인기글 랭킹.

그런데 이 블로그는 Cloudflare Workers다. 자체 Redis를 못 띄우니, 선택지는 **Cloudflare KV**였다. 결국 해답을 아는 상태에서 KV의 한계에 직접 부딪혔다 — 이 글이 "공부한 걸 실제로 쓰면서 느낀 것"의 기록이다.

```figure
{"type":"flow","caption":"아이디어 → 실제 구현 → 한계 체험","nodes":[{"id":"idea","label":"조회수 INCR?","note":"Redis라면 원자적"},{"id":"kv","label":"Cloudflare KV","note":"INCR 없음 · 강한 일관성 아님","emphasis":true},{"id":"rmw","label":"read-modify-write","note":"best-effort 카운터"},{"id":"rank","label":"랭킹","note":"ZRANGE 없어 자체 정렬"}],"edges":[{"from":"idea","to":"kv"},{"from":"kv","to":"rmw"},{"from":"rmw","to":"rank"}]}
```

## 1. Redis로 풀었다면 — INCR 한 줄

Redis를 쓸 수 있었다면 조회수는 이렇게 *너무나 간단*했다.

```terminal
$ redis-cli
127.0.0.1:6379> INCR post:redis-data:views
(integer) 1
127.0.0.1:6379> ZINCRBY ranking:popular 1 "redis-data"
"1"
```

- `INCR`은 **조회와 증가를 원자적으로** 한다 — 동시 요청 100개가 와도 카운터 손실이 없다.
- `ZINCRBY`는 점수 누적 + **정렬된 상태 유지**를 한 번에 한다 — `ZRANGE`로 상위 N을 바로 얻는다.

이 두 명령이 없는 KV에서, 같은 일을 하려면 골치 아파진다.

## 2. Cloudflare KV로 직접 구현하면서 느낀 한계

### 2a. 조회수 — read-modify-write (INCR이 없다)

KV에는 `get`/`put`만 있다. 그래서 조회수 +1은 **전체 값을 읽고, 하우 +1 해서 다시 쓴다**는 read-modify-write가 된다.

```js
// Cloudflare KV — INCR 없음 → read-modify-write
const prev = await KV.get(`views:${slug}`, 'json') || { views: 0 };
await KV.put(`views:${slug}`, JSON.stringify({ views: prev.views + 1, updatedAt: Date.now() }));
```

이때 문제: **KV는 강한 일관성이 아니다.** 두 인스턴스가 동시에 같은 값을 읽어 각자 `+1`을 쓰면 카운터가 하나만 오른다. 즉 "엄밀한 정확성"이 필요한 카운터에는 부적합하다. `INCR`이 하나의 명령으로 read+write+증가를 원자적으로 하는 것과 정반대.

### 2b. 랭킹 — ZSet이 없어 자체 정렬

`ZINCRBY`/`ZRANGE`가 없으니, "상위 N 인기글"을 얻으려면 **모든 글의 조회수를 읽어 자바스크립트로 정렬**해야 한다.

```js
// 모든 글 조회수 읽어 → 조회수 순 정렬 (ZRANGE 대신)
const items = await Promise.all(slugs.map(async (s) => ({ slug: s, views: await getViews(KV, s) })));
return items.sort((a, b) => b.views - a.views);
```

글이 수십 개면 문제없지만, 수천·수만 개가 되면 **"정렬된 상태로 유지하는 스토어(ZSet)"의 가치**가 절실해진다. 규모가 커질수록 Redis ZSet이 빛나는 지점이다.

## 3. 그래서 한계가 "학습"이 된다

이 구현이 훌륭한 건 기능이 동작해서가 아니라, **Redis가 왜 존재하는지 몸으로 느끼게** 해준다는 점이다.

| 관점 | Redis | Cloudflare KV |
|---|---|---|
| 카운터 | `INCR` — 원자적 | read-modify-write — 일관성 최선 |
| 랭킹 | `ZINCRBY`+`ZRANGE` | 전체 읽고 자체 정렬 |
| 일관성 | 강한(메모리) | **최종적(eventual)** |
| 적합 | 정확·원자·정렬 필요한 상태 | 읽기 많은 부트스트랩·플래그 |

핵심 깨달음: **"조회수 카운터"라는 요구를 Redis로 푸는 건 과잉이 아니라, 원자성 때문에 오히려 정석에 가깝다.** 다만 블로그 규모(글 수십 개, 동시성 낮음)에서는 KV의 read-modify-write도 실용적으로 충분해 "어느 쪽이 맞나"는 **정확성 요구도와 스케일**이 결정한다.

## 4. 이 블로그에 실제로 들어간 것

방금 [Redis 자료구조 글에서 배운 대로](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-data-structures-and-production-patterns), 이 블로그에 구현했다:

- 글 페이지(SSR) 진입 시 **조회수 +1** → 상단에 `👁 N` 표시
- `POST /api/posts/:slug/views` — 카운터 증가
- `GET /api/popular` — 조회수 순 **인기 랭킹**
- `GET /api/posts` 목록/상세에 `views` 포함

```terminal
$ curl -X POST .../api/posts/redis-data.../views
{"views": 3}          # read-modify-write 문++

$ curl .../api/popular
[ { "title": "Redis 자료구조의 내부를 이해...", "views": 12 }, ... ]
```

## 5. 결론

Redis의 INCR/ZSet을 "안다"는 것과 "그게 없을 때의 필요성을 체험한다"는 것은 다른 깊이다. 이번 적용으로:

- **INCR의 원자성**이 느낌이 아니라 이유로 남았다 (KV read-modify-write의 손실 가능성).
- **ZSet의 정렬 유지**가 필수가 되는 스케일을 알았다 (자체 정렬의 한계).
- "어느 저장소"보다 **요구사항(정확성·스케일)**이 정답이라는 원칙을 재확인했다.

이 글로 Redis 시리즈(개념 → 자료구조 → Semantic Cache → KV Cache → **실전 적용**) 가 하나의 완결된 학습 루프가 됐다. 만약 나중에 이 블로그의 트래픽이 커져 정확한 카운터가 필요해지면, 그때 [Upstash Redis](https://upstash.com)로 갈아타는 게 **그 깨달음을 실현**하는 순간이 될 것이다.
