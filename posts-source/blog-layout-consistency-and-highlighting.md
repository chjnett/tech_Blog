---
slug: blog-layout-consistency-and-highlighting
title: 폰에서 보니 카드가 어긋났다 — 이 블로그의 레이아웃 정합성·넘침·하이라이팅 일괄 정리
excerpt: 데스크톱에선 잘 맞아 보이던 블로그가 폰에선 카드 좌우가 어긋나고, 긴 코드가 화면을 넘치고, 터미널 로그가 잘렸다. 이 블로그(modular CSS, 디자인 시스템)에서 좌우 여백을 맞추고 넘침을 막고, 코드 하이라이팅을 Shiki로 바꾼 과정을 정리.
tags: [cloudflare, meta, optimization]
status: published
---

지난 [모바일 반응형 글](https://tech-blog-worker.cheonhyeonjun583.workers.dev/posts/blog-mobile-responsive-optimization)에선 3D·터치·배터리를 다뤘다. 이번엔 그 다음 단계로, 실제 폰에서 열어보니 드러난 **레이아웃 정합성·넘침·하이라이팅** 문제와 그 해결을 정리한다. 전부 이 블로그에 실제 적용한 것들이다.

```figure
{"type":"flow","caption":"폰에서 발견한 세 부류의 문제","nodes":[{"id":"a","label":"카드 어긋남","note":"좌우 여백·간격 불일치"},{"id":"b","label":"넘침/잘림","note":"grid 자식이 화면 폭 초과"},{"id":"c","label":"코드/터미널","note":"색 없음 · 가로 스크롤 없음"}],"edges":[{"from":"a","to":"b"},{"from":"b","to":"c"}]}
```

## 1. 문제 — 데스크톱엔 맞는데 폰엔 어긋나는 카드

이 블로그의 게시글 그리드와 오픈소스(PR) 영역은 각자 `max-width: 880px` + 좌우 `24px` 패딩을 쓴다. 겉보기엔 같아 보이는데, 폰에서 보니 **오픈소스 패널이 추가로 내부 패딩을 가져서** 게시글 카드보다 안쪽으로 들여져 있었다. 즉 좌우 시작 위치가 달랐다.

```
데스크톱: posts(24px)  [카드...]  /  oss-panel(24px+패널내부24px)  [카드...]   ← 안쪽으로 더 들여짐
```

## 2. 해결 — 좌우 여백·카드 간격을 '같은 숫자'로

시각적 일관성의 핵심은 **"같은 값을 쓰는 것"** 이다. `.oss-rows`의 패딩을 없애 패널 안 카드가 게시글 카드와 같은 `24px`에서 시작하게 하고, 카드 간격도 게시글 그리드의 `gap:22px`로 맞췄다.

```css
.posts-grid{ grid-template-columns:repeat(2,1fr); gap:22px; }
.oss-row   { grid-template-columns:repeat(2,1fr); gap:22px; }  /* 동일 gap */
.oss-rows  { padding:18px 0 24px; }   /* 24px에서 시작 → posts와 정렬 */
```

다른 값(14px 등)을 같은 값(22px)으로 통일하니, 폰에서 두 영역의 카드가 **좌우로 딱 맞게** 보였다.

## 3. 넘침/잘림 — grid 자식의 `min-width:0`과 `overflow-wrap`

폰에서 긴 PR 제목이나 코드가 화면을 넘치고 오른쪽이 잘렸다. 원인은 **grid/flex 자식이 내용물 폭으로 커지는** 전형적인 버그다. 넘치기 쉬운 자식에는 두 가지를 d며:

```css
.post-card, .contrib-card, .pr-branch{
  min-width:0;          /* 내용물 폭으로 커지지 않게 */
  overflow-wrap:anywhere; /* 긴 코드/URL은 행바꿈 */
}
```

- `min-width:0` — 그리드 자식이 최소 폭 0일 수 있게 해, 내용물이 카드를 밀어내지 못하게
- `overflow-wrap:anywhere` — 미닫히는 코드/URL이 있으면 줄바꿈 (화면 밖으로 밀지 않음)

## 4. 터미널 로그 — 코드 블록처럼 가로 스크롤

터미널 출력의 긴 한 줄이 폰에서 잘렸다. 코드 블록(`.code-block pre`)은 이미 가로 스크롤이 있었는데, 터미널(`.terminal pre`)만 빼먹었던 것.

```css
.terminal pre{
  overflow-x:auto;                 /* 긴 로그 스크롤 */
  white-space:pre;                 /* 줄바꿈 대신 원문 유지 */
  -webkit-overflow-scrolling:touch; /* 모바일 부드러운 스크롤 */
}
```

## 5. 코드 하이라이팅 — Prism → Shiki로 모든 언어에 색

이 블로그는 디자인 원칙상 **색은 코드 블록 안에서만** 쓴다. 그런데 기존 Prism은 5개 언어만 지원해서, `css`, `markdown`, `dockerfile` 등 코드 블록에는 색이 없었다. 그래서 **Shiki**(VS Code 문법)로 바꿨다.

- **지원 언어 5 → 11개** (python/ts/js/json/bash/css/markdown/html/dockerfile/go/sql)
- 블로그 4색 팔레트(keyword/string/comment/function) 커스텀 테마
- **번들 최적화**: `shiki` 전체(10MB+) 대신 `shiki/core` + 필요한 언어만 → **1.4MB** (Worker 제한 안)
- sanitize가 코드 블록 안 `span`/`code`의 인라인 색을 허용하도록 확장

```terminal
$ curl .../posts/redis-data...
# keyword #E2A33D:20  string #6FBF8B:22  comment #7A8290:6  function #F6F7F9:66
```

```css
.token, span[style^="color"]{
  /* Shiki가 코드블록 안에서 팔레트 색을 인라인으로 넣는다 */
}
```

## 6. 정리 — 폰에서 다시 보니

| 문제 | 해결 | 원리 |
|---|---|---|
| 카드 좌우 어긋남 | 패딩 제거 + gap 22px 통일 | **같은 값을 쓰기** |
| 카드 넘침/잘림 | `min-width:0` + `overflow-wrap` | **grid 자식 폭 제어** |
| 터미널 로그 잘림 | `overflow-x:auto` | **블록별 가로 스크롤** |
| 코드색 부족 | Prism → Shiki | **서버사이드 하이라이팅** |

이번 개선은 "데스크톱에서 보인다"가 아니라 **"폰에서 실제로 열어보고"** 고쳐야 발견되는 것들이었다. 블로그가 진짜 반응형이 되려면, 확인은 항상 실제 기기에서 해야 한다는 교훈을 다시 한 번 남긴다.
