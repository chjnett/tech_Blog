import { handleListPosts, handleGetPostBySlug } from './routes/posts';
import { handleRss } from './routes/rss';

export interface Env {
  DB: D1Database;
  SITE_URL: string;
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

      return Response.json({ error: 'not found' }, { status: 404 });
    } catch (err) {
      console.error(err);
      return Response.json({ error: 'internal error' }, { status: 500 });
    }
  },
};
