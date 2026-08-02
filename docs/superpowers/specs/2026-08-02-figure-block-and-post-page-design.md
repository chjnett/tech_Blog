# Figure 블록 렌더러 + 포스트 상세 페이지 설계

## 배경

`docs/TODO.md`의 "설계는 됐지만 어느 Phase에도 안 들어간 것" 두 항목(figure 블록 자동
레이아웃, 포스트 상세 페이지 템플릿)을 함께 설계한다. 둘은 서로 의존적이다 — 포스트 페이지가
`content_html` 안의 figure SVG를 실제로 보여주려면 figure 렌더러의 출력 형식과 CSS 클래스를
알아야 하고, figure 렌더러가 제대로 동작하는지는 실제 포스트 페이지에서 눈으로 확인해야 한다.
Phase 1(기반)이 완료된 뒤 이어지는 다음 구현 단계로, `docs/HANDOFF.md` §2.3, §7을 대체/구체화한다.

## 범위

- `figure` 콘텐츠 컴포넌트(JSON → SVG 다이어그램) 자동 레이아웃 렌더러
- `GET /posts/:slug` — Worker가 서버사이드로 완전한 HTML을 반환하는 개별 글 페이지
- `pages/blog.css` — 아티클 셸 + code/terminal/figure 컴포넌트 공유 스타일시트

## 범위 밖

- 리뷰 대시보드, 논문 파이프라인, 웹훅 등 다른 Phase (변경 없음)
- 블로그 글 목록 페이지 (홈에서 글 목록을 보여주는 UI) — 이번 스펙은 개별 글 페이지만

---

## 1. Figure 블록 렌더러

### 1.1 스키마 확장

```json
{
  "type": "flow",
  "caption": "설명 캡션",
  "nodes": [
    { "id": "q", "label": "Query (Q)", "note": "보조 설명", "emphasis": false }
  ],
  "edges": [
    { "from": "q", "to": "score", "label": "선택적 라벨" }
  ]
}
```

`emphasis`는 optional boolean (기본 `false`). `true`면 해당 노드를 `var(--ink)` 채우기 +
흰 텍스트로 렌더링 (검정/흰색 반전 강조 — `docs/HANDOFF.md` §1.1 무채색 원칙 준수).

### 1.2 레이아웃 알고리즘

노드/엣지 렌더링 코드는 공유하고, 타입별로 포지션(열/행) 계산 함수만 다르다.

- **`flow`**: 각 노드의 column = 소스(들어오는 edge가 없는 노드)로부터의 최장 경로 길이
  (topological layering, Sugiyama 스타일의 단순화 버전). 같은 column의 노드는 세로로
  균등 배치. `nodes`/`edges` 배열 순서와 무관하게 실제 그래프 구조로 열을 계산하므로,
  Q/K/V → 유사도 계산 → 가중합 출력 같은 fan-in 구조가 자연스럽게 처리된다.
- **`compare`**: column = `nodes` 배열 인덱스, 한 줄로 나란히 배치. edge가 있으면 flow와
  동일한 화살표 렌더링 방식을 그대로 재사용.
- **`stack`**: row = `nodes` 배열 인덱스, 한 열로 위→아래 배치.

컬럼/행 간격은 고정 상수(예: column 180px, row 90px)로 두고, SVG `viewBox`는
`(최대 column 수 × 열 너비, 최대 column당 노드 수 × 행 높이)`로 계산한다.

### 1.3 렌더링 규칙

- 일반 노드: 흰 배경 + `var(--ink)` 테두리(1.5~2px), 라운드 6px
- `emphasis: true` 노드: `var(--ink)` 채우기 + 흰 텍스트
- 화살표: 직선 + 삼각형 머리 (곡선 금지). edge에 `label`이 있으면 선 중간에 mono 텍스트로 표시
- 라벨은 14자, note는 20자 기준으로 단어 경계에서 자동 줄바꿈 — 여러 `<tspan>` 라인으로
  나누고, 노드 높이는 실제 줄 수에 따라 가변
