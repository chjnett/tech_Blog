# TODO — 전체 진행 현황

이 문서 하나로 모든 phase의 진행 상황을 관리합니다. 대(大) phase는 독립적으로 브레인스토밍
→ 스펙 → 플랜 사이클을 도는 단위, 소(小) 항목은 그 안의 태스크/서브아이템입니다. 전체 설계는
[`docs/HANDOFF.md`](HANDOFF.md), 항상-먼저-확인 체크리스트는
[`docs/HANDOFF.md#6-체크포인트-질문`](HANDOFF.md#6-체크포인트-질문) — 별도 리스트이니 여기
섞지 않음.

## 블로킹 / 결정 필요

- [ ] **프로덕션 도메인 미정.** `worker/wrangler.toml`의 `routes`/`SITE_URL`이
      `<YOUR_DOMAIN>` 플레이스홀더 — `wrangler deploy` 전에만 필요 (로컬 개발엔 불필요).
- [x] ~~ponytail 플러그인 설치~~ — 완료.

---

## Phase 1 — 기반 (Workers + D1 + 퍼블릭 API) — 완료 (7/7)

Plan: [`2026-08-02-blog-phase1-foundation.md`](superpowers/plans/2026-08-02-blog-phase1-foundation.md)
(Subagent-Driven Development로 실행, 최종 브랜치 리뷰까지 완료)

- [x] Task 1: Worker 스캐폴딩 + D1 데이터베이스 생성
- [x] Task 2: D1 `posts` 스키마 + 로컬 시드 데이터
- [x] Task 3: `GET /api/posts`, `GET /api/posts/:slug`
- [x] Task 4: `GET /rss.xml`
- [x] Task 5: 터미널 블록(` ```terminal `) 렌더링
- [x] Task 6: Prism.js 코드 블록 신택스 하이라이팅
- [x] Task 7: `pages/` 이동 + 공유 디자인 토큰 + Worker Routes

로컬 D1에 실제 글 1편(`attention-is-all-you-need-kv-cache-gqa`)을 넣어 전체 파이프라인
(마크다운 → Prism 하이라이팅 → JSON API)을 검증함. 예쁜 페이지로 보려면 아래 "포스트 상세
페이지 템플릿" 항목이 필요 — 현재는 `/api/posts/:slug`로 JSON만 확인 가능.

## Phase 1.5 — figure 블록 렌더러 + 포스트 상세 페이지 — 스펙 완료, 플랜 미작성

Spec: [`2026-08-02-figure-block-and-post-page-design.md`](superpowers/specs/2026-08-02-figure-block-and-post-page-design.md)

- [ ] `writing-plans`로 구현 플랜 작성
- [ ] `worker/src/figure.ts` — JSON→SVG 레이어드 자동 배치 렌더러 (`emphasis` 필드, flow/compare/stack)
- [ ] `GET /posts/:slug` Worker SSR 라우트 (article 셸 + `/mark.jpg` 로고)
- [ ] `pages/blog.css` — code/terminal/figure 공유 스타일시트, Prism 토큰 → 4색 매핑
- [ ] `worker/wrangler.toml`에 `/posts/*` Worker Route 추가

## Phase 2 — 리뷰 대시보드 — 미착수 (스펙 없음)

- [ ] `GET/POST /admin/review*` (draft 목록 조회 / 승인 / 수정 / 반려)
- [ ] 접근 제한 방식 결정 (비밀번호 또는 Cloudflare Access)
- [ ] 브레인스토밍 → 스펙 → 플랜부터 시작해야 함

## Phase 3 — 논문 소싱 & 분석 파이프라인 — 스펙 완료, 플랜 미작성

Spec: [`2026-08-02-papers-pipeline-design.md`](superpowers/specs/2026-08-02-papers-pipeline-design.md)

- [ ] `writing-plans`로 구현 플랜 작성
- [ ] arXiv + OpenReview 수집 워커
- [ ] Semantic Scholar 정제/dedupe (venue, decision, citation_count 채움)
- [ ] 탑티어 필터(oral/spotlight) + 관심사 스코어링
- [ ] 딥 분석 (상위 N편만, `analysis_md`)
- [ ] figure 블록 포함 초안 생성 → `posts` insert (`status='draft'`)
- [ ] `papers` 테이블 마이그레이션 (Phase 1의 `posts`와 별도)

## Phase 4 — 깃허브 웹훅 → 커밋 기반 초안 — 미착수 (스펙 없음)

- [ ] `commit_log` 테이블 마이그레이션
- [ ] 웹훅 대상 레포/브랜치 확인 (전체 커밋 초안화 시 노이즈 우려 — 체크포인트 항목)

## Phase 5 — 수동 초안 API (`POST /api/drafts`) — 미착수 (스펙 없음)

- [ ] 메모/링크 → Anthropic API(or Gemini) 초안 생성 → `status='draft'`

## Phase 6 — R2 이미지 업로드 — 미착수 (스펙 없음)

- [ ] R2 버킷 바인딩, 업로드 플로우, `cover_image_key` 연결

## Phase 7 — RAG 기반 논문 검색 + admin 로그인 — 미착수 (스펙 없음)

- [ ] 논문 벡터 DB 구축
- [ ] admin 로그인
- [ ] RAG 검색 인터페이스

---

## Phase 1 최종 리뷰에서 넘어온 항목 (블로킹 아님, Phase 1.5에서 같이 처리)

- [ ] RSS `<link>`/`<guid>`의 slug가 `escapeXml` 안 됨 (현재는 슬러그를 사람이 직접
      지어서 위험 없음 — 슬러그 자동생성이 생기면 반드시 처리)
- [ ] `content_md`에 들어간 원본 HTML을 `marked`가 그대로 통과시킴 — 지금은 신뢰된
      수동 콘텐츠뿐이라 문제 없지만, Phase 3(논문 자동 초안) 등 기계 생성 콘텐츠가
      `posts`에 들어가기 전에 sanitize 전략을 정해야 함
