---
slug: shopping-mall-image-worker-optimization
title: 쇼핑몰 이미지 Worker를 실제로 뜯어보며 — R2 업로드만 하고 '최적화'는 아직 안 했다
excerpt: 직접 운영 중인 쇼핑몰 4곳의 이미지 처리 Worker(Cloudflare Workers + R2) 두 개를 실제 코드로 비교해보니, 둘 다 '업로드+서빙'까지만 구현돼 있고 리사이즈·WebP·CDN 캐시 최적화가 빠져 있었다. 그 '안 한 것'을 블로그의 캐시 시리즈 관점에서 분석한다.
tags: [cloudflare, backend, worker]
status: published
---

운영 중인 쇼핑몰 몇 곳이 Cloudflare Workers 기반으로 돌아간다. 트래픽은 하루 수만 건이지만, 그중 **이미지가 차지하는 비중**이 크다. 쇼핑몰에서 이미지는 상품을 팔고, 페이지 무게를 결정한다. 그래서 "이미지를 어떻게 서빙하느냐"가 사실은 퍼포먼스의 핵심인데, 실제 워커 코드를 열어보니 두 곳 모두 **"업로드 + R2 저장 + 그대로 반환"**까지만 되어 있고 '최적화'는 이름뿐이었다.

이 글은 그 실제 워커 두 개를 비교하고, 빠진 최적화(리사이즈·WebP·CDN 캐시)를 블로그에서 다룬 [캐시/Redis 시리즈](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-data-structures-and-production-patterns) 관점으로 짚는다.

```figure
{"type":"compare","caption":"쇼핑몰 이미지 Worker A와 B — 원리는 같고 구현 프레임워크만 다르다","nodes":[{"id":"m","label":"Worker A","note":"순수 Workers fetch"},{"id":"a","label":"Worker B","note":"Hono + GET 서빙"}],"edges":[]}
```

## 1. 실제 코드 — 공통 원리

두 워커는 프레임워크가 달라도 본질은 같다: **다중 파트 폼 → MIME 검증 → R2에 put**.

Worker A (순수 Workers):
```ts
const file = formData.get('file')
if (!ALLOWED_MIME_TYPES.has(file.type)) return json(..., 415)
const key = `uploads/${Date.now()}-${crypto.randomUUID()}.${ext}`
await env.IMAGE_BUCKET.put(key, bytes, {
  httpMetadata: { contentType: file.type, cacheControl: 'public, max-age=31536000, immutable' },
})
```

Worker B (Hono):
```ts
const mimeType = file.type.toLowerCase()
if (!ALLOWED_MIMES.includes(mimeType)) return c.json({...}, 400)
const key = `images/${crypto.randomUUID()}.${ext}`
await BUCKET.put(key, arrayBuffer, { httpMetadata: { contentType: mimeType, cacheControl: 'public, max-age=31536000' } })
```

눈에 보이는 차이는 **Worker B가 `GET /images/:filename` 서빙 라우트를 갖는다**는 것. Worker A는 업로드만 하고, public URL(게이트웨이/CDN)을 외부에 맡긴다.

## 2. 정작 없는 것 — '최적화'라는 이름이 안 하는 일

이름은 `image-optimizer`인데, 실제로는:

| 작업 | Worker A | Worker B | 이것이 왜 중요한가 |
|---|---|---|---|
| 업로드/서빙 | ✅ | ✅ | 기본 |
| **리사이즈(다운스케일)** | ❌ | ❌ | 원본 4000px 그대로 전송 → 무거움 |
| **WebP/AVIF 변환** | ❌ | ❌ | JPEG 유지 → 더 큰 바이트 |
| **CDN 캐시 헤더 조절** | 일부 | 일부 | 만료는 `immutable`이지만 히트가 안 나면 무용 |
| 원본 품질 제어(quality) | ❌ | ❌ | 대역폭·저장 낭비 |

결국 **원본 이미지가 그대로 CDN을 통해 내려간다.** 쇼핑몰에서 상품 이미지가 수 메가면, 모바일에서는 그게 곧 로딩 지연이다.

## 3. 빠진 것 중 하나가 내 블로그의 조회수 문제와 닮았다

방금 [조회수/랭킹 적용 글](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-lessons-applied-view-count-and-ranking)에서 "KV의 read-modify-write"가 Redis `INCR`과 다른 이유를 코드로 봤다. 이미지도 비슷하다. **"업로드만 하고 최적화를 안 하면, 아무것도 최적화 안 하는 것"** — 기능이 동작한다는 것과 무거운 모바일 페이지를 만드는 것은 다른 문제다.

또 이 블로그의 [Redis 자료구조 글](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-data-structures-and-production-patterns)에서 다룬 `cache-aside`·`TTL` 원리가 이미지 CDN에도 그대로 적용된다: **`Cache-Control: public,max-age=...` 를 정확히 주고, 리사이즈 버전마다(가로 400/800/1600) 캐시를 나눠** CDN 히트율을 높이는 것.

## 4. 개선 방향 — Cloudflare 이미지 최적화(또는 Workers에서)

한 가지 확실한 해법: **Cloudflare 자체 이미지 최적화 기능**을 붙이면, 별도 Worker 로직 없이 `cf-image` 크기/품질 인자로 리사이즈·WebP를 CDN 에지에서 한다.

```
https://cdn.domain.com/uploads/abc.jpg?width=400&quality=75&format=webp
```

또는 Workers에서 직접 (엣지에서 libvips/Sharp류) 처리해 리사이즈 후 R2에 파생본(derivative)으로 저장하고, 그냥 재계산하지 않도록 **이미 저장된 파생본을 재사용**한다 — Redis/KV의 `cache-aside` 패턴과 구조가 같다.

```
원본(원본만 R2) 
   → 요청 width/format마다 파생본 생성
   → 파생본 저장(동일 인자는 재사용)
   → CDN 캐시 헤더로 히트 유도
```

이 구조는 정확히 [Semantic Cache](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-semantic-cache-llm-cost)에서 본 "재계산을 피하려 (이미 계산한 답을 재사용)" 발상의 이미지 버전이다.

## 5. 결론 — "기능은 되지만 '최적화'는 아니다"

운영 중인 워커를 실제로 뜯어보니, 이미지 워커는 **안전하게 업로드·서빙하는** 좋은 기반이지만, 트래픽이 커질수록 원본 전송이 병목이 되는 지점이었다. 개선 포인트는 명확하다:

- **리사이즈 + WebP/AVIF + 품질 제어** → 전송 바이트를 수십 % 줄임
- **파생본 재사용(cache-aside) + CDN 캐시 헤더** → 위의 [캐시 시리즈](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-lessons-applied-view-count-and-ranking) 원리를 이미지에 적용
- 캐시 히트율(지금 ~16%)이 낮은 건, "만료 헤더만 있고 실제 리소스별 캐시 분기가 없다"는 현실을 반영한다

이만큼 다듬으면, 이름대로 "이미지를 최적화하는" 워커가 된다. 이 글이 그 **현실 진단**이다.
