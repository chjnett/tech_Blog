import type { PostRow } from './types';

export async function listPublishedPosts(db: D1Database): Promise<PostRow[]> {
  const { results } = await db
    .prepare("SELECT * FROM posts WHERE status = 'published' ORDER BY published_at DESC")
    .all<PostRow>();
  return results;
}

export async function getPublishedPostBySlug(
  db: D1Database,
  slug: string
): Promise<PostRow | null> {
  const row = await db
    .prepare("SELECT * FROM posts WHERE slug = ? AND status = 'published'")
    .bind(slug)
    .first<PostRow>();
  return row ?? null;
}