- 라벨은 mono, 보조설명(note)은 `var(--ink-soft)`로 축소 (기존 §2.3 규칙 유지)

### 1.4 통합 지점

Phase 1 Task 5/6과 동일한 패턴:

- `worker/src/figure.ts` 신설 — `renderFigure(json: string): string`, JSON을 파싱해 레이아웃을
  계산하고 SVG 문자열(+ `.figure-block` 래퍼, `.figure-caption`)을 반환
- `worker/src/render.ts`의 `code` 렌더러에 `infostring === 'figure'` 분기 추가
- **에러 폴백**: JSON 파싱 실패, `type`이 `flow`/`compare`/`stack`이 아님, `edges`가 존재하지
  않는 `id`를 참조 — 이런 경우 예외를 던지지 않고 원문을 이스케이프된 일반 코드블록으로
  폴백한다 (발행 파이프라인이 잘못된 figure JSON 하나 때문에 500으로 죽지 않도록).

---

## 2. 포스트 상세 페이지 (`GET /posts/:slug`, Worker SSR)

- 새 Worker 라우트. `getPublishedPostBySlug`(`db.ts`)와 `renderMarkdown`(`render.ts`)을
  Task 3의 API 라우트와 동일하게 재사용 — 쿼리 로직 중복 없음
- 미승인 상태이거나 존재하지 않는 slug → 404 (퍼블릭 API와 동일한 노출 규칙: draft/in_review/
  rejected는 존재 자체를 노출하지 않음)
- HTML 구조:
  - 상단: `pages/index.html`과 동일한 원형 마크 로고(`/mark.jpg`), 홈(`/`)으로 링크
  - `article-header`: 태그, 날짜, 제목 (exBlog.html 마크업 그대로)
  - `article-body`: `content_html`을 그대로 삽입
- `<title>{post.title} — chjnett.dev</title>`
- `<meta name="description" content="{excerpt}">`
- CSS는 인라인하지 않고 `<link rel="stylesheet" href="/blog.css">`로 참조

## 3. 공유 스타일시트 (`pages/blog.css`)

`exBlog.html`의 컴포넌트 CSS(article shell, `.code-block`, `.terminal`, `.figure-block`)를
그대로 옮기되, `.kw`/`.str`/`.cm`/`.fn` 같은 exBlog.html의 손으로 만든 클래스 대신 Phase 1
Task 6이 실제로 내보내는 Prism 토큰 클래스(`.token.keyword`, `.token.string`,
`.token.comment`, `.token.function`)를 `docs/HANDOFF.md` §1.1의 4색에 매핑한다. Prism의
다른 토큰 타입(operator, punctuation, number 등)은 색을 넣지 않고 기본 텍스트색을 그대로 둔다
(팔레트 밖 색 추가 금지 원칙).

`pages/index.html`의 인라인 `<style>`은 건드리지 않는다 — 포트폴리오 셸과 아티클 페이지는
서로 다른 관심사이므로 분리 유지.

## 4. 라우팅

`worker/wrangler.toml`에 `/posts/*` 패턴을 Worker Route로 추가 (Phase 1 Task 7이 `/api/*`,
`/rss.xml`을 추가한 것과 동일한 방식). `/mark.jpg`, `/blog.css`는 계속 Pages가 서빙(Worker
Route에 안 걸림).

---

## 의사결정 로그

- 개별 글 페이지는 Worker SSR (클라이언트 fetch 방식 아님) — SEO/크롤러 대응, RSS의
  `<link>`가 이미 `/posts/:slug` 형태를 가리키고 있어 일관성 유지
- figure 자동 레이아웃은 손으로 좌표를 조정한 exBlog.html 재현이 목표가 아니라, 실제
  콘텐츠 자동화 파이프라인에서 매번 그럴듯한 다이어그램이 나오는 것이 목표 — 그리드/레이어드
  배치로 충분
- CSS는 공유 파일(`pages/blog.css`)로 분리 — `index.html`과 향후 다른 페이지(블로그 목록,
  리뷰 대시보드 등)에서 중복 없이 재사용 가능하게
