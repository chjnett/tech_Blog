# Phase 1 (기반: Workers + D1 + 퍼블릭 API) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Cloudflare Worker + D1 backend that serves published blog posts via `GET /api/posts`, `GET /api/posts/:slug`, and `GET /rss.xml`, and move the existing static shell into a `pages/` directory alongside it.

**Architecture:** A single Cloudflare Worker (`worker/`) reads a `posts` table in D1. `content_md` is stored raw and converted to `content_html` at request time via the `marked` library. Only `status = 'published'` rows are ever visible through the public API — everything else 404s. Pages (`pages/`) and the Worker share one custom domain: the Worker only intercepts `/api/*` and `/rss.xml` via Cloudflare Worker Routes, everything else falls through to Pages.

**Tech Stack:** Cloudflare Workers, D1, Wrangler 3, TypeScript, `marked` (markdown → HTML).

## Global Constraints

- No automated test framework this phase — verify every task via `wrangler dev` + `curl` against a local D1 instance (spec: YAGNI, CRUD-level logic).
- `draft` / `in_review` / `rejected` posts are never visible through the public API — return `404 { "error": "not found" }`, don't leak their existence.
- `content_md` is stored as-is in D1; `content_html` is computed on every request by the Worker (not at write time).
- Repo layout is a monorepo: `pages/` (static shell) + `worker/` (API), per the approved spec.
- D1 migrations this phase cover the `posts` table only — `papers` and `commit_log` are out of scope.
- The production domain isn't chosen yet. `wrangler.toml` uses the literal placeholder `<YOUR_DOMAIN>` in the `routes` and `SITE_URL` var — this must be filled in by the user before `wrangler deploy` (not before local dev, which doesn't need it).
- D1 error → `500 { "error": "internal error" }`, logged via `console.error`. Empty `/api/posts` result → `200 []`, not an error.

---

### Task 1: Worker scaffolding + D1 database

**Files:**
- Create: `worker/package.json`
- Create: `worker/tsconfig.json`
- Create: `worker/wrangler.toml`
- Create: `worker/src/index.ts`

**Interfaces:**
- Produces: `Env` interface (`{ DB: D1Database; SITE_URL: string }`) in `worker/src/index.ts`, imported by every later route module.

- [ ] **Step 1: Create `worker/package.json`**

```json
{
  "name": "tech-blog-worker",
  "version": "0.0.1",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "wrangler dev",
    "deploy": "wrangler deploy",
    "db:migrate:local": "wrangler d1 execute tech_blog_db --local --file=./migrations/0001_posts.sql",
    "db:seed:local": "wrangler d1 execute tech_blog_db --local --file=./seed.sql"
  },
  "devDependencies": {
    "@cloudflare/workers-types": "^4.20250101.0",
    "typescript": "^5.6.0",
    "wrangler": "^3.90.0"
  },
  "dependencies": {
    "marked": "^13.0.0"
  }
}
```

- [ ] **Step 2: Install dependencies**

Run (from `worker/`): `npm install`
Expected: `node_modules/` created, no errors.

- [ ] **Step 3: Create the D1 database**

Run (from `worker/`): `npx wrangler d1 create tech_blog_db`
Expected output includes a `database_id` (UUID) — copy it, it's needed in Step 4. This requires the Cloudflare account login the user already has (`npx wrangler login` first if not authenticated).

- [ ] **Step 4: Create `worker/wrangler.toml`**

```toml
name = "tech-blog-worker"
main = "src/index.ts"
compatibility_date = "2026-08-02"

[[d1_databases]]
binding = "DB"
database_name = "tech_blog_db"
database_id = "PASTE_DATABASE_ID_FROM_STEP_3_HERE"

[vars]
SITE_URL = "https://<YOUR_DOMAIN>"
```

- [ ] **Step 5: Create `worker/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2021",
    "lib": ["ES2021"],
    "module": "ES2022",
    "moduleResolution": "Bundler",
    "types": ["@cloudflare/workers-types"],
    "strict": true,
    "skipLibCheck": true,
    "noEmit": true
  },
  "include": ["src/**/*.ts"]
}
```

