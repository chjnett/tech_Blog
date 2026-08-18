import type { PostSummary } from '../types';
import { listPublishedPosts, getPublishedPostBySlug } from '../db';
import { renderMarkdown } from '../render';
import { parseTags } from '../utils';
import { getViews } from '../views';

async function toSummary(row: PostSummary, kv: KVNamespace) {
  return {
    id: row.id,
    slug: row.slug,
    title: row.title,
    excerpt: row.excerpt,
    tags: parseTags(row.tags),
    cover_image_key: row.cover_image_key,
    published_at: row.published_at,
    views: await getViews(kv, row.slug),
  };
}

export async function handleListPosts(db: D1Database, kv: KVNamespace): Promise<Response> {
  const rows = await listPublishedPosts(db);
  const out = await Promise.all(rows.map((r) => toSummary(r, kv)));
  return Response.json(out);
}

export async function handleGetPostBySlug(db: D1Database, slug: string, kv: KVNamespace): Promise<Response> {
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
    views: await getViews(kv, row.slug),
  });
}
