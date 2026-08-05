import { getPublishedPostBySlug } from '../db';
import { renderMarkdown } from '../render';

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function parseTags(tags: string | null): string[] {
  if (!tags) return [];
  try {
    return JSON.parse(tags);
  } catch {
    return [];
  }
}

export async function handlePostPage(db: D1Database, slug: string): Promise<Response> {
  const row = await getPublishedPostBySlug(db, slug);
  if (!row) {
    return new Response('Not Found', {
      status: 404,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  }

  const tags = parseTags(row.tags);
  const tagsHtml = tags.map((tag) => `<span class="tag">#${escapeHtml(tag)}</span>`).join('');
  const dateLabel = (row.published_at ?? '').slice(0, 10);

  const html = `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escapeHtml(row.title)} — chjnett.dev</title>
<meta name="description" content="${escapeHtml(row.excerpt ?? '')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/blog.css">
</head>
<body>

<header class="post-header">
  <a href="/"><img class="logo" src="/mark.jpg" alt="chjnett"></a>
</header>

<header class="article-header">
  <div class="article-meta">
    ${tagsHtml}
    <span>${escapeHtml(dateLabel)}</span>
  </div>
  <h1>${escapeHtml(row.title)}</h1>
</header>

<article class="article-body">
${renderMarkdown(row.content_md)}
</article>

<script>
  document.querySelectorAll('.code-block').forEach((block) => {
    const pre = block.querySelector('pre');
    const button = block.querySelector('.code-expand');
    if (!pre || !button) return;
    if (pre.scrollHeight <= 420) return;

    block.classList.add('collapsed');
    button.hidden = false;
    button.textContent = '더 보기';

    button.addEventListener('click', () => {
      const collapsed = block.classList.toggle('collapsed');
      button.textContent = collapsed ? '더 보기' : '접기';
    });
  });
</script>

</body>
</html>`;

  return new Response(html, {
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  });
}
