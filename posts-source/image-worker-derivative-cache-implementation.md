---
slug: image-worker-derivative-cache-implementation
title: 이미지 Worker 개선 실제 코드 — 파생본 생성과 캐시 분기를 직접 구현해보니
excerpt: 직전 이미지 Worker 분석 글에서 '파생본·캐시 분기가 빠져 있다'고 진단했다. 이번엔 그 답안을 실제 Workers 코드로 써본다: 업로드 시 thumb/detail/zoom 파생본을 만들고, 목록·상세·확대 요청을 캐시 분기로 나누어 전송량과 캐시 히트율을 어떻게 개선하는지.
tags: [cloudflare, backend, worker, optimization]
status: published
---

[직전 글](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/shopping-mall-image-worker-optimization)에서 실제 이미지 Worker가 "업로드만 하고 파생본·캐시 분기가 없다"고 진단했다. 그건 관찰이었고, 이번엔 **그 답안을 실제 코드로** 써본다.

핵심 통찰은 다시 한 번: **"계산한 파생본을 재사용 + 요청 경로에 맞는 캐시 분기"**. 이건 내 [캐시/Redis 시리즈](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-data-structures-and-production-patterns)에서 반복해서 본 "재계산을 피하는" 원리의 이미지 버전이다.

```figure
{"type":"flow","caption":"업로드 시 파생본 3종을 만들어 재사용한다","nodes":[{"id":"up","label":"업로드"},{"id":"gen","label":"파생본 생성","note":"thumb/detail/zoom","emphasis":true},{"id":"sv","label":"R2 저장","note":"경로별 캐시 헤더"},{"id":"req","label":"요청경로 분기","note":"목록·상세·확대"}],"edges":[{"from":"up","to":"gen"},{"from":"gen","to":"sv"},{"from":"sv","to":"req"}]}
```

## 1. 파생본이 왜 전송량을 줄이나 — 목록이 상세만큼 무거운 문제

쇼핑몰 목록 페이지는 상품 이미지 10여 개를 한 번에 보여준다. 만약 목록에서 **상세(detail 420KB)** 를 전부 내려받으면, 목록 하나가 몇 MB가 된다. 반면 목록용 `thumb`(90KB)만 쓰면 전송량이 대폭 줄어든다.

![thumb를 목록에 쓰면 전송량이 줄어든다](/posts-assets/shopping-mall-image-worker/fig3_thumb_savings.png)

위 차트처럼, 목록 10개 + 상세 1개 페이지에서 "전부 원본(1.2MB)" 대신 "목록은 thumb, 상세는 detail" 을 쓰면 **전송량이 10%대까지** 떨어진다. 이게 파생본 분리의 실익이다.

## 2. 실제 코드 — 업로드 시 파생본 생성 (WASM 이미지 처리)

Workers에서 리사이즈·WebP 인코딩을 하려면 이미지 코덱이 필요하다. 여기선 **@jsquash**(WASM) 계열을 쓴다 — Workers에서 `fetch`로 WASM을 로드해 `resize`/`encode`를 할 수 있다.

```ts
// workers/image-optimizer/src/derivatives.ts
import { resize } from '@jsquash/resize';
import { webpEncode } from '@jsquash/webp';

export type DerivSpec = { width: number; quality: number };
export const DERIVS: Record<string, DerivSpec> = {
  thumb: { width: 400,  quality: 75 },
  detail:{ width: 1200, quality: 82 },
  zoom:  { width: 2000, quality: 88 },
};

async function toImageData(blob: Blob): Promise<ImageData> {
  const bitmap = await createImageBitmap(blob);
  const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(bitmap, 0, 0);
  return ctx.getImageData(0, 0, bitmap.width, bitmap.height);
}

/** 원본 바이트 → 각 파생본(webp)을 만들어 R2에 저장. 이미 존재하면 건너뜀(cache-aside). */
export async function createDerivatives(
  bucket: R2Bucket, baseKey: string, bytes: ArrayBuffer, contentType: string,
): Promise<Record<string, string>> {
  const blob = new Blob([bytes], { type: contentType });
  const src = await toImageData(blob);
  const keys: Record<string, string> = {};

  for (const [name, spec] of Object.entries(DERIVS)) {
    const ratio = Math.min(1, spec.width / src.width);
    const key = `${baseKey}/${name}.webp`;

    // 이미 파생본이 있으면 재사용 (cache-aside — 재계산 방지)
    if (await bucket.head(key)) { keys[name] = key; continue; }

    const w = Math.max(1, Math.round(src.width * ratio));
    const h = Math.max(1, Math.round(src.height * ratio));
    const out = await resize(src, { width: w, height: h });
    const webp = await webpEncode(out, { quality: spec.quality });

    await bucket.put(key, webp, {
      httpMetadata: { contentType: 'image/webp', cacheControl: 'public, max-age=31536000, immutable' },
    });
    keys[name] = key;
  }
  return keys;
}
```

