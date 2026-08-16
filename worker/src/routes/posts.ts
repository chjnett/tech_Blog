import type { PostSummary } from '../types';
import { listPublishedPosts, getPublishedPostBySlug } from '../db';
import { renderMarkdown } from '../render';
import { parseTags } from '../utils';

function toSummary(row: PostSummary) {
  return {
    id: row.id,
    slug: row.slug,
    title: row.title,
    excerpt: row.excerpt,
    tags: parseTags(row.tags),
    cover_image_key: row.cover_image_key,
    published_at: row.published_at,
  };
}

export async function handleListPosts(db: D1Database): Promise<Response> {
  const rows = await listPublishedPosts(db);
  return Response.json(rows.map(toSummary));
}

export async function handleGetPostBySlug(db: D1Database, slug: string): Promise<Response> {
  const row = await getPublishedPostBySlug(db, slug);
  if (!row) {
    return Response.json({ error: 'not found' }, { status: 404 });
  }
  return Response.json({
    id: row.id,
    slug: row.slug,
    title: row.title,
    content_html: renderMarkdown(row.content_md),
    excerpt: row.excerpt,
    tags: parseTags(row.tags),
    cover_image_key: row.cover_image_key,
    published_at: row.published_at,
  });
}