- [ ] **Step 6: Create `worker/src/index.ts` (stub router)**

```typescript
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
```

- [ ] **Step 7: Verify the stub runs**

Run: `npm run dev` (from `worker/`), then in another terminal: `curl -s http://localhost:8787/`
Expected: `{"error":"not found"}`

- [ ] **Step 8: Commit**

```bash
git add worker/package.json worker/tsconfig.json worker/wrangler.toml worker/src/index.ts worker/package-lock.json
git commit -m "worker: scaffold Cloudflare Worker + D1 database"
```

---

### Task 2: D1 schema (`posts`) + local seed data

**Files:**
- Create: `worker/migrations/0001_posts.sql`
- Create: `worker/seed.sql`

**Interfaces:**
- Produces: `posts` table (columns below) that `worker/src/db.ts` (Task 3) queries directly.

- [ ] **Step 1: Create `worker/migrations/0001_posts.sql`**

```sql
CREATE TABLE posts (
  id TEXT PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  content_md TEXT NOT NULL,
  excerpt TEXT,
  source_type TEXT NOT NULL,
  source_ref TEXT,
  status TEXT NOT NULL DEFAULT 'draft',
  tags TEXT,
  cover_image_key TEXT,
  created_at TEXT NOT NULL,
  published_at TEXT
);
```

- [ ] **Step 2: Apply the migration locally**

Run (from `worker/`): `npm run db:migrate:local`
Expected: command succeeds, no SQL errors.

- [ ] **Step 3: Verify the table exists**

Run: `npx wrangler d1 execute tech_blog_db --local --command "SELECT name FROM sqlite_master WHERE type='table'"`
Expected: output includes a row with `name: posts`.

- [ ] **Step 4: Create `worker/seed.sql`**

```sql
INSERT INTO posts (id, slug, title, content_md, excerpt, source_type, source_ref, status, tags, cover_image_key, created_at, published_at)
VALUES
  (
    '11111111-1111-1111-1111-111111111111',
    'hello-world',
    'Hello World',
    '# Hello

This is the **first** post.

- one
- two',
    'The first post on this blog.',
    'manual',
    NULL,
    'published',
    '["intro"]',
    NULL,
    '2026-08-01T00:00:00Z',
    '2026-08-01T00:00:00Z'
  ),
  (
    '22222222-2222-2222-2222-222222222222',
    'second-post',
    'Second Post',
    '## Section

Some [link](https://example.com) and more text.',
    'A second sample post.',
    'manual',
    NULL,
    'published',
    '["notes"]',
    NULL,
    '2026-08-02T00:00:00Z',
    '2026-08-02T00:00:00Z'
  ),
  (
    '33333333-3333-3333-3333-333333333333',
    'draft-only',
    'Draft Only',
    'Should never appear publicly.',
    'Draft excerpt.',
    'manual',
    NULL,
    'draft',
    '[]',
    NULL,
    '2026-08-02T00:00:00Z',
    NULL
  );
```

- [ ] **Step 5: Load the seed data**

Run: `npm run db:seed:local`
Expected: command succeeds, 3 rows inserted.

- [ ] **Step 6: Verify seed data**

Run: `npx wrangler d1 execute tech_blog_db --local --command "SELECT slug, status FROM posts ORDER BY slug"`
Expected: 3 rows — `draft-only`/`draft`, `hello-world`/`published`, `second-post`/`published`.

- [ ] **Step 7: Commit**

```bash
git add worker/migrations/0001_posts.sql worker/seed.sql
git commit -m "worker: add posts migration and local seed data"
```

---

### Task 3: Post read API (`GET /api/posts`, `GET /api/posts/:slug`)

**Files:**
- Create: `worker/src/types.ts`
- Create: `worker/src/db.ts`
- Create: `worker/src/render.ts`
- Create: `worker/src/routes/posts.ts`
- Modify: `worker/src/index.ts` (wire the two routes in)

