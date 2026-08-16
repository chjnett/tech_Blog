import type { PostDetail, PostSummary } from './types';

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
