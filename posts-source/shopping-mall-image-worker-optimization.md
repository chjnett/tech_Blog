---
slug: shopping-mall-image-worker-optimization
title: 외주 쇼핑몰의 이미지 Worker를 뜯어보며 — "업로드만 하고 최적화는 아직 안 했다"
excerpt: 외주로 운영하는 쇼핑몰 사이트들의 이미지 처리 Worker(Cloudflare Workers + R2) 실제 코드를 비교 분석해보니, 관리자 업로드 시 브라우저 1차 WebP 변환은 있지만 서버 리사이즈·파생본 저장·CDN 캐시 분기가 아직 없다. 그 '안 한 것'의 영향과 최적화 로드맵을 실측 수치로 정리한다.
tags: [cloudflare, backend, worker, optimization]
status: published
---

외주로 받아 운영하는 쇼핑몰 사이트 몇 곳이 Cloudflare Workers 기반으로 돌아간다. 이번에 그중 이미지 처리 Worker의 실제 코드를 열어보고, 아키텍처 문서와 트래픽 수치까지 함께 살펴봤다. 쇼핑몰에서 **이미지는 상품을 팔고, 페이지 무게를 결정**한다. 그런데 정작 Worker 코드는 "업로드 + R2 저장 + 그대로 반환"까지만 있고, 이름이 `image-optimizer`인데 **최적화라 할 만한 건 브라우저 쪽 1차 변환이 거의 전부**였다.

이 글은 그 실제 코드·문서·트래픽을 근거로, "지금 뭐가 돼 있고, 빠진 게 무엇이고, 얼마나 아낄 수 있는지"를 정리한다. 쇼핑몰 식별 정보는 비공개로 두고 기술 내용만 담는다.

```figure
{"type":"compare","caption":"외주 쇼핑몰 이미지 Worker 2곳 — 원리는 같고 프레임워크만 다르다","nodes":[{"id":"a","label":"Worker A","note":"순수 Workers fetch"},{"id":"b","label":"Worker B","note":"Hono + GET 서빙"}],"edges":[]}
```

## 1. 외주 사이트의 실제 아키텍처

외주 사이트들은 스택이 조금씩 달랐다:

| 사이트 | 스택 | 포인트 |
|---|---|---|
| 사이트 X | **Next.js + Supabase**(Postgres+Storage) | 이미지 최적화 유료 한도 초과, CPU 부하 |
| 사이트 Y | **Cloudflare 단일**: Workers+D1+R2 | API/권한/이미지/DB 전부 CF |

**사이트 Y** (Cloudflare 단일)의 이미지 Worker가 이 글의 핵심이다. 반면 **사이트 X**는 Supabase Storage의 이미지 최적화를 URL 파라미터(`?width=400&quality=75`)로 쓰고 있어, 어느 쪽이 이미지를 어디서 최적화하는지가 사이트마다 달라진다. 이 **파편화** 자체가 외주 작업의 특징이다.

## 2. 실제 코드 — 관리자 업로드 흐름

사이트 Y의 이미지 Worker는 관리자(Admin)가 업로드하는 이미지를 받아 R2에 저장한다.

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

차이는 **Worker B가 `GET /images/:filename` 서빙 라우트**를 갖는 것뿐, 둘 다 핵심은 "MIME 검증 + 원본 그대로 R2 저장"이다.

> **외주 특징**: 
> - 둘 다 `x-admin-key`** 헤더 인증 + 허용 도메인 CORS(`ALLOWED_ORIGINS`)
> - 관리자 키는 하드코딩 금지 → `wrangler secret put`으로 주입
> - 보안 관리는 잘 돼 있다 (원본 저장만 빼고)

## 3. 클라이언트(브라우저)는 이미 1차 최적화를 한다

흥미로운 건, **이미지 워커가 아니라 프론트에서 이미 최적화를 시도**하고 있다는 점이다. 실제 구현 문서(`image-optimization-implementation.md`)에 따르면:

- 관리자가 이미지를 선택하면 **브라우저에서 1차 WebP 변환**(최대 너비 1600px, 품질 0.82 기본)
- 목표 용량(450KB)을 향해 **품질/해상도를 단계적으로 낮춰** 반복 압축
- 그 결과를 Image Worker에 올림

```
관리자 이미지 선택
  → 브라우저 1차 최적화 (WebP, ≤1600px, q 0.82)
  → 450KB 목표까지 반복 압축
  → Image Worker 업로드 (MIME 검증 + R2 put)
```

이 접근은 "브라우저에서 미리 줄여 **서버 연산 비용을 피하자**"는 실용적 선택이다. 하지만 한계가 있다: **기기가 다르고, 원본이 트래픽마다 재전송되지 않도록 서버에서도 파생본을 정책으로 관리해야** 한다.

## 4. 정작 빠진 것 — 서버 파생본·CDN 캐시 분기

