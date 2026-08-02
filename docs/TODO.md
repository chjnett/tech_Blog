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

## Phase 1 — 기반 (Workers + D1 + 퍼블릭 API) — 진행 중 (4/7)

Plan: [`2026-08-02-blog-phase1-foundation.md`](superpowers/plans/2026-08-02-blog-phase1-foundation.md)
(Subagent-Driven Development로 실행 중)

- [x] Task 1: Worker 스캐폴딩 + D1 데이터베이스 생성
- [x] Task 2: D1 `posts` 스키마 + 로컬 시드 데이터
- [x] Task 3: `GET /api/posts`, `GET /api/posts/:slug`
- [x] Task 4: `GET /rss.xml`
- [ ] Task 5: 터미널 블록(` ```terminal `) 렌더링
- [ ] Task 6: Prism.js 코드 블록 신택스 하이라이팅
- [ ] Task 7: `pages/` 이동 + 공유 디자인 토큰 + Worker Routes

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

## 설계는 됐지만 어느 Phase에도 아직 안 들어간 것

- [ ] **figure 블록 자동 레이아웃.** `exBlog.html`은 좌표를 손으로 조정한 예시라 그대로
      재현 불가 — `flow`/`compare`/`stack`별 그리드 자동 배치, 노드 강조(emphasis) 필드,
      라벨 줄바꿈 규칙을 별도 설계해야 함. (`docs/HANDOFF.md` §2.3, §7)
- [ ] **포스트 상세 페이지 템플릿.** `content_html`을 실제로 감싸서 보여줄 `pages/`
      아티클 셸(article-header/article-body + code-block/terminal/figure CSS)이 아직
      없음. Phase 1의 Task 6이 Worker가 내보내는 실제 클래스명(Prism 토큰 등)을 정하니,
      그 이후에 착수.
