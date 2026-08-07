# chjnett.dev — 클로드 코드 인수인계 문서

이 문서 하나로 전체 프로젝트(디자인 시스템 + 인프라 + 콘텐츠 자동화 파이프라인)를 클로드 코드에 넘길 수 있습니다.

---

## 0. 프로젝트 한 줄 요약

개인 기술 블로그 + 포트폴리오. Cloudflare(Pages + Workers + D1 + R2) 위에서 동작하며, 글쓰기(수동 메모 / 깃허브 커밋 / 논문 추천)를 자동 초안화하되 **모든 발행은 사람이 승인해야 함**.

---

## 1. 디자인 시스템

### 1.1 컬러 원칙

사이트 전체는 **무채색(흑백)** 이 기본이다. 색은 오직 **코드 블록의 syntax highlighting에서만** 쓴다 — 이게 이 디자인의 유일한 컬러 포인트다. 버튼, 링크, 다이어그램, 터미널, 호버 상태 등 그 외 모든 곳은 색이 아니라 굵기(weight) · 테두리 진하기 · 인버트(흑백 반전) · 위치 이동으로 강조를 표현한다.

```json
{
  "color": {
    "bg": "#FFFFFF",
    "bgSoft": "#F6F7F9",
    "ink": "#10131A",
    "inkSoft": "#5B6270",
    "line": "#E7E9EE",
    "accent": "var(--ink)"
  },
  "codeSyntax": {
    "background": "#10131A",
    "text": "#F6F7F9",
    "keyword": "#E2A33D",
    "string": "#6FBF8B",
    "comment": "#7A8290",
    "function": "#F6F7F9"
  },
  "font": {
    "mono": "'JetBrains Mono', ui-monospace, monospace",
    "sans": "'Inter', -apple-system, sans-serif"
  }
}
```

**적용 규칙**