문서의 설계 목표는 명확했지만 **아직 구현은 초기다**. 저장 정책은 이렇게 설계돼 있었다:

| 파생본 | 규격 | 용도 |
|---|---|---|
| `thumb` | 너비 400px, WebP q=75 | 목록 썸네일 |
| `detail` | 너비 1200px, WebP q=82 | 상세 이미지 |
| `zoom` | 너비 2000px, WebP q=88 | 확대 보기 |
| `original` | (선택) TTL 7~30일 후 자동 삭제 | 필요 시에만 |

그런데 현재는 **`detail` 하나만 저장**되어 `thumb`/`zoom`은 만들어지지 않고, `original` TTL 자동 삭제도 아직 적용 전이다. 즉 "파생본 최소화 + 중복 방지(SHA-256 해시) + 캐시 헤더"는 **설계는 됐지만 실행은 안 된** 상태다.

![원본 대비 최적화와 파생본 저장 정책](/posts-assets/shopping-mall-image-worker/fig1_org_vs_optimized.png)

## 5. 그래서 얼마나 아낄 수 있나 — 실측 추정

외주 사이트 중 **가장 트래픽이 몰리는 사이트 Y**는 하루 약 1.4만 건 요청, 워커 호출 약 9.4천 건이었다. 그중 **캐시 히트율이 ~16.7%** 에 그친다. 이는 "만료 헤더는 있고, 실제 리소스별 캐시 분기가 없어서" 생기는 낮은 히트율의 전형이다.

- 만약 원본 이미지 평균 1.2MB를 최적화(상세 200KB)하면 **월 전송량은 1/6 이하로** 줄어든다 (아래 차트).
- 게다가 `thumb`(400px)을 목록에 쓰면, "상세 이미지까지 전부 내려받는" 무거운 목록 페이지도 크게 가벼워진다.

![최적화에 따른 월 전송량 절감 추정](/posts-assets/shopping-mall-image-worker/fig2_traffic_savings.png)

> 수치는 지금 운영 중인 사이트의 요청량(약 1.4만/일) × 이미지 비중(약 60%)을 가정한 **추정**이다. 정확한 값은 CDN 로그로 측정해야 하지만, "파생본을 만들면 트래픽이 얼마나 줄까"의 직관은 이 정도로 충분하다.

## 6. 개선 로드맵 — 블로그 캐시 시리즈와 연결

이미지 최적화의 핵심은 **"계산한 것을 다시 하지 않는다"** — [Semantic Cache 글](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-semantic-cache-llm-cost) 과 정확히 같은 발상이다. 세부 계획을 세 단계로 나누면:

**1단계: Upload 시간에 파생본 생성 (한 번 하면 재사용)**
- 관리자 업로드 직후 Worker(또는 CDN 이미지 최적화)가 `thumb`/`detail`/`zoom`을 만들어 R2에 저장
- 이후 요청은 파생본을 그대로 반환 — **cache-aside 패턴** ([조회수 글](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-lessons-applied-view-count-and-ranking)에서 다룬 재사용)

**2단계: CDN 캐시 분기 + 히트 유도**
- `Cache-Control`을 파생본 경로마다 다르게 (예: `thumb`은 더 길게)
- 리소스별 캐시를 나눠 **지금의 ~16.7% 히트율을 끌어올림**

**3단계: 원본 정리**
- `original`을 기본 비활성, 꼭 필요할 때만 **TTL 자동 삭제** (Redis/KV의 TTL 원리)

```figure
{"type":"flow","caption":"이미지 최적화 로드맵 — 재계산을 피하고 캐시를 쪼갠다","nodes":[{"id":"up","label":"업로드"},{"id":"gen","label":"파생본 생성","note":"thumb/detail/zoom","emphasis":true},{"id":"cd","label":"CDN 캐시 분기","note":"경로별 TTL·히트 유도"},{"id":"orig","label":"원본 정리","note":"TTL 자동 삭제"}],"edges":[{"from":"up","to":"gen"},{"from":"gen","to":"cd"},{"from":"cd","to":"orig"}]}
```

## 7. 결론 — 외주 사이트에서 이미지가 만드는 진짜 병목

이미지 워커는 **안전하고 정상 동작**한다. 하지만:

1. "최적화"라는 이름과 달리 **서버 파생본·CDN 캐시 분기는 아직 없다** (브라우저 1차 변환이 전부).
2. 트래픽이 몰리는 사이트에서 **캐시 히트율 ~16.7% + 원본 전송**은 모바일 로딩과 대역폭 비용의 병목.
3. 개선은 "파생본을 만들고 → 경로별 캐시를 나누고 → 원본은 TTL로 정리" — 내 블로그의 [캐시/Redis 시리즈](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-data-structures-and-production-patterns) 원리와 정확히 맞닿는다.

외주 작업에서 "리서치하고 설계했지만 실행은 초기"인 부분이 가장 많은 개선 여지를 준다. 이 글이 그 **현실 진단**이다.
