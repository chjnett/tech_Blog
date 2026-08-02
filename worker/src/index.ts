export interface Env {
  DB: D1Database;
  SITE_URL: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    try {
      return Response.json({ error: 'not found' }, { status: 404 });
    } catch (err) {
      console.error(err);
      return Response.json({ error: 'internal error' }, { status: 500 });
    }
  },
};
