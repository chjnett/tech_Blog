# GitHub PR 상태 점검 — 홈 섹션 스펙

`docs/HANDOFF.md` §7 로드맵의 "RAG/논문 검색"과는 별개로, 내가 오픈소스에 기여한 PR의
현재 상태를 홈페이지에 보여주는 섹션이다. 기존 디자인 시스템(모노크롬, code/terminal/figure
컴포넌트)을 **그대로 유지**하면서, 홈(`pages/index.html`) 아래에 PR 목록 카드 영역을 추가한다.

## 1. 목표

- "내가 올린 모든 PR"의 상태를 한눈에: 열림(리뷰 대기·CI 실패·머지 충돌) / 변경 요청 / 머지됨.
- 매 방문 때마다 GitHub API를 때리지 않도록, 최신 상태를 캐시한다.
- 디자인 시스템 규칙(컬러는 코드 블록 안에서만, 강조는 굵기·테두리·흑백 반전·위치로)을 어기지 않는다.

## 2. 사용할 GitHub API

| API | 용도 | 인증/제한 |
|---|---|---|
| `GET /search/issues?q=author:{user}+type:pr` | 내가 올린 모든 PR 목록 (제목·repo·번호·상태) | 인증 없이 10 req/min, **토큰 시 30 req/min** → 이번엔 토큰 사용 |
| `GET /repos/{owner}/{repo}/commits/{sha}/status` | 각 PR의 head 커밋 CI 상태 (결합 상태) | 무인증 60 req/h, 토큰 시 5000 req/h → 토큰 사용 |

PR 목록 1회 조회 후 각 PR의 CI 상태를 병렬로 조회한다. 검색 API 결과에 `status`(open/closed),
`merged_at`, `html_url`, `repository_url`, `head.sha`가 포함되므로, 머지/열림 판정은 목록만으로
충분하고 CI 상태만 head 커밋 조회가 필요하다.

## 3. GitHub 사용자명 / 표시 범위

- 사용자명: `chjnett` (이 저장소 remote의 소유자)
- "내가 올린 모든 PR" = `author:chjnett type:pr`. 공개 repo의 PR이 대상(비공개 repo는 토큰이
  그 repo 권한을 가질 때만 — 권한이 없으면 자동 제외됨).

## 4. D1 스키마 (새 테이블: pr_status)

PR 상태를 캐시하고, 홈은 매 요청에 DB만 읽는다 (GitHub API는 cron/수동 갱신 시에만 호출).

```sql
CREATE TABLE pr_status (
  repo TEXT NOT NULL,             -- 'owner/repo'
  pr_number INTEGER NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL,              -- PR html_url
  state TEXT NOT NULL,            -- 'open' | 'closed'
  merged BOOLEAN NOT NULL DEFAULT 0,  -- 머지 여부
  head_sha TEXT,
  ci_combined TEXT,               -- null | 'success' | 'failure' | 'pending'
  authored_at TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (repo, pr_number)
);
```

`posts`와 달리 이 테이블은 "발행 승인" 개념이 없다. PR 상태는 사실 데이터이므로 표시 자체가
승인 행위가 아니다. 다만 자동으로 뭔가를 **발행**하는 것이 없음을 확인한다.

## 5. Worker 라우트 / 동작

- `GET /api/prs` — D1 `pr_status` 읽어 홈용 JSON 반환 (홈은 그대로 표시).
  - 정렬: 열림 PR 먼저 → `updated_at` 최신순.
  - CI 합계: 모든 PR 중 `failure` 수, `pending` 수를 같이 내려준다.

- `POST /api/prs/refresh` — GitHub API 조회 → D1 `pr_status` UPSERT.
  - 인증: `Authorization: Bearer <GITHUB_TOKEN>` (관리자용). `wrangler secret put GITHUB_TOKEN`.
  - 시크릿이 없으면 잠긴다(401) — 기존 `isAuthorized` 로직 재사용.

- 갱신 주기: 처음엔 **수동 `POST /api/prs/refresh` + 섹션에 "마지막 갱신 시각" 표시**.
  자동 cron은 비용·호출 빈도를 사용자와 합의 후 추가(체크포인트 항목).

## 6. 디자인 (기존 시스템 유지)

- 홈 `index.html`의 `.posts` 근처에 `#pr` 섹션 추가. 스타일은 `index.html`의 인라인 CSS에
  기존 토큰(`--ink`/`--ink-soft`/`--line`/`--bg-soft`)만 사용.
- PR 카드: repo 라벨(mono, `--ink-soft`) + 타이틀(굵기만, 색 없음) + 상태 배지.
- **상태 배지는 색을 쓰지 않고 텍스트·테두리·흑백 반전으로 구분**:
  - 머지됨: `— merged` (짙은 테두리, 굵은 텍스트)
  - 열림·리뷰 대기: `open` (가는 테두리)
  - CI 실패: `✗ CI failure` (텍스트만, 굵기로 강조 — 색 없음)
  - CI 진행 중: `… pending`
- 파일/목록 항목이 아니라 **홈의 한 섹션**이므로 "새 콘텐츠 컴포넌트"(코드/터미널/피규어 외
  새 블록)가 아니라 기존 홈 레이아웃의 확장이다. 글 본문 안에는 새 컴포넌트를 추가하지 않는다.

## 7. 구현 순서

1. `wrangler secret put GITHUB_TOKEN` (사용자 GitHub PAT — repo read + public read 권한)
2. D1 마이그레이션: `pr_status` 테이블 생성 (기존 `posts` 데이터 무영향 — 새 테이블만 추가)
3. Worker: `db.ts`에 `pr_status` 조회/업서트 추가 → `/api/prs` + `/api/prs/refresh` 라우트
4. 홈: `index.html`에 PR 섹션 + `/api/prs` fetch 렌더
5. 로컬 검증 → 배포 → 수동 refresh

## 8. 체크포인트 질문 (구현 전 사용자 확인)

- [ ] GitHub 기능을 위해 **홈에 카드 섹션을 추가**하는 것이 맞는지 (기존 홈이 포트폴리오+글 목록인데 PR 섹션이 들어가도 되는지)
- [ ] `GITHUB_TOKEN`을 직접 발급해 `wrangler secret put`으로 넣어줄 수 있는지 (Worker가 사용)
- [ ] PR 상태를 수동 갱신으로 시작할지, 아니면 cron 자동 갱신(하루 1~2회)까지 원하는지
- [ ] CI 상태(CI 실패 강조)까지 표시할지, 아니면 머지/열림 상태만 표시할지

## 9. 범위 제외

- 리뷰 대시보드와 같은 "발행 승인" 흐름은 만들지 않는다 (PR 상태는 표시만).
- 논문 파이프라인(papers)와는 무관.
- 새 콘텐츠 블록(글 본문 안)은 만들지 않는다.
