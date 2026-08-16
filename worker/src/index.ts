import { handleListPosts, handleGetPostBySlug } from './routes/posts';
import { handleRss } from './routes/rss';
import { handlePostPage } from './routes/post-page';
import { handlePublishPost, isAuthorized } from './routes/admin';
import { handleListPrs, handleRefreshPrs } from './routes/prs';

export interface Env {
  DB: D1Database;
  SITE_URL: string;
  ADMIN_TOKEN?: string;
  GITHUB_TOKEN?: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { pathname } = new URL(request.url);

    try {
      if (pathname === '/api/posts' && request.method === 'GET') {
        return await handleListPosts(env.DB);
      }

      const slugMatch = pathname.match(/^\/api\/posts\/([^/]+)$/);
      if (slugMatch && request.method === 'GET') {
        return await handleGetPostBySlug(env.DB, slugMatch[1]);
      }

      if (pathname === '/rss.xml' && request.method === 'GET') {
        return await handleRss(env.DB, env.SITE_URL);
      }

      const postPageMatch = pathname.match(/^\/posts\/([^/]+)$/);
      if (postPageMatch && request.method === 'GET') {
        return await handlePostPage(env.DB, postPageMatch[1]);
      }

      if (pathname === '/api/prs' && request.method === 'GET') {
        return await handleListPrs(env.DB);
      }

      if (pathname === '/api/prs/refresh' && request.method === 'POST') {
        return await handleRefreshPrs(request, env.DB, env.GITHUB_TOKEN);
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
