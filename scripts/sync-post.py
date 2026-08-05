#!/usr/bin/env python3
"""
sync-post.py — posts-source/<slug>.md 파일을 읽어 로컬 D1의 posts 테이블에 반영한다.

사용법:
    python3 scripts/sync-post.py posts-source/<slug>.md
    python3 scripts/sync-post.py posts-source/<slug>.md --remote   # 배포된 프로덕션 D1에 반영

파일 형식 (frontmatter + 마크다운 본문):

    ---
    slug: my-post-slug
    title: 글 제목
    excerpt: 목록에 보일 한두 문장 요약
    tags: [transformer, attention]
    status: draft
    source_ref: https://github.com/... (선택)
    ---
    (마크다운 본문 — title은 여기 다시 안 써도 됨, 페이지 템플릿이 따로 렌더링함)

status는 draft | in_review | published 중 하나. published일 때만 홈/목록/RSS에 노출된다.
기존에 같은 slug의 글이 D1에 있으면 id/created_at을 유지하고 내용만 갱신한다.
"""
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKER_DIR = REPO_ROOT / "worker"


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise ValueError("파일이 '---'로 시작하는 frontmatter가 없습니다")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("frontmatter가 '---'로 열리고 닫혀야 합니다")
    _, fm_text, body = parts
    fields: dict = {}

    def unquote(s: str) -> str:
        # Only strip quotes that actually wrap the whole value — a leading or
        # trailing quote that's part of the real content (e.g. a title like
        # `"Attention Is All You Need"를 읽다가...`) must survive untouched.
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
            return s[1:-1]
        return s

    for line in fm_text.strip().splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "tags":
            inner = value.strip("[]")
            fields[key] = [unquote(t.strip()) for t in inner.split(",") if t.strip()]
        else:
            fields[key] = unquote(value)
    return fields, body.lstrip("\n")


def sql_escape(value: str) -> str:
    return value.replace("'", "''")


def d1_query(sql: str, remote: bool) -> list:
    cmd = ["npx", "wrangler", "d1", "execute", "tech_blog_db", "--json", "--command", sql]
    cmd.append("--remote" if remote else "--local")
    result = subprocess.run(cmd, cwd=WORKER_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError("wrangler d1 execute 실패")
    data = json.loads(result.stdout)
    return data[0]["results"]


def d1_run_file(sql_path: Path, remote: bool) -> None:
    cmd = ["npx", "wrangler", "d1", "execute", "tech_blog_db", "--file", str(sql_path)]
    cmd.append("--remote" if remote else "--local")
    result = subprocess.run(cmd, cwd=WORKER_DIR, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError("wrangler d1 execute 실패")


def main() -> None:
    args = sys.argv[1:]
    remote = "--remote" in args
    args = [a for a in args if a != "--remote"]
    if len(args) != 1:
        print("사용법: python3 scripts/sync-post.py posts-source/<slug>.md [--remote]", file=sys.stderr)
        sys.exit(1)

    md_path = Path(args[0]).resolve()
    fields, body = parse_frontmatter(md_path.read_text(encoding="utf-8"))

    for required in ("slug", "title", "status"):
        if required not in fields:
            print(f"frontmatter에 '{required}' 필드가 필요합니다", file=sys.stderr)
            sys.exit(1)

    slug = fields["slug"]
    title = fields["title"]
    excerpt = fields.get("excerpt", "")
    tags = fields.get("tags", [])
    status = fields["status"]
    source_ref = fields.get("source_ref") or None

    if status not in ("draft", "in_review", "published", "rejected"):
        print(f"status는 draft|in_review|published|rejected 중 하나여야 합니다 (받은 값: {status})", file=sys.stderr)
        sys.exit(1)

    existing = d1_query(f"SELECT id, created_at, published_at FROM posts WHERE slug = '{sql_escape(slug)}'", remote)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if existing:
        post_id = existing[0]["id"]
        created_at = existing[0]["created_at"]
        published_at = existing[0]["published_at"] if status == "published" else None
        if status == "published" and not published_at:
            published_at = now
    else:
        post_id = str(uuid.uuid4())
        created_at = now
        published_at = now if status == "published" else None

    tags_json = json.dumps(tags, ensure_ascii=False)
    source_ref_sql = f"'{sql_escape(source_ref)}'" if source_ref else "NULL"
    published_at_sql = f"'{published_at}'" if published_at else "NULL"

    sql = f"""INSERT INTO posts (id, slug, title, content_md, excerpt, source_type, source_ref, status, tags, cover_image_key, created_at, published_at)
VALUES (
  '{sql_escape(post_id)}',
  '{sql_escape(slug)}',
  '{sql_escape(title)}',
  '{sql_escape(body)}',
  '{sql_escape(excerpt)}',
  'manual',
  {source_ref_sql},
  '{sql_escape(status)}',
  '{sql_escape(tags_json)}',
  NULL,
  '{created_at}',
  {published_at_sql}
)
ON CONFLICT(slug) DO UPDATE SET
  title = excluded.title,
  content_md = excluded.content_md,
  excerpt = excluded.excerpt,
  source_ref = excluded.source_ref,
  status = excluded.status,
  tags = excluded.tags,
  published_at = excluded.published_at;
"""

    tmp_sql = REPO_ROOT / ".sync-post-tmp.sql"
    tmp_sql.write_text(sql, encoding="utf-8")
    try:
        d1_run_file(tmp_sql, remote)
    finally:
        tmp_sql.unlink(missing_ok=True)

    target = "REMOTE(프로덕션)" if remote else "로컬"
    print(f"✓ '{slug}' → {target} D1에 반영됨 (status={status})")


if __name__ == "__main__":
    main()
