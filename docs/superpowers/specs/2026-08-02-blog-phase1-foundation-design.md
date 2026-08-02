# Phase 1: 기반 (Workers + D1 + 퍼블릭 API) 설계

## 배경

전체 블로그 자동화 시스템(Pages 정적 셸 + Workers API + D1 + R2, 리뷰 승인
기반 발행, 논문 추천 cron, 깃허브 커밋 기반 초안 등)은 여러 독립된
서브시스템으로 구성된다. 이번 스펙은 그중 가장 먼저 만들어야 하는
기반(foundation)만 다룬다: Workers 프로젝트 세팅, D1 스키마(posts만),
퍼블릭 읽기 API. 나머지(리뷰 대시보드, 논문 cron, 깃허브 웹훅, 수동 초안
API, R2 업로드, RAG)는 이 기반 위에서 각각 별도 스펙으로 진행한다.

## 목표

- Pages(정적 셸)와 Workers(API)를 하나의 커스텀 도메인에서 서빙
- D1에 `posts` 테이블을 두고, 승인된(published) 글만 퍼블릭 API로 노출
- `GET /api/posts`, `GET /api/posts/:slug`, `GET /rss.xml` 구현
- 로컬 `wrangler dev` + 시드 데이터로 동작 검증

## 범위 밖 (다음 스펙에서 다룸)

- 리뷰 대시보드(`/admin/review/*`), draft/approve/reject 워크플로우
- 논문 추천 cron, 깃허브 웹훅, 수동 초안 API (`POST /api/drafts`)
- R2 이미지 업로드
- `papers`, `commit_log` 테이블 마이그레이션
- RAG 기반 논문 검색 / admin 로그인

## 아키텍처

```
tech_blog/
├── pages/                 # 정적 셸 (기존 index.html 이동)
│   ├── index.html
│   └── mark.jpg
├── worker/                # Cloudflare Worker (API)
│   ├── src/
│   │   ├── index.ts       # 라우터 엔트리
│   │   ├── routes/
│   │   │   ├── posts.ts   # GET /api/posts, GET /api/posts/:slug
│   │   │   └── rss.ts     # GET /rss.xml
│   │   ├── render.ts      # marked 기반 md→html 변환
│   │   └── db.ts          # D1 쿼리 헬퍼
│   ├── migrations/
│   │   └── 0001_posts.sql
│   ├── seed.sql            # 로컬 테스트용 published 샘플 2~3개
│   ├── wrangler.toml
│   └── package.json
└── design-tokens.json      # 공유 디자인 토큰
```

Pages와 Worker는 같은 커스텀 도메인에서 서빙한다. zone의 Worker Route로
`yourdomain.com/api/*`, `yourdomain.com/rss.xml`만 Worker가 가로채고,
나머지 경로는 Pages가 서빙한다. 별도 서브도메인은 두지 않는다.

## D1 스키마 (이번 단계: posts만)

```sql
CREATE TABLE posts (
  id TEXT PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  content_md TEXT NOT NULL,
  excerpt TEXT,
  source_type TEXT NOT NULL,
  source_ref TEXT,
  status TEXT NOT NULL DEFAULT 'draft',
  tags TEXT,
  cover_image_key TEXT,
  created_at TEXT NOT NULL,
  published_at TEXT
);
```

`papers`, `commit_log`은 해당 기능(cron, 웹훅) 스펙에서 별도 마이그레이션으로
추가한다.

## API 계약

```
GET /api/posts
  → 200: [{ id, slug, title, excerpt, tags, cover_image_key, published_at }, ...]
  → status='published'만, published_at DESC
  → content_md/html은 목록 응답에서 제외 (payload 경량화)

GET /api/posts/:slug
  → 200: { id, slug, title, content_html, excerpt, tags, cover_image_key, published_at }
  → 404: slug가 없거나 status != 'published'

GET /rss.xml
  → 200 (Content-Type: application/rss+xml)
  → published 글 최신순 RSS 2.0 (title, link, pubDate, description=excerpt)
```

- `content_md`는 D1에 원문 그대로 저장, 조회 시점에 `render.ts`(marked
  라이브러리)가 `content_html`로 변환해 응답한다. 매 요청마다 변환하지만
  이 단계 트래픽에서는 문제없다. 캐싱은 필요해지면 추가한다.
- draft/in_review/rejected 상태 글은 퍼블릭 API에서 완전히 숨긴다 —
  존재 자체를 노출하지 않고 404로 응답한다.

## 에러 처리

- `/api/posts/:slug`에서 slug 없음 또는 미승인 상태 → `404 { error: "not found" }`
- D1 쿼리 실패 → `500 { error: "internal error" }`, Workers 로그에 상세 기록
- `/api/posts`는 글이 하나도 없어도 에러 아님 → `200 []`

## 테스트

이 단계는 CRUD 조회 수준의 단순한 로직이므로 자동화 테스트 프레임워크는
도입하지 않는다(YAGNI). `wrangler d1 execute --local`로 마이그레이션 적용 후
`seed.sql`로 published 샘플 2~3건을 넣고, `wrangler dev` + curl로 세 엔드포인트
동작을 수동 검증한다. 다음 단계(리뷰 대시보드, cron 등)에서 로직이 늘어나면
그때 테스트 프레임워크 도입을 재검토한다.

## 의사결정 로그

- Cloudflare 계정과 이 프로젝트용 도메인은 이미 준비됨
- 리포지토리는 모노레포 구조(`pages/` + `worker/`)로 진행
- markdown → HTML 변환 라이브러리는 `marked` (순수 JS, Workers 호환,
  가볍고 커뮤니티 표준). `markdown-it`은 이번 단계엔 과함, 직접 파서는
  엣지케이스 유지보수 부담이 큼
- 변환은 저장 시점이 아닌 조회 시점(Worker)에서 수행 — SEO/RSS에 유리
