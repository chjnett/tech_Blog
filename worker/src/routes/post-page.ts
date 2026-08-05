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
  const codeLinkHtml = row.source_ref
    ? `<a class="code-link" href="${escapeHtml(row.source_ref)}" target="_blank" rel="noopener" title="전체 코드 보기" aria-label="전체 코드 보기">
        <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true">
          <path d="M12 0.5C5.65 0.5 0.5 5.65 0.5 12c0 5.08 3.29 9.39 7.86 10.91.57.1.78-.25.78-.55 0-.27-.01-1.16-.02-2.11-3.2.7-3.88-1.36-3.88-1.36-.52-1.33-1.28-1.68-1.28-1.68-1.04-.72.08-.7.08-.7 1.15.08 1.76 1.19 1.76 1.19 1.03 1.75 2.69 1.25 3.35.96.1-.75.4-1.25.73-1.53-2.55-.29-5.24-1.28-5.24-5.7 0-1.26.45-2.29 1.19-3.09-.12-.29-.52-1.47.11-3.06 0 0 .97-.31 3.18 1.18a11.05 11.05 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.77.11 3.06.74.8 1.19 1.83 1.19 3.09 0 4.43-2.69 5.41-5.25 5.69.41.36.78 1.07.78 2.15 0 1.55-.01 2.8-.01 3.18 0 .3.21.66.79.55A10.51 10.51 0 0 0 23.5 12C23.5 5.65 18.35 0.5 12 0.5Z"/>
        </svg>
        <span>전체 코드 보기</span>
      </a>`
    : '';

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
    ${codeLinkHtml}
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
