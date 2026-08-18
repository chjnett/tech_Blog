---
slug: worker-refactor-sanitize-hardening
title: 개인 블로그 Worker 코드 개선기 — SELECT * 제거부터 XSS 하드닝까지
excerpt: D1 쿼리 컬럼 최적화, 6개 파일에 흩어진 헬퍼 통합, 콘텐츠 sanitize, RSS 이스케이프 누락, 타입/Web Crypto 개선까지. 직접 운영하는 Cloudflare Workers 블로그의 코드를 정리한 기록.
tags: [cloudflare, security]
status: published
---

이 블로그는 Cloudflare <span class="tooltip" data-tooltip="(Cloudflare Workers) CDN 엣지에서 도는 서버리스 함수" tabindex="0">Workers</span> + <span class="tooltip" data-tooltip="(Cloudflare D1) Workers 위에서 쓰는 SQLite 기반 서버리스 DB" tabindex="0">D1</span>로 돌아간다. 글 원문(`content_md`)은 D1에 저장하고, Worker가 읽어서 마크다운 → HTML로 렌더링해 서빙한다. 발행할 때마다 사이트를 재빌드하지 않아도 되는 구조다.

글을 계속 쓰면서 코드를 다시 들여다보니, "지금은 돌아가지만 앞으로 발목 잡을" 지점이 몇 개 보였다. 특히 다음 페이즈(논문 자동 초안, 깃허브 커밋 초안)부터는 **기계가 생성한 콘텐츠가 DB에 들어오기 시작**하는데, 그 전에 하드닝을 해두는 게 맞겠다는 판단이었다. 이 글은 그 개선 작업의 기록이다.

```figure
{"type":"flow","caption":"콘텐츠 렌더링 + sanitize 파이프라인","nodes":[{"id":"md","label":"content_md","note":"D1에 저장된 마크다운 원문"},{"id":"marked","label":"marked.parse","note":"code/terminal/figure 렌더러"},{"id":"sanitize","label":"sanitize-html","note":"allowlist 필터","emphasis":true},{"id":"html","label":"HTML","note":"퍼블릭 응답"}],"edges":[{"from":"md","to":"marked"},{"from":"marked","to":"sanitize"},{"from":"sanitize","to":"html"}]}
```

## 개선 목록 한눈에

| 항목 | 문제 | 조치 |
|---|---:|---|
| D1 쿼리 | `SELECT *`로 `content_md`까지 실어 나름 | 목록/상세 컬럼 분리 |
| 헬퍼 중복 | `escapeHtml` 등이 6개 파일에 중복 | `utils.ts`로 통합 |
| XSS | `marked`가 원본 HTML 그대로 통과 | allowlist sanitize |
| RSS | `<link>` slug 이스케이프 누락 | `escapeXml` 적용 |
| 타입/보안 | `status`가 그냥 `string`, 손수 만든 토큰 비교 | 리터럴 유니온 + Web Crypto |

하나씩 보자.

## 1. `SELECT *` 제거 — 목록이 무거웠다

목록 조회(`/api/posts`, `/rss.xml`)는 제목·요약·태그·발행일만 필요한데, 원래 코드는 `SELECT *`로 `content_md` 본문 전체를 D1에서 읽어 Worker 메모리에 올리고 있었다. 응답 JSON은 요약만 내보내지만, 그 전에 필요 없는 본문 전체를 D1에서 끌어올리는 낭비가 있었던 셈이다.

```ts
// before — 목록에도 본문 전체가 실림
const { results } = await db
  .prepare("SELECT * FROM posts WHERE status = 'published' ORDER BY published_at DESC")
  .all<PostRow>();
```

```ts
// after — 목록은 요약 컬럼만
const { results } = await db
  .prepare(
    "SELECT id, slug, title, excerpt, tags, cover_image_key, published_at " +
    "FROM posts WHERE status = 'published' ORDER BY published_at DESC"
  )
  .all<PostSummary>();
```

거기에 맞춰 타입도 `PostRow` 하나에서 `PostSummary`(목록용) / `PostDetail`(본문 포함)로 나눴다. DB에서 뭘 읽는지가 타입에 드러나니까, 나중에 컬럼을 추가해도 "목록에 본문이 섞여 들어가는" 실수를 컴파일 시점에 잡을 수 있다.