**Interfaces:**
- Consumes: `Env` from `worker/src/index.ts` (Task 1).
- Produces: `PostRow` type (`worker/src/types.ts`), `listPublishedPosts(db): Promise<PostRow[]>` and `getPublishedPostBySlug(db, slug): Promise<PostRow | null>` (`worker/src/db.ts`), `renderMarkdown(md): string` (`worker/src/render.ts`) — all consumed by Task 4's `rss.ts`.

- [ ] **Step 1: Create `worker/src/types.ts`**

```typescript
export interface PostRow {
  id: string;
  slug: string;
  title: string;
  content_md: string;
  excerpt: string | null;
  source_type: string;
  source_ref: string | null;
  status: string;
  tags: string | null;
  cover_image_key: string | null;
  created_at: string;
  published_at: string | null;
}
```

- [ ] **Step 2: Create `worker/src/db.ts`**

```typescript
import type { PostRow } from './types';

export async function listPublishedPosts(db: D1Database): Promise<PostRow[]> {
  const { results } = await db
    .prepare("SELECT * FROM posts WHERE status = 'published' ORDER BY published_at DESC")
    .all<PostRow>();
  return results;
}

export async function getPublishedPostBySlug(
  db: D1Database,
  slug: string
): Promise<PostRow | null> {
  const row = await db
    .prepare("SELECT * FROM posts WHERE slug = ? AND status = 'published'")
    .bind(slug)
    .first<PostRow>();
  return row ?? null;
}
```

- [ ] **Step 3: Create `worker/src/render.ts`**

```typescript
import { marked } from 'marked';

export function renderMarkdown(md: string): string {
  return marked.parse(md) as string;
}
```

- [ ] **Step 4: Create `worker/src/routes/posts.ts`**

```typescript
import type { PostRow } from '../types';
import { listPublishedPosts, getPublishedPostBySlug } from '../db';
import { renderMarkdown } from '../render';

function parseTags(tags: string | null): string[] {
  if (!tags) return [];
  try {
    return JSON.parse(tags);
  } catch {
    return [];
  }
}

function toSummary(row: PostRow) {
  return {
    id: row.id,
    slug: row.slug,
    title: row.title,
    excerpt: row.excerpt,
    tags: parseTags(row.tags),
    cover_image_key: row.cover_image_key,
    published_at: row.published_at,
  };
}

export async function handleListPosts(db: D1Database): Promise<Response> {
  const rows = await listPublishedPosts(db);
  return Response.json(rows.map(toSummary));
}

export async function handleGetPostBySlug(db: D1Database, slug: string): Promise<Response> {
  const row = await getPublishedPostBySlug(db, slug);
  if (!row) {
    return Response.json({ error: 'not found' }, { status: 404 });
  }
  return Response.json({
    id: row.id,
    slug: row.slug,
    title: row.title,
    content_html: renderMarkdown(row.content_md),
    excerpt: row.excerpt,
    tags: parseTags(row.tags),
    cover_image_key: row.cover_image_key,
    published_at: row.published_at,
  });
}
```

- [ ] **Step 5: Wire the routes into `worker/src/index.ts`**

```typescript
import { handleListPosts, handleGetPostBySlug } from './routes/posts';

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

      return Response.json({ error: 'not found' }, { status: 404 });
    } catch (err) {
      console.error(err);
      return Response.json({ error: 'internal error' }, { status: 500 });
    }
  },
};
```

- [ ] **Step 6: Verify `GET /api/posts`**

Run: `npm run dev`, then: `curl -s http://localhost:8787/api/posts | python3 -m json.tool`
Expected: JSON array of 2 objects (only `published` rows), `second-post` before `hello-world` (DESC by `published_at`), no `content_md`/`content_html` field present.

- [ ] **Step 7: Verify `GET /api/posts/:slug` (found)**

Run: `curl -s http://localhost:8787/api/posts/hello-world | python3 -m json.tool`
Expected: 200, `content_html` contains `<h1>Hello</h1>`, `<strong>first</strong>`, and a `<ul><li>` list.

- [ ] **Step 8: Verify `GET /api/posts/:slug` (draft hidden, not found)**

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8787/api/posts/draft-only`
Expected: `404`
Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8787/api/posts/does-not-exist`
Expected: `404`