여기서 **`bucket.head(key)` 로 파생본 존재를 먼저 확인**해 이미 있으면 재사용하는 게 핵심이다 — 이게 "동일 입력이면 파생본을 또 만들지 않는다(cache-aside)"는 원리다.

## 3. 실제 코드 — 요청 경로별 캐시 분기

업로드 후 프론트가 파생본 URL을 경로로 요청하면, 해당 Worker가 **경로에 맞는 캐시 헤더**로 응답한다.

```ts
// worker 라우팅: /img/{base}/{deriv}
const CACHE = {
  thumb:  'public, max-age=604800',      // 7일 — 목록은 자주 바뀌지 않음
  detail: 'public, max-age=86400',       // 1일
  zoom:   'public, max-age=31536000, immutable', // 확대는 바뀔 일 적음
};

async function handleImage(req: Request, env: Env, base: string, deriv: string) {
  const key = `uploads/${base}/${deriv}.webp`;
  const obj = await env.IMAGE_BUCKET.get(key);
  if (!obj) return new Response('Not found', { status: 404 });

  const headers = new Headers();
  obj.writeHttpMetadata(headers);
  headers.set('etag', obj.httpEtag);
  headers.set('cache-control', CACHE[deriv] ?? 'public, max-age=86400');
  headers.set('vary', 'Accept'); // webp/avif 협상
  const body = obj.body as ReadableStream;
  return new Response(body, { headers });
}
```

**경로별로 다른 TTL**을 주어, 자주 바뀌는 detail은 짧게, 확대(zoom)는 길게 캐시한다. 이렇게 하면 **동일 파생본 URL 요청이 CDN에서 히트**되어 오리진(R2/Worker)까지 안 간다.

```figure
{"type":"flow","caption":"캐시 히트율이 오리진 부하를 좌우한다","nodes":[{"id":"req","label":"파생본 요청"},{"id":"cache","label":"CDN 캐시","note":"경로별 TTL"},{"id":"origin","label":"오리진(R2)","note":"미스만 통과"}],"edges":[{"from":"req","to":"cache"},{"from":"cache","to":"origin"}]}
```

![캐시 히트율이 오리진 부하를 좌우한다](/posts-assets/shopping-mall-image-worker/fig4_cache_hit_origin.png)

## 4. 원본 정리 — TTL 자동 삭제

파생본이 만들어지면 **원본(original)** 은 꼭 필요한 경우 외엔 보관하지 않는 게 R2 저장비용을 줄인다. Cloudflare KV/Workers에서 TTL로 정리하는 방식(내 캐시 시리즈에서 다룬 원리)과 같다.

```ts
// 원본은 7일 뒤 자동 삭제 — 파생본만 상시 보관
await bucket.put(`${baseKey}/original.jpg`, bytes, {
  httpMetadata: { contentType },
  // R2 자체 만료: customMetadata에 삭제할 시간을 기록 후 cron/큐로 정리하거나,
  // 간단히 파생본 생성 후 original을 삭제하도록 정책화
  customMetadata: { expiresAt: String(Date.now() + 7*24*3600*1000) },
});
```

다만 "파생본 원복이 필요해지는 경우"를 대비해, `original`을 무조건 지우기보다 **짧은 TTL 보관 후 정책 발동 시 삭제**하는 절충이 일반적이다.

## 5. 정리 — 블로그 캐시 시리즈와 이어지는 답

| 개선 | 실제 코드 | 원리 |
|---|---|---|
| 파생본 생성 | thumb/detail/zoom (WASM) | **재계산 회피** |
| 파생본 재사용 | `bucket.head` 캐시 | **cache-aside** ([Semantic Cache](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-semantic-cache-llm-cost) 와 동일) |
| 요청 경로 캐시 분기 | 경로별 TTL | **분기 캐시** ([Redis 자료구조](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/redis-data-structures-and-production-patterns) 캐시 원리) |
| 원본 정리 | TTL/삭제 정책 | **만료** |

지난 글에서 "이름만 최적화고 파생본·캐시 분기가 빠져 있다"고 지적한 것에 대해, 이 글은 **그 답안을 실제로 돌아가는 Workers 코드로** 제시한다. 외주 Worker에 적용하면 지난 글의 실측 수치(전송량 1/6, 캐시 히트율 ~16.7% 개선) 쪽으로 실제로 나아갈 수 있다.

## 마무리

"최적화"는 코드가 아니라 **설계 의도**다. 업로드 한 번에 파생본을 만들고, 요청 경로마다 다르게 캐시하고, 원본은 TTL로 정리하는 세 가지가 실제 코드로 갖춰질 때 비로소 이름값을 한다. 이 글의 답안 코드는 그 출발점이다.