이 개선이 실제로 얼마나 줄였는지, 로컬 D1의 발행 글 5편을 실측해봤다. `GET /api/posts`가 D1에서 읽는 바이트가 이렇게 바뀐다.

![GET /api/posts가 D1에서 읽는 바이트 — 48.7KB → 1.1KB (44.9배 감소)](/posts-assets/worker-refactor-sanitize-hardening/fig1_d1_read_bytes.png)

본문(`content_md`)이 빠졌기 때문에, 글 수가 늘어날수록 이 격차는 선형으로 벌어진다(현재 평균 기준 예측).

![글 수 증가에 따른 D1 읽기 바이트 예측 — SELECT *는 선형 폭증, 컬럼 명시는 완만](/posts-assets/worker-refactor-sanitize-hardening/fig2_scaling.png)

## 2. 헬퍼 중복 제거 — `utils.ts` 하나로

`escapeHtml`이 `render.ts`, `highlight.ts`, `terminal-block.ts`, `figure.ts`, `figure-groups.ts`, `post-page.ts` 여섯 군데에 각자 조금씩 다르게 정의돼 있었다(어떤 건 `"`를 이스케이프하고 어떤 건 안 하고). `parseTags`도 두 곳, `escapeXml`도 한 곳. 같은 로직이 흩어져 있으면 한 곳만 고치고 나머지를 놓치는 게 흔한 버그다.

```ts
// src/utils.ts — 이제 한 곳에서 관리
export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch]);
}

export function escapeXml(value: string): string { /* ... */ }

export function parseTags(tags: string | null): string[] { /* ... */ }
```

모든 렌더러/라우트가 이걸 import하도록 바꾸고, 파일마다 있던 사본을 지웠다.

## 3. 콘텐츠 sanitize — 원본 HTML 통과를 막는다

이게 이번 작업의 핵심이다. `marked`는 마크다운에 섞인 **원본 HTML을 그대로 통과**시킨다. 지금까지는 내가 직접 쓴 글뿐이라 문제가 없었지만, 논문 크롤링이나 깃허브 커밋 메시지 같은 **기계 생성 콘텐츠가 `content_md`로 들어오면** `<script>`나 `onerror="..."` 같은 게 그대로 실행될 수 있다.

그래서 렌더 결과를 `sanitize-html`로 **allowlist 기반 필터링**하게 바꿨다. 허용 목록은 이 블로그 디자인 시스템이 실제로 만들어내는 HTML(코드/터미널/피규어 블록, 툴팁 `<span class="tooltip">`)만 담고, 나머지는 제거된다.

```ts
// src/render.ts — 렌더 결과를 allowlist로 정리
export function renderMarkdown(md: string): string {
  const html = marked.parse(md) as string;
  const wrapped = /* 표 래핑 */;
  return sanitizeRenderedHtml(wrapped);
}
```

검증 삼아 이런 글을 넣어봤다:

```html
본문 <span class="tooltip" data-tooltip="설명" tabindex="0">툴팁</span> 테스트.
<script>alert(1)</script>
<img src="x" onerror="alert(2)">
<a href="javascript:alert(3)">bad</a>
```

```terminal
$ curl -s http://localhost:8787/api/posts/sanitize-test-post
# tooltip 생존: True
# script 제거: True
# onerror 제거: True
# javascript: 제거: True
```

툴팁은 살아남고, 스크립트·이벤트 핸들러·`javascript:` URL은 전부 빠진다.

### viewBox의 함정

한 가지 삽질이 있었다. 이 블로그의 피규어 블록은 JSON → SVG로 그려지는데, `sanitize-html`이 내부적으로 HTML 파서를 써서 **속성명을 전부 소문자로** 바꿔버린다. 그래서 SVG의 camelCase 속성 `viewBox`가 `viewbox`가 되어 allowlist에서 빠지고, `viewBox`가 통째로 사라졌다.

```html
<!-- sanitize 전 -->
<svg viewBox="0 0 400 220" xmlns="...">

<!-- sanitize 후 (viewBox 유실) -->
<svg xmlns="...">
```

