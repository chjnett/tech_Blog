import { listPublishedPosts } from '../db';
import { escapeXml } from '../utils';

export async function handleRss(db: D1Database, siteUrl: string): Promise<Response> {
  const rows = await listPublishedPosts(db);

  const items = rows
    .map((row) => {
      // slug는 이전까지 escapeXml 없이 URL에 들어가고 있었다. 슬러그 자동생성이
      // 생기면 특수문자가 섞일 수 있으므로 명시적으로 이스케이프한다.
      const postUrl = `${siteUrl}/posts/${encodeURIComponent(row.slug)}`;
      return `
    <item>
      <title>${escapeXml(row.title)}</title>
      <link>${escapeXml(postUrl)}</link>
      <guid>${escapeXml(postUrl)}</guid>
      <pubDate>${new Date(row.published_at as string).toUTCString()}</pubDate>
      <description>${escapeXml(row.excerpt ?? '')}</description>
    </item>`;
    })
    .join('');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>chjnett.dev blog</title>
    <link>${escapeXml(siteUrl)}</link>
    <description>Hyeonjun Cheon's blog</description>${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: { 'Content-Type': 'application/rss+xml; charset=utf-8' },
  });
}
