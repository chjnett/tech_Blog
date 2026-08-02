import { listPublishedPosts } from '../db';

function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

export async function handleRss(db: D1Database, siteUrl: string): Promise<Response> {
  const rows = await listPublishedPosts(db);

  const items = rows
    .map(
      (row) => `
    <item>
      <title>${escapeXml(row.title)}</title>
      <link>${siteUrl}/posts/${row.slug}</link>
      <guid>${siteUrl}/posts/${row.slug}</guid>
      <pubDate>${new Date(row.published_at as string).toUTCString()}</pubDate>
      <description>${escapeXml(row.excerpt ?? '')}</description>
    </item>`
    )
    .join('');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>chjnett.dev blog</title>
    <link>${siteUrl}</link>
    <description>Hyeonjun Cheon's blog</description>${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: { 'Content-Type': 'application/rss+xml; charset=utf-8' },
  });
}
