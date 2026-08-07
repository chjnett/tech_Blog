import type { PostRow } from '../types';

export async function handlePublishPost(
  db: D1Database,
  body: Record<string, unknown>
): Promise<Response> {
  const {
    slug,
    title,
    excerpt,
    content_md,
    tags,
    source_ref,
  } = body as {
    slug: string;
    title: string;
    excerpt: string;
    content_md: string;
    tags: string[];
    source_ref: string;
  };

  if (!slug || !title || !content_md) {
    return Response.json(
      { error: 'Missing required fields: slug, title, content_md' },
      { status: 400 }
    );
  }

  const now = new Date().toISOString();
  const postId = `post_${slug}`;
  const tagsJson = JSON.stringify(tags || []);

  try {
    // Check if post already exists
    const existing = await db
      .prepare('SELECT id FROM posts WHERE slug = ?')
      .bind(slug)
      .first<{ id: string }>();

    if (existing) {
      // Update existing post
      await db
        .prepare(`
          UPDATE posts
          SET title = ?, excerpt = ?, content_md = ?, tags = ?,
              status = 'published', published_at = ?
          WHERE slug = ?
        `)
        .bind(title, excerpt, content_md, tagsJson, now, slug)
        .run();

      return Response.json({
        success: true,
        message: 'Post updated and published',
        slug,
      });
    } else {
      // Create new post
      await db
        .prepare(`
          INSERT INTO posts (
            id, slug, title, content_md, excerpt, source_type, source_ref,
            status, tags, cover_image_key, created_at, published_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `)
        .bind(
          postId,
          slug,
          title,
          content_md,
          excerpt,
          'manual',
          source_ref,
          'published',
          tagsJson,
          null,
          now,
          now
        )
        .run();

      return Response.json({
        success: true,
        message: 'Post created and published',
        slug,
      });
    }
  } catch (err) {
    console.error('Publish error:', err);
    return Response.json(
      { error: `Failed to publish: ${(err as Error).message}` },
      { status: 500 }
    );
  }
}
