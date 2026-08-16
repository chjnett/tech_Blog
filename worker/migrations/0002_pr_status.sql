-- pr_status: 홈 PR 섹션이 github.com에서 조회한 내 PR 상태를 캐시하는 테이블.
-- posts와 무관한 별도 사실 데이터. 스키마: docs/superpowers/specs/2026-08-16-github-pr-status-design.md
CREATE TABLE IF NOT EXISTS pr_status (
  repo TEXT NOT NULL,                -- 'owner/repo'
  pr_number INTEGER NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL,                 -- PR html_url
  state TEXT NOT NULL,               -- 'open' | 'closed'
  merged BOOLEAN NOT NULL DEFAULT 0, -- 머지 여부
  head_sha TEXT,
  ci_combined TEXT,                  -- null | 'success' | 'failure' | 'pending'
  authored_at TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (repo, pr_number)
);
