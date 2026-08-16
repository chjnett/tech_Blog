import type { PostDetail, PostSummary } from './types';
import type { GitHubPrRow } from './github';

// 목록/RSS는 content_md를 필요로 하지 않는다. SELECT * 대신 필요한 컬럼만
// 조회해 D1에서 읽어오는 바이트를 줄인다.

export async function listPublishedPosts(db: D1Database): Promise<PostSummary[]> {
  const { results } = await db
    .prepare(
      "SELECT id, slug, title, excerpt, tags, cover_image_key, published_at FROM posts WHERE status = 'published' ORDER BY published_at DESC"
    )
    .all<PostSummary>();
  return results;
}

export async function getPublishedPostBySlug(
  db: D1Database,
  slug: string
): Promise<PostDetail | null> {
  const row = await db
    .prepare(
      "SELECT id, slug, title, content_md, excerpt, source_ref, tags, cover_image_key, published_at FROM posts WHERE slug = ? AND status = 'published'"
    )
    .bind(slug)
    .first<PostDetail>();
  return row ?? null;
}

// ── pr_status: 홈 PR 섹션용 캐시 ──────────────────────────────────────

export async function listPrs(db: D1Database): Promise<GitHubPrRow[]> {
  const { results } = await db
    .prepare(
      "SELECT repo, pr_number, title, url, state, merged, head_sha, ci_combined, authored_at, updated_at, post_slug FROM pr_status ORDER BY CASE WHEN state='open' THEN 0 ELSE 1 END, updated_at DESC"
    )
    .all<GitHubPrRow>();
  return results;
}

export async function getPrLastUpdated(db: D1Database): Promise<string | null> {
  const row = await db
    .prepare('SELECT MAX(updated_at) AS m FROM pr_status')
    .first<{ m: string | null }>();
  return row?.m ?? null;
}

export async function upsertPrs(db: D1Database, rows: GitHubPrRow[]): Promise<void> {
  const stmt = db.prepare(`
    INSERT INTO pr_status (repo, pr_number, title, url, state, merged, head_sha, ci_combined, authored_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(repo, pr_number) DO UPDATE SET
      title = excluded.title,
      url = excluded.url,
      state = excluded.state,
      merged = excluded.merged,
      head_sha = excluded.head_sha,
      ci_combined = excluded.ci_combined,
      authored_at = excluded.authored_at,
      updated_at = excluded.updated_at
      -- post_slug는 refresh가 건드리지 않는다(보존). 연결은 별도 엔드포인트로만.
  `);

  await db.batch(
    rows.map((r) =>
      stmt.bind(
        r.repo,
        r.pr_number,
        r.title,
        r.url,
        r.state,
        r.merged ? 1 : 0,
        r.head_sha,
        r.ci_combined,
        r.authored_at,
        r.updated_at
      )
    )
  );
}

/** 특정 PR에 기여 상세 글(post_slug)을 연결한다. */
export async function setPrPostSlug(
  db: D1Database,
  repo: string,
  prNumber: number,
  postSlug: string | null
): Promise<void> {
  await db
    .prepare('UPDATE pr_status SET post_slug = ? WHERE repo = ? AND pr_number = ?')
    .bind(postSlug, repo, prNumber)
    .run();
}