- `accent` 토큰은 `var(--ink)`를 가리킨다 — 즉 UI 전역에서 "강조 색"은 사실상 존재하지 않고 검정/흰색 반전만 있다.
- 코드 블록(`.code-block`) 안에서만 `codeSyntax`의 4개 색(keyword/string/comment/function)을 쓴다. 이 팔레트 밖의 색은 추가하지 않는다.
- 새 컴포넌트를 만들 때 "강조가 필요하다"고 색을 추가하고 싶은 유혹이 들면: 대신 굵기/테두리/인버트로 먼저 시도해볼 것. 코드 블록 외 영역에 색이 필요하다고 판단되면, 구현 전에 반드시 [체크포인트 질문](#6-체크포인트-질문)을 통해 사용자에게 확인한다.

### 1.2 타이포그래피

- 헤딩, 라벨, 날짜, 태그: JetBrains Mono
- 본문: Inter
- 아티클 본문: `max-width 680px`, `font-size 17px`, `line-height 1.75`
- 코드/터미널/피규어 블록: `max-width 640px` (본문보다 살짝 좁게 인셋 → 별도 블록임을 여백으로 구분)

---

## 2. 콘텐츠 컴포넌트 3종

레퍼런스 구현: [`exBlog.html`](../exBlog.html) (예시 아티클 페이지, 세 컴포넌트 모두 포함).
실제로 글을 쓸 때 참고할 실용 가이드(frontmatter, 문법, 체크리스트)는
[`posts-source/README.md`](../posts-source/README.md) — 이 섹션은 "왜/무엇을", 그
파일은 "어떻게" 담당.

### 2.1 코드 블록 — `code`

일반 fenced code block(언어 태그 필수) 그대로 사용.

- 배경 `#10131A`, 기본 텍스트 `#F6F7F9`
- syntax 강조: keyword `#E2A33D`(bold), string `#6FBF8B`, comment `#7A8290`(italic), function명 `#F6F7F9`(bold) — 딱 이 4개 역할만, 색상 추가 금지
- 상단 바: 언어 라벨(우측, mono 11px, 반투명) + 복사 버튼
- 구현: Worker 쪽은 Prism.js로 토큰화하고, Prism의 표준 토큰 클래스(`.token.keyword` 등)만 이 4색에 매핑한다 — 나머지 토큰 타입(operator/punctuation/number 등)은 기본 텍스트색 그대로 둬서 팔레트 밖 색이 새지 않게 한다.

### 2.2 터미널 블록 — `terminal`

````
```terminal
$ python train.py --epochs 10
epoch 1/10 | loss 4.21
...
```
````

- 배경 `var(--bg-soft)`, 상단에 점 3개 + 라벨 바 (career 섹션의 `.terminal`과 동일 컴포넌트 재사용)
- `$`로 시작하는 줄: `var(--ink)` + bold (명령어)
- 나머지 줄: `var(--ink-soft)` (출력) — **색이 아니라 굵기로 구분**한다는 점 주의

### 2.3 피규어 블록 — `figure` (개념 다이어그램)

매번 새로 그리지 않고, 아래 JSON 스키마 → 고정 렌더러를 거쳐서만 SVG를 생성한다.

```json
{
  "type": "flow",
  "caption": "설명 캡션",
  "nodes": [
    { "id": "q", "label": "Query (Q)", "note": "보조 설명" }
  ],
  "edges": [
    { "from": "q", "to": "score", "label": "선택적 라벨" }
  ]
}
```

**렌더 규칙**

- 일반 노드: 흰 배경 + `var(--ink)` 테두리(1.5~2px), 라운드 6px
- 강조 노드(계산 결과 등): `var(--ink)` 채우기(검정 인버트) + 흰 텍스트 — **색이 아니라 흑백 반전으로 강조**
- 화살표: 직선 + 삼각형 머리, 곡선 금지 (회로도 느낌 유지)
- `type`: `flow`(좌→우) / `compare`(나란히) / `stack`(위→아래, 트랜스포머 블록 구조용)
- 라벨은 mono, 보조설명은 `var(--ink-soft)`로 축소

> 이 렌더러(자동 레이아웃, 노드 강조 필드 등)는 아직 설계되지 않았다 — [로드맵](#7-로드맵--추후-개발) 참고.

---

## 3. Cloudflare 아키텍처

```
[Pages] ── 정적 셸 (포트폴리오 + 디자인 시스템 CSS)
   │
   ▼
[Workers] ── /api/posts, /api/papers, /admin/review, cron
   │
   ├──▶ [D1] posts, papers, commit_log
   └──▶ [R2] 이미지, 첨부파일
```

Pages는 정적 셸만 담당하고, 실제 글은 Workers가 D1에서 직접 읽어 서빙한다 → 발행(승인)할 때마다 재빌드 불필요, 즉시 반영.

### 3.1 D1 스키마

```sql
CREATE TABLE posts (
  id TEXT PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  content_md TEXT NOT NULL,
  excerpt TEXT,
  source_type TEXT NOT NULL,          -- 'manual' | 'commit' | 'paper'
  source_ref TEXT,
  status TEXT NOT NULL DEFAULT 'draft', -- 'draft' | 'in_review' | 'published' | 'rejected'
  tags TEXT,                          -- JSON array
  cover_image_key TEXT,               -- R2 key
  created_at TEXT NOT NULL,
  published_at TEXT
);

CREATE TABLE commit_log (
  sha TEXT PRIMARY KEY,
  repo TEXT NOT NULL,
  summarized_at TEXT NOT NULL,
  linked_post_id TEXT
);
```

`posts`는 Phase 1에서 마이그레이션됨. `commit_log`는 깃허브 웹훅 구현 시점에 별도
마이그레이션으로 추가한다.

`papers` 테이블은 위 목록에서 빠졌다 — 최신 스키마와 논문 수집/분석 파이프라인 전체는
[`docs/superpowers/specs/2026-08-02-papers-pipeline-design.md`](superpowers/specs/2026-08-02-papers-pipeline-design.md)를
기준으로 구현한다 (arXiv + OpenReview + Semantic Scholar 조합, 딥 분석 단계 포함 — 아래 §3.2
표는 그 문서의 요약일 뿐이다).

### 3.2 Workers 라우트 / cron

| 종류 | 트리거 | 동작 |
|---|---|---|
| cron (논문 추천) | 매일 09:00 KST | arXiv+OpenReview 수집 → Semantic Scholar로 정제 → 탑티어(oral/spotlight) 필터 → 관련도 스코어링 → 상위 N편 딥 분석 → figure 블록 포함 초안 생성 → `status='draft'`. 상세: [papers-pipeline-design.md](superpowers/specs/2026-08-02-papers-pipeline-design.md) |
| webhook (깃허브) | push 이벤트 | 새 커밋 diff/메시지 요약 → 개발로그 초안 생성 → `status='draft'` |
| `POST /api/drafts` | 수동 | 메모/링크 → 초안 생성 → `status='draft'` |
| `GET/POST /admin/review*` | 수동 | 초안 목록 조회 / 승인(`published`) / 수정 / 반려(`rejected`) |
| `GET /api/posts`, `/api/posts/:slug` | 퍼블릭 | 발행된 글만 조회 (Phase 1에서 구현) |
| `GET /rss.xml` | 퍼블릭 | 발행 글 기준 RSS (Phase 1에서 구현) |

발행 파이프라인 공통 흐름: **소재 발생 → Anthropic API 초안 생성 → `draft` → 리뷰 대시보드 → 승인 시 `published`(즉시 반영) / 반려 시 `rejected`**. 자동 즉시발행 없음 — 모든 소스(수동/커밋/논문) 공통 규칙.

### 3.3 임시 발행 경로 `POST /admin/publish` (대시보드 구현 전까지)

리뷰 대시보드(§5의 6단계)가 아직 없어서, 사람이 손으로 쓴 글을 올리는 임시 통로만
열어둔 상태다. **대시보드가 생기면 `worker/src/routes/admin.ts`를 파일째 지운다.**

- 인증: `Authorization: Bearer <ADMIN_TOKEN>`. 토큰은 `wrangler secret put ADMIN_TOKEN`으로
  넣는다. 시크릿이 없으면 **열리는 게 아니라 잠긴다**(전부 401) — 설정 누락이 곧
  공개가 되면 안 되기 때문.
- 동작: `slug`가 있으면 UPDATE, 없으면 INSERT. 둘 다 `status='published'`로 만든다.
  즉 **이 경로는 리뷰 게이트를 우회한다** — 사람이 직접 쓴 글에만 쓰고,
  cron/webhook 등 자동 생성 경로를 여기에 연결하지 말 것.
- 중요: `posts-source/*.md`의 `status:`를 고쳐도 사이트는 바뀌지 않는다. Worker는
  D1에서 읽는다. 반드시 이 엔드포인트(또는 `wrangler d1 execute`)로 D1을 갱신해야 한다.

```bash
# frontmatter를 파싱해 JSON으로 만든 뒤
curl -X POST https://tech-blog-worker.cheonhyeonjun583.workers.dev/admin/publish \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d @post.json
```

이미지는 `pages/posts-assets/<slug>/` 평평한 구조에 두고 본문에서
`/posts-assets/<slug>/x.png`로 참조한다. `wrangler deploy`가 `pages/`를 정적
자산으로 함께 올린다.

---

## 4. 콘텐츠 저작 — 클로드 프롬프트

`POST /api/drafts` 워커 또는 클로드 코드 커맨드의 시스템 프롬프트로 사용:

```
당신은 chjnett의 기술 블로그 편집자입니다. 사용자가 대충 정리한 줄글 메모를 받아,
정해진 컴포넌트 문법(섹션 2)을 사용한 마크다운 포스트로 변환합니다.

규칙:
1. 사용자의 말투와 느낀 점, 삽질 과정은 다시 쓰지 않고 다듬기만 한다.
2. 개념 간 관계/흐름을 설명하는 부분만 figure 블록(JSON)으로 뽑는다.
   모든 문단을 그림으로 만들지 말 것 — 정말 다이어그램이 이해를 돕는 경우만.
3. 코드 언급 → code 블록, 실행 결과/로그/벤치마크 수치 언급 → terminal 블록.
4. figure JSON은 섹션 2.3 스키마를 그대로 따르고, 색상은 임의 지정하지 않는다
   (렌더러가 토큰 기반으로 처리).
5. code 블록 안에서만 섹션 1.1의 codeSyntax 팔레트를 사용하고,
   그 외 어디에도 새로운 색을 추가하지 않는다.
6. 출력은 frontmatter + 마크다운 하나로만 한다. 부연 설명 없이.

출력 형식:
---
title: "..."
tags: [...]
status: draft
---
(마크다운 본문, code/terminal/figure 블록 포함)
```

---

## 5. 구현 순서

1. `wrangler init` → D1/R2 바인딩 연결
2. 섹션 3.1 스키마로 마이그레이션 작성
3. 퍼블릭 API(`/api/posts`, `/rss.xml`) 먼저 구현 → 더미 데이터로 테스트
4. 논문 추천 cron worker (Anthropic API 연동)
5. 깃허브 웹훅 worker
6. 리뷰 대시보드 (섹션 1~2 디자인 시스템 그대로 재사용)
7. Pages에 포트폴리오 셸 배포, Workers API 연결
8. R2 이미지 업로드 플로우

Phase 1(현재 진행 중)은 1~3단계 중 백엔드 부분(스키마+API)을 다룬다. 자세한 태스크는
[`docs/superpowers/plans/2026-08-02-blog-phase1-foundation.md`](superpowers/plans/2026-08-02-blog-phase1-foundation.md) 참고.

---

## 6. 체크포인트 질문

작업을 진행하다가 아래 상황을 만나면, 클로드는 **임의로 결정하지 말고 먼저 사용자에게 물어본 뒤 진행**한다.

**디자인 시스템 관련**

- [ ] 코드 블록 외의 영역에 색을 추가해야 할 것 같은 상황이 생기면 → "여기 색을 넣는 게 나을 것 같은데, 무채색 원칙을 깨도 될까요?"라고 먼저 확인
- [ ] 새로운 컴포넌트(터미널/코드/피규어 외)가 필요해지면 → 기존 3종에 억지로 끼워맞추지 말고, 새 컴포넌트 스펙을 제안하고 승인받기

**인프라 관련**

- [ ] D1 마이그레이션을 실행하기 전 → "기존에 저장된 데이터가 있는지, 스키마 변경이 기존 글을 깨뜨리지 않는지 확인했나요?"
- [ ] 프로덕션 배포(`wrangler deploy` on Pages/Workers) 전 → "지금 바로 프로덕션에 반영해도 되는지, 아니면 프리뷰만 먼저 볼지" 확인
- [ ] 깃허브 웹훅 연결 시 → "어떤 레포/브랜치에 웹훅을 걸지" 확인 (전체 커밋이 다 초안화되면 노이즈가 클 수 있음)
- [ ] Anthropic API 호출 비용이 예상보다 커질 수 있는 변경(예: cron 주기를 매일→매시간으로) 전 → 반드시 확인

**콘텐츠 자동화 관련**

- [ ] 논문 추천 관심 카테고리(cs.CL/cs.AI/cs.AR)를 넓히거나 좁힐 필요가 보이면 → 확인 후 변경
- [ ] 초안이 반려되는 패턴이 반복되면 → "이런 이유로 계속 반려되는데, 프롬프트 규칙을 바꿔볼까요?"라고 먼저 제안
- [ ] 자동 발행처럼 보이는 코드 경로를 추가하게 되면(예: 특정 조건에서 리뷰 없이 publish) → **절대 임의로 만들지 말고 반드시 확인**. 리뷰 승인 게이트는 예외 없는 규칙.

**논문 소싱 & 분석 파이프라인 관련** (상세: [papers-pipeline-design.md](superpowers/specs/2026-08-02-papers-pipeline-design.md))

- [ ] 탑티어 판정 기준(예: oral/spotlight만 vs poster도 포함)을 넓히거나 좁힐 필요가 보이면 → 확인 후 변경
- [ ] Semantic Scholar API 요청이 무료 한도(100req/5분)에 근접하면 → 키 신청 여부를 먼저 확인 (임의로 캐싱 전략 바꾸지 말고 상의)
- [ ] 딥 분석 대상 논문 수(N)를 늘리면 Anthropic API 비용이 커짐 → 기본값에서 변경 전 확인

이 체크리스트는 새 상황이 생길 때마다 이 문서에 항목을 추가해서 계속 키워나갈 것.

---

## 7. 로드맵 / 추후 개발

- **figure 블록 자동 레이아웃 설계** — `exBlog.html`의 예시는 좌표를 손으로 정밀 조정한 것이라 그대로 재현할 수 없다. `flow`/`compare`/`stack` 타입별 자동 배치 알고리즘(그리드 기반이면 충분), 노드 강조(emphasis) 필드, 라벨 줄바꿈 규칙을 별도로 설계해야 한다. Phase 1 범위에서 제외됨.
- **포스트 상세 페이지 템플릿** — `content_html`을 실제로 감싸서 보여줄 `pages/` 쪽 아티클 셸(article-header, article-body, code-block/terminal/figure CSS)이 아직 없다. `exBlog.html`이 레퍼런스.
- **논문 추천 콘텐츠도 동일한 컴포넌트 체계를 따른다** — 논문 추천 cron(섹션 3.2)이 생성하는 초안도 수동 작성 글과 동일하게 섹션 2의 code/terminal/figure 컴포넌트 문법을 사용해야 한다. 즉 섹션 4의 클로드 프롬프트 규칙(특히 2~5번)은 `POST /api/drafts`뿐 아니라 논문 추천 cron의 초안 생성 프롬프트에도 그대로 적용한다 — 두 개의 서로 다른 프롬프트/렌더링 규칙을 따로 만들지 않는다.
- **RAG 기반 논문 검색 + admin 로그인** — 논문을 추천만 하는 게 아니라 RAG로 분석하고, admin 로그인 후 관련 DB를 RAG로 검색할 수 있게 하는 기능. 아직 스펙 없음.
