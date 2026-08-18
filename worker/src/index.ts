import { handleListPosts, handleGetPostBySlug } from './routes/posts';
import { handleRss } from './routes/rss';
import { handlePostPage } from './routes/post-page';
import { handlePublishPost, isAuthorized } from './routes/admin';
import { handleListPrs, handleRefreshPrs, handleLinkPrPost } from './routes/prs';
import { incrementViews, listPopular } from './views';
import { listPublishedPosts } from './db';

export interface Env {
  DB: D1Database;
  SITE_URL: string;
  ADMIN_TOKEN?: string;
  GITHUB_TOKEN?: string;
  POSTS_META: KVNamespace;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { pathname } = new URL(request.url);

    try {
      if (pathname === '/api/posts' && request.method === 'GET') {
        return await handleListPosts(env.DB, env.POSTS_META);
      }

      // 조회수 증가 (글 페이지 진입 시 호출)
      const viewsMatch = pathname.match(/^\/api\/posts\/([^/]+)\/views$/);
      if (viewsMatch && request.method === 'POST') {
        const v = await incrementViews(env.POSTS_META, viewsMatch[1]);
        return Response.json({ slug: viewsMatch[1], views: v });
      }

      // 인기글 랭킹
      if (pathname === '/api/popular' && request.method === 'GET') {
        const rows = await listPublishedPosts(env.DB);
        const popular = await listPopular(env.POSTS_META, rows.map((r) => r.slug));
        // 발행 글 slug→제목 매핑
        const bySlug = new Map(rows.map((r) => [r.slug, r.title]));
        return Response.json(
          popular
            .filter((p) => bySlug.has(p.slug))
            .map((p) => ({ slug: p.slug, title: bySlug.get(p.slug), views: p.views }))
        );
      }

      const slugMatch = pathname.match(/^\/api\/posts\/([^/]+)$/);
      if (slugMatch && request.method === 'GET') {
        return await handleGetPostBySlug(env.DB, slugMatch[1], env.POSTS_META);
      }

      if (pathname === '/rss.xml' && request.method === 'GET') {
        return await handleRss(env.DB, env.SITE_URL);
      }

      const postPageMatch = pathname.match(/^\/posts\/([^/]+)$/);
      if (postPageMatch && request.method === 'GET') {
        return await handlePostPage(env.DB, postPageMatch[1], env.POSTS_META);
      }

      // 기여 상세 페이지(/oss/:slug) — posts 테이블의 oss-* 글로, post-page 셸 재사용.
      // source_ref에 PR/GitHub 링크를 넣으면 동일하게 GitHub 배지가 표시된다.
      const ossPageMatch = pathname.match(/^\/oss\/([^/]+)$/);
      if (ossPageMatch && request.method === 'GET') {
        return await handlePostPage(env.DB, ossPageMatch[1], env.POSTS_META);
      }

      if (pathname === '/api/prs' && request.method === 'GET') {
        return await handleListPrs(env.DB);
      }

      if (pathname === '/api/prs/refresh' && request.method === 'POST') {
        return await handleRefreshPrs(request, env.DB, env.GITHUB_TOKEN);
      }

      if (pathname === '/api/prs/link' && request.method === 'POST') {
        return await handleLinkPrPost(request, env.DB, env.ADMIN_TOKEN);
      }

      if (pathname === '/admin/publish' && request.method === 'POST') {
        if (!(await isAuthorized(request, env.ADMIN_TOKEN))) {
          return Response.json({ error: 'unauthorized' }, { status: 401 });
        }
        const body = await request.json<Record<string, unknown>>();
        return await handlePublishPost(env.DB, body);
      }

      return Response.json({ error: 'not found' }, { status: 404 });
    } catch (err) {
      console.error(err);
      return Response.json({ error: 'internal error' }, { status: 500 });
    }
  },
};
