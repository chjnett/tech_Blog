// 리뷰 대시보드(HANDOFF.md §5-6)가 구현되기 전까지 쓰는 임시 발행 경로.
// 대시보드가 생기면 이 파일째 제거한다.
//
// 타이밍 공격에 안전한 비교. 길이가 다르면 즉시 false지만, 토큰 길이 자체는
// 비밀이 아니므로 문제되지 않는다.
function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

export function isAuthorized(request: Request, expected: string | undefined): boolean {
  // 시크릿이 없으면 열어두지 않고 잠근다 — 설정 누락이 곧 공개가 되면 안 된다.
  if (!expected) return false;
  const header = request.headers.get('Authorization') ?? '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : '';
  return token.length > 0 && safeEqual(token, expected);
}

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