`viewBox`가 없으면 SVG가 스케일링을 못 해서 다이어그램이 잘린다. 해결은 두 단계였다. allowlist에는 소문자 `viewbox`로 등록해 살려내고, 그 뒤에 `viewBox`로 복원한다.

```ts
// 소문자로 매칭해서 살려낸 뒤 camelCase로 복원
svg: ['viewbox', 'xmlns', ...],
// ...
return sanitized.replace(/viewbox=/g, 'viewBox=');
```

우리 렌더러가 쓰는 camelCase SVG 속성은 `viewBox` 하나뿐이라 전역 치환으로도 안전하다. "SVG를 HTML sanitizer에 통과시킬 땐 대소문자를 조심하라"는 교훈.

## 4. RSS `<link>` 이스케이프 누락

RSS 피드의 `<link>`/`<guid>`에 slug가 **이스케이프 없이** 들어가고 있었다. 지금은 slug를 사람이 영문 소문자로 직접 지어서 위험은 없지만, 나중에 slug 자동 생성이 생기면 특수문자가 섞일 수 있다.

```ts
// before — slug가 그대로 URL에
const link = `${siteUrl}/posts/${row.slug}`;
// after — 이스케이프 + 인코딩
const postUrl = `${siteUrl}/posts/${encodeURIComponent(row.slug)}`;
```

`escapeXml(postUrl)`까지 적용해 피드 파싱이 깨질 여지를 없앴다.

## 5. 타입 강화 + Web Crypto

`status`와 `source_type`이 그냥 `string`이어서 오타(`'publshed'`)가 컴파일 타임에 안 잡혔다. 리터럴 유니온으로 좁혔다.

```ts
export type PostStatus = 'draft' | 'in_review' | 'published' | 'rejected';
export type SourceType = 'manual' | 'commit' | 'paper';
```

또 임시 발행 엔드포인트(`/admin/publish`)의 두 군데를 Web Crypto로 갈아끼웠다. ID는 슬러그 기반 문자열 대신 `crypto.randomUUID()`로, 관리자 토큰 비교는 손으로 짠 비교문 대신 `crypto.subtle.timingSafeEqual()`로.

```ts
// 토큰 비교 — 타이밍 공격에 안전한 Web Crypto 사용
const aBytes = encoder.encode(a);
const bBytes = encoder.encode(b);
if (aBytes.byteLength !== bBytes.byteLength) return false;
return crypto.subtle.timingSafeEqual(aBytes, bBytes);
```

`Math.random()`이 아닌, Workers 런타임이 제공하는 암호학적 안전 난수/비교라는 점이 포인트다.

## 검증

프로젝트에 자동 테스트가 없는 대신, `wrangler dev` + `curl`이 실제 테스트 사이클이다. 타입체크와 주요 라우트를 돌렸다.

```terminal
$ npx tsc --noEmit
# (통과, exit 0)

$ curl -s -o /dev/null -w "%{http_code}" http://localhost:8787/api/posts
200

$ curl -s -o /dev/null -w "%{http_code}" http://localhost:8787/rss.xml
200

$ curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8787/admin/publish
401
```

`/admin/publish`는 시크릿이 없을 때 잠겨서(401) 열리는 게 아니라 닫히는 것까지 확인했다.

## 마무리

정리하면 "동작은 하는데, 규모가 커지거나 기계 생성 콘텐츠가 들어오면 터질 수 있는" 지점을 미리 손본 작업이었다. 특히 sanitize는 다음 페이즈(논문 자동 초안)로 가기 전에 반드시 필요한 안전장치였다.

다음으로 손볼 만한 것도 보인다. `Env` 바인딩 타입을 손으로 쓰지 말고 `wrangler types`로 생성하게 하는 것, `marked`에 남아 있는 죽은 옵션(`useNewRenderer`) 정리 같은 것들이다. 하지만 이번처럼 "지금 문제가 되는 것"부터 차근차근.

이 글 자체가 그 과정을 담은 메타 포스팅이 됐다. 앞으로의 글도 이 개선된 파이프라인을 타고 올라간다.
