-- pr_status에 기여 상세 블로그 글 연결 컬럼 추가.
-- 기존 행/데이터를 깨지 않도록 ADD COLUMN만 수행 (기존 행은 NULL 유지).
-- 스펙: docs/superpowers/specs/2026-08-16-github-pr-status-design.md 부록 B
ALTER TABLE pr_status ADD COLUMN post_slug TEXT;