- [ ] **Step 9: Commit**

```bash
git add worker/src/types.ts worker/src/db.ts worker/src/render.ts worker/src/routes/posts.ts worker/src/index.ts
git commit -m "worker: implement GET /api/posts and GET /api/posts/:slug"
```

---

### Task 4: RSS feed (`GET /rss.xml`)

**Files:**
- Create: `worker/src/routes/rss.ts`
- Modify: `worker/src/index.ts` (add the route)

**Interfaces:**
- Consumes: `listPublishedPosts(db)` from `worker/src/db.ts` (Task 3), `Env` from `worker/src/index.ts` (Task 1).

- [ ] **Step 1: Create `worker/src/routes/rss.ts`**

```typescript
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
```

- [ ] **Step 2: Wire the route into `worker/src/index.ts`**

```typescript
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
```

- [ ] **Step 3: Verify the feed**

Run: `curl -s http://localhost:8787/rss.xml`
Expected: `Content-Type: application/rss+xml`, well-formed XML containing exactly 2 `<item>` blocks (`hello-world`, `second-post`), and no mention of `draft-only`.

- [ ] **Step 4: Commit**

```bash
git add worker/src/routes/rss.ts worker/src/index.ts
git commit -m "worker: implement GET /rss.xml"
```

---

### Task 5: Repo layout — `pages/` shell, shared design tokens, Worker Routes

**Files:**
- Move: `index.html` → `pages/index.html`
- Move: `mark.jpg` → `pages/mark.jpg`
- Create: `design-tokens.json`
- Modify: `worker/wrangler.toml` (add `[[routes]]`)

**Interfaces:** None — this task only rearranges static assets and finalizes deploy-time config; it doesn't change any Worker code from Task 1–4.

- [ ] **Step 1: Move the static shell into `pages/`**

```bash
mkdir -p pages
git mv index.html pages/index.html
git mv mark.jpg pages/mark.jpg
```

`pages/index.html` references `mark.jpg` with a relative path (`src="mark.jpg"`), so no edit is needed — both files move together.

- [ ] **Step 2: Verify the page still renders**

Run (from `pages/`): `python3 -m http.server 8935`
Then `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8935/index.html` → expect `200`, and `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8935/mark.jpg` → expect `200`.
Stop the server: `pkill -f "http.server 8935"`.

- [ ] **Step 3: Create `design-tokens.json`**

```json
{
  "color": {
    "bg": "#FFFFFF",
    "ink": "#10131A",
    "inkSoft": "#5B6270",
    "line": "#E7E9EE"
  },
  "font": {
    "mono": "'JetBrains Mono', ui-monospace, monospace",
    "sans": "'Inter', -apple-system, sans-serif"
  }
}
```

This mirrors the CSS custom properties already in `pages/index.html` (`--bg`, `--ink`, `--ink-soft`, `--line`, `--mono`, `--sans`) — no `accent` key, since the site is monochrome. Future components (review dashboard, paper cards) register new tokens here before use.

- [ ] **Step 4: Add Worker Routes to `worker/wrangler.toml`**

`worker/wrangler.toml` already has `[[d1_databases]]` (with the real `database_id` filled in during Task 1) and `[vars]` — don't touch those. Append this block to the end of the file:

```toml

[[routes]]
pattern = "<YOUR_DOMAIN>/api/*"
zone_name = "<YOUR_DOMAIN>"

[[routes]]
pattern = "<YOUR_DOMAIN>/rss.xml"
zone_name = "<YOUR_DOMAIN>"
```

`<YOUR_DOMAIN>` is a literal placeholder — replace both `pattern`/`zone_name` pairs (and the `SITE_URL` var already in `[vars]`) with the real domain once it's chosen. This blocks `wrangler deploy` but not local dev (`npm run dev` doesn't read `routes`).

- [ ] **Step 5: Commit**

```bash
git add pages/index.html pages/mark.jpg design-tokens.json worker/wrangler.toml
git commit -m "repo: move static shell into pages/, add design tokens and Worker Routes"
```
