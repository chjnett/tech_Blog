# Figure Block Renderer + Post Detail Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render `figure` content blocks (JSON → auto-laid-out SVG diagram) and serve a real, styled `GET /posts/:slug` article page — the two previously-deferred TODO items, now spec'd together since the page needs the renderer's output classes.

**Architecture:** `worker/src/figure.ts` (+ `figure-layout.ts` for the pure position math) parses a `figure` fenced-code JSON block, computes node positions with a layered/topological algorithm for `flow` and simple index-based placement for `compare`/`stack`, and emits an SVG string — never throwing, falling back to an escaped code block on any parse/validation error. `render.ts` gains one more branch alongside the existing `terminal`/default-code ones. A new Worker route, `GET /posts/:slug`, reuses the same `getPublishedPostBySlug` + `renderMarkdown` Task 3 already built, wraps the result in an article shell, and links a new shared stylesheet (`pages/blog.css`) that both this page and (unchanged) `pages/index.html`'s design tokens are visually consistent with.

**Tech Stack:** Same as Phase 1 — Cloudflare Workers, D1, TypeScript, `marked` + `prismjs` (unchanged). No new dependencies.

## Global Constraints

- `renderFigure` must never throw. Any JSON parse error, invalid `type`, empty `nodes`, or an edge referencing an unknown node id falls back to an escaped `<pre><code>` block of the raw text — the publish pipeline must never 500 because of one malformed figure block.
- Only monochrome + black/white inversion in figure diagrams (`emphasis: true` → ink fill + white text, otherwise white fill + ink border) — no new colors. The project's only color anywhere is inside `.code-block` Prism syntax highlighting (unchanged, untouched by this plan).
- `GET /posts/:slug` obeys the exact same visibility rule as the JSON API: non-`published` or nonexistent slug → 404, no existence leak.
- `pages/index.html`'s inline `<style>` is not touched — `pages/blog.css` is a new, separate file for article/content-component styling only.
- No automated test framework this phase either — verify every task via `wrangler dev` + `curl` against local D1, same as Phase 1.
- `worker/wrangler.toml` already has `[dev] host = "localhost"` (added after Phase 1 Task 7 broke local dev by adding `<YOUR_DOMAIN>`-placeholder routes) — adding one more `[[routes]]` entry in this plan does not require touching that block, and should not break `wrangler dev` again.

---

### Task 1: Figure block renderer

**Files:**
- Create: `worker/src/figure-layout.ts`
- Create: `worker/src/figure.ts`
- Modify: `worker/src/render.ts` (add the `figure` branch)
- Modify: `worker/seed.sql` (two new demo posts: one valid figure, one intentionally broken)

**Interfaces:**
- Consumes: nothing from earlier tasks — this is new, self-contained rendering logic.
- Produces: `renderFigure(jsonText: string): string` (`worker/src/figure.ts`), called from `render.ts`. `FigureSpec`/`FigureNode`/`FigureEdge` types (`worker/src/figure-layout.ts`) are internal to this feature — no other task consumes them.

- [ ] **Step 1: Create `worker/src/figure-layout.ts`**

```typescript
export interface FigureNode {
  id: string;
  label: string;
  note?: string;
  emphasis?: boolean;
}

export interface FigureEdge {
  from: string;
  to: string;
  label?: string;
}

export interface FigureSpec {
  type: 'flow' | 'compare' | 'stack';
  caption?: string;
  nodes: FigureNode[];
  edges?: FigureEdge[];
}

export interface PositionedNode extends FigureNode {
  x: number;
  y: number;
  labelLines: string[];
  noteLines: string[];
  height: number;
}

export interface FigureLayout {
  positioned: Map<string, PositionedNode>;
  width: number;
  height: number;
  vertical: boolean;
}

const COL_WIDTH = 180;
const ROW_HEIGHT = 90;
export const NODE_WIDTH = 140;
const NODE_BASE_HEIGHT = 52;
const LINE_HEIGHT = 16;
const LABEL_WRAP = 14;
const NOTE_WRAP = 20;

export function wrapText(text: string, maxChars: number): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = '';
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length > maxChars && current) {
      lines.push(current);
      current = word;
    } else {
      current = candidate;
    }
  }
  if (current) lines.push(current);
  return lines.length ? lines : [''];
}

function computeColumns(spec: FigureSpec): Map<string, number> {
  const column = new Map<string, number>();
  spec.nodes.forEach((n) => column.set(n.id, 0));

  if (spec.type === 'compare') {
    spec.nodes.forEach((n, i) => column.set(n.id, i));
    return column;
  }

  if (spec.type === 'stack') {
    return column;
  }

  // flow: longest-path-from-source layering (Kahn's algorithm variant)
  const edges = spec.edges ?? [];
  const incoming = new Map<string, number>();
  spec.nodes.forEach((n) => incoming.set(n.id, 0));
  edges.forEach((e) => incoming.set(e.to, (incoming.get(e.to) ?? 0) + 1));

  const adjacency = new Map<string, string[]>();
  edges.forEach((e) => {
    if (!adjacency.has(e.from)) adjacency.set(e.from, []);
    adjacency.get(e.from)!.push(e.to);
  });

  const remaining = new Map(incoming);
  const queue = spec.nodes.filter((n) => (incoming.get(n.id) ?? 0) === 0).map((n) => n.id);

  while (queue.length) {
    const id = queue.shift()!;
    for (const next of adjacency.get(id) ?? []) {
      column.set(next, Math.max(column.get(next) ?? 0, (column.get(id) ?? 0) + 1));
      remaining.set(next, (remaining.get(next) ?? 0) - 1);
      if (remaining.get(next) === 0) queue.push(next);
    }
  }

  return column;
}

export function computeLayout(spec: FigureSpec): FigureLayout {
  const columnOf = computeColumns(spec);
  const byColumn = new Map<number, FigureNode[]>();
  for (const node of spec.nodes) {
    const c = columnOf.get(node.id) ?? 0;
    if (!byColumn.has(c)) byColumn.set(c, []);
    byColumn.get(c)!.push(node);
  }

  const vertical = spec.type === 'stack';
  const counts = Array.from(byColumn.values()).map((arr) => arr.length);
  const maxCount = Math.max(...counts, 1);
  const totalSecondary = maxCount * ROW_HEIGHT;

  const positioned = new Map<string, PositionedNode>();
  for (const [col, nodes] of byColumn) {
    const startSecondary = (totalSecondary - nodes.length * ROW_HEIGHT) / 2;
    nodes.forEach((node, i) => {
      const secondary = startSecondary + i * ROW_HEIGHT + ROW_HEIGHT / 2;
      const primary = col * COL_WIDTH + COL_WIDTH / 2;
      const labelLines = wrapText(node.label, LABEL_WRAP);
      const noteLines = node.note ? wrapText(node.note, NOTE_WRAP) : [];
      const height = Math.max(
        NODE_BASE_HEIGHT,
        (labelLines.length + noteLines.length) * LINE_HEIGHT + 20
      );
      positioned.set(node.id, {
        ...node,
        x: vertical ? COL_WIDTH / 2 : primary,
        y: secondary,
        labelLines,
        noteLines,
        height,
      });
    });
  }

  const columnCount = Math.max(...Array.from(byColumn.keys()), 0) + 1;
  const width = vertical ? COL_WIDTH : columnCount * COL_WIDTH;
  const height = totalSecondary;

  return { positioned, width, height, vertical };
}
```

- [ ] **Step 2: Create `worker/src/figure.ts`**

```typescript
import type { FigureEdge, FigureSpec, PositionedNode } from './figure-layout';
import { computeLayout, NODE_WIDTH } from './figure-layout';

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function tspans(lines: string[], x: number): string {
  return lines
    .map((line, i) => `<tspan x="${x}" dy="${i === 0 ? 0 : 16}">${escapeHtml(line)}</tspan>`)
    .join('');
}

function renderNode(node: PositionedNode): string {
  const rectX = node.x - NODE_WIDTH / 2;
  const rectY = node.y - node.height / 2;
  const fill = node.emphasis ? 'var(--ink)' : '#fff';
  const labelClass = node.emphasis ? 'fig-node-label on-accent' : 'fig-node-label';
  const noteFillAttr = node.emphasis ? ' fill="rgba(255,255,255,0.75)"' : '';

  const labelY = rectY + 20;
  const noteY = labelY + node.labelLines.length * 16 + 2;

  const noteText = node.noteLines.length
    ? `<text x="${node.x}" y="${noteY}" text-anchor="middle" class="fig-node-note"${noteFillAttr}>${tspans(
        node.noteLines,
        node.x
      )}</text>`
    : '';

  return `<rect x="${rectX}" y="${rectY}" width="${NODE_WIDTH}" height="${node.height}" rx="6" fill="${fill}" stroke="var(--ink)" stroke-width="1.6"/>
<text x="${node.x}" y="${labelY}" text-anchor="middle" class="${labelClass}">${tspans(node.labelLines, node.x)}</text>
${noteText}`;
}

function edgeEndpoints(from: PositionedNode, to: PositionedNode, vertical: boolean) {
  if (vertical) {
    return { x1: from.x, y1: from.y + from.height / 2, x2: to.x, y2: to.y - to.height / 2 };
  }
  return { x1: from.x + NODE_WIDTH / 2, y1: from.y, x2: to.x - NODE_WIDTH / 2, y2: to.y };
}

function renderEdge(from: PositionedNode, to: PositionedNode, edge: FigureEdge, vertical: boolean): string {
  const { x1, y1, x2, y2 } = edgeEndpoints(from, to, vertical);
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const headLen = 9;
  const p1x = x2 - headLen * Math.cos(angle - Math.PI / 6);
  const p1y = y2 - headLen * Math.sin(angle - Math.PI / 6);
  const p2x = x2 - headLen * Math.cos(angle + Math.PI / 6);
  const p2y = y2 - headLen * Math.sin(angle + Math.PI / 6);

  const label = edge.label
    ? `<text x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 - 6}" text-anchor="middle" class="fig-edge-label">${escapeHtml(
        edge.label
      )}</text>`
    : '';

  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="var(--ink)" stroke-width="1.4"/>
<polygon points="${x2},${y2} ${p1x},${p1y} ${p2x},${p2y}" fill="var(--ink)"/>
${label}`;
}

function validateSpec(raw: unknown): FigureSpec {
  if (typeof raw !== 'object' || raw === null) {
    throw new Error('figure spec must be an object');
  }
  const spec = raw as FigureSpec;
  if (spec.type !== 'flow' && spec.type !== 'compare' && spec.type !== 'stack') {
    throw new Error('figure type must be flow, compare, or stack');
  }
  if (!Array.isArray(spec.nodes) || spec.nodes.length === 0) {
    throw new Error('figure requires at least one node');
  }
  const ids = new Set(spec.nodes.map((n) => n.id));
  for (const edge of spec.edges ?? []) {
    if (!ids.has(edge.from) || !ids.has(edge.to)) {
      throw new Error(`edge references unknown node id: ${edge.from} -> ${edge.to}`);
    }
  }
  return spec;
}

export function renderFigure(jsonText: string): string {
  try {
    const spec = validateSpec(JSON.parse(jsonText));
    const { positioned, width, height, vertical } = computeLayout(spec);
    const margin = 20;

    const nodesSvg = spec.nodes.map((n) => renderNode(positioned.get(n.id)!)).join('\n');
    const edgesSvg = (spec.edges ?? [])
      .map((e) => renderEdge(positioned.get(e.from)!, positioned.get(e.to)!, e, vertical))
      .join('\n');

    const viewW = width + margin * 2;
    const viewH = height + margin * 2;
    const captionHtml = spec.caption
      ? `<div class="figure-caption">${escapeHtml(spec.caption)}</div>`
      : '';

    return `<div class="figure-block">
  <svg viewBox="0 0 ${viewW} ${viewH}" xmlns="http://www.w3.org/2000/svg">
    <g transform="translate(${margin}, ${margin})">
      ${nodesSvg}
      ${edgesSvg}
    </g>
  </svg>
  ${captionHtml}
</div>`;
  } catch {
    return `<pre><code>${escapeHtml(jsonText)}</code></pre>`;
  }
}
```

- [ ] **Step 3: Modify `worker/src/render.ts` to add the `figure` branch**

```typescript
import { marked, type Tokens } from 'marked';
import { highlightCode } from './highlight';
import { renderTerminalBlock } from './terminal-block';
import { renderFigure } from './figure';

const renderer = new marked.Renderer();

renderer.code = (token: Tokens.Code) => {
  const infostring = (token.lang ?? '').trim();

  if (infostring === 'terminal') {
    return renderTerminalBlock(token.text);
  }

  if (infostring === 'figure') {
    return renderFigure(token.text);
  }

  const language = infostring.split(/\s+/)[0] || 'text';
  const { html, lang } = highlightCode(token.text, language);

  return `<div class="code-block">
  <div class="code-bar">
    <span class="code-lang">${lang}</span>
    <button class="copy-btn">copy</button>
  </div>
  <pre><code>${html}</code></pre>
</div>`;
};

marked.use({ renderer, useNewRenderer: true });

export function renderMarkdown(md: string): string {
  return marked.parse(md) as string;
}
```

- [ ] **Step 4: Add two demo posts to `worker/seed.sql`**

Append to the file (as two more tuples on the existing `INSERT ... VALUES` statement, or as a new `INSERT` statement — either is fine, just keep it valid SQL):

```sql
INSERT INTO posts (id, slug, title, content_md, excerpt, source_type, source_ref, status, tags, cover_image_key, created_at, published_at)
VALUES
  (
    '55555555-5555-5555-5555-555555555555',
    'figure-demo',
    'Figure Block Demo',
    '# Figure Block Demo

Testing the figure auto-layout renderer.

```figure
{"type":"flow","caption":"A와 B가 합쳐져 C가 되는 예시 — fan-in 레이아웃 테스트","nodes":[{"id":"a","label":"Input A","note":"첫 번째 입력 벡터"},{"id":"b","label":"Input B","note":"두 번째 입력 벡터"},{"id":"c","label":"Combined Output","emphasis":true}],"edges":[{"from":"a","to":"c","label":"merge"},{"from":"b","to":"c"}]}
```',
    'Demo post exercising the figure block renderer.',
    'manual',
    NULL,
    'published',
    '["demo"]',
    NULL,
    '2026-08-02T14:00:00Z',
    '2026-08-02T14:00:00Z'
  ),
  (
    '66666666-6666-6666-6666-666666666666',
    'figure-broken',
    'Figure Broken Demo',
    '# Figure Broken Demo

This figure JSON is intentionally invalid to test the fallback path.

```figure
{not valid json
```',
    'Demo post exercising the figure fallback path.',
    'manual',
    NULL,
    'published',
    '["demo"]',
    NULL,
    '2026-08-02T14:01:00Z',
    '2026-08-02T14:01:00Z'
  );
```

- [ ] **Step 5: Reload the seed data**

Run (from `worker/`): `npx wrangler d1 execute tech_blog_db --local --file=./seed.sql`
Expected: succeeds, 2 more rows inserted (6 total in `posts`, don't worry about re-verifying the original 4 — Phase 1 already covers those).

- [ ] **Step 6: Verify the valid figure renders**

Run: `npm run dev`, then: `curl -s http://localhost:8787/api/posts/figure-demo | python3 -m json.tool`
Expected: `content_html` contains `<div class="figure-block">`, `<svg`, exactly 3 `<rect` elements (one per node), the string `fig-node-label on-accent` (the emphasis node), and the string `merge` (the edge label).

- [ ] **Step 7: Verify the broken figure falls back gracefully**

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8787/api/posts/figure-broken`
Expected: `200` (not 500 — the parse failure must be caught internally).
Run: `curl -s http://localhost:8787/api/posts/figure-broken | python3 -m json.tool`
Expected: `content_html` contains `<pre><code>{not valid json` and does NOT contain `<div class="figure-block">`.

- [ ] **Step 8: Commit**

```bash
git add worker/src/figure-layout.ts worker/src/figure.ts worker/src/render.ts worker/seed.sql
git commit -m "worker: render figure blocks with auto-layout SVG"
```

---

### Task 2: Shared stylesheet (`pages/blog.css`)

**Files:**
- Create: `pages/blog.css`

**Interfaces:** None consumed. Produces the CSS class contract (`.article-header`, `.article-body`, `.code-block` + `.token.*`, `.terminal`, `.figure-block` + `.fig-*`, `.post-header .logo`) that Task 3's HTML template targets by class name.

- [ ] **Step 1: Create `pages/blog.css`**

```css
:root {
  --bg: #FFFFFF;
  --bg-soft: #F6F7F9;
  --ink: #10131A;
  --ink-soft: #5B6270;
  --line: #E7E9EE;
  --mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
  --sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
*{box-sizing:border-box; margin:0; padding:0;}
body{
  background:var(--bg);
  color:var(--ink);
  font-family:var(--sans);
}
a{color:var(--ink);}

/* ---------- POST HEADER (home link) ---------- */
.post-header{
  max-width:680px;
  margin:0 auto;
  padding:24px;
}
.post-header .logo{
  display:block;
  width:36px;
  height:36px;
  border-radius:50%;
  object-fit:cover;
  border:1px solid var(--line);
}

/* ---------- ARTICLE SHELL ---------- */
.article-header{
  max-width:680px;
  margin:0 auto;
  padding:32px 24px 32px;
  border-bottom:1px solid var(--line);
}
.article-meta{
  font-family:var(--mono);
  font-size:12.5px;
  color:var(--ink);
  display:flex;
  gap:10px;
  align-items:center;
  margin-bottom:16px;
}
.article-meta .tag{
  background:var(--bg-soft);
  border:1px solid var(--line);
  color:var(--ink-soft);
  padding:3px 8px;
  border-radius:4px;
}
.article-header h1{
  font-family:var(--mono);
  font-size:clamp(24px, 4vw, 32px);
  font-weight:700;
  letter-spacing:-0.01em;
  line-height:1.3;
}
.article-body{
  max-width:680px;
  margin:0 auto;
  padding:40px 24px 100px;
  font-size:17px;
  line-height:1.75;
}
.article-body p{margin-bottom:22px;}
.article-body h2{
  font-family:var(--mono);
  font-size:19px;
  margin:44px 0 18px;
  padding-top:4px;
}
.article-body ul, .article-body ol{margin:0 0 22px 24px;}
.article-body strong{color:var(--ink); font-weight:600;}

/* ---------- CODE BLOCK ---------- */
.code-block{
  background:var(--ink);
  border-radius:8px;
  margin:32px auto;
  max-width:640px;
  overflow:hidden;
}
.code-block .code-bar{
  display:flex;
  justify-content:space-between;
  align-items:center;
  padding:8px 16px;
  border-bottom:1px solid rgba(255,255,255,0.08);
}
.code-block .code-lang{
  font-family:var(--mono);
  font-size:11px;
  color:rgba(246,247,249,0.5);
  letter-spacing:0.02em;
}
.code-block .copy-btn{
  font-family:var(--mono);
  font-size:11px;
  color:rgba(246,247,249,0.5);
  background:none;
  border:none;
  cursor:pointer;
}
.code-block .copy-btn:hover{color:#fff;}
.code-block pre{
  padding:18px 20px;
  overflow-x:auto;
  font-family:var(--mono);
  font-size:13.5px;
  line-height:1.7;
  color:#F6F7F9;
}
.code-block .token.keyword{color:#E2A33D; font-weight:600;}
.code-block .token.string{color:#6FBF8B;}
.code-block .token.comment{color:#7A8290; font-style:italic;}
.code-block .token.function{color:#F6F7F9; font-weight:700;}

/* ---------- TERMINAL BLOCK ---------- */
.terminal{
  background:var(--bg-soft);
  border:1px solid var(--line);
  border-radius:8px;
  margin:32px auto;
  max-width:640px;
  overflow:hidden;
}
.terminal-bar{
  display:flex; align-items:center; gap:6px;
  padding:10px 14px;
  border-bottom:1px solid var(--line);
}
.terminal-bar span{width:9px; height:9px; border-radius:50%; background:var(--line);}
.terminal pre{
  padding:16px 18px;
  font-family:var(--mono);
  font-size:13px;
  line-height:1.8;
}
.terminal .cmd{color:var(--ink); font-weight:700;}
.terminal .out{color:var(--ink-soft);}

/* ---------- FIGURE BLOCK ---------- */
.figure-block{
  margin:40px auto;
  max-width:640px;
  border:1px solid var(--line);
  border-radius:10px;
  padding:28px 20px 18px;
  background:#fff;
}
.figure-block svg{width:100%; height:auto; display:block;}
.figure-caption{
  font-family:var(--mono);
  font-size:12.5px;
  color:var(--ink-soft);
  text-align:center;
  margin-top:16px;
  line-height:1.6;
  padding:0 12px;
}
.fig-node-label{font-family:var(--mono); font-size:12px; font-weight:700; fill:var(--ink);}
.fig-node-label.on-accent{fill:#fff;}
.fig-node-note{font-family:var(--mono); font-size:9.5px; fill:var(--ink-soft);}
.fig-edge-label{font-family:var(--mono); font-size:9.5px; fill:var(--ink);}

@media (max-width:640px){
  .article-body{font-size:16px;}
  .code-block, .terminal, .figure-block{border-radius:6px; margin-left:0; margin-right:0;}
}
```

Note the class names here match what Phase 1 Task 6 (`worker/src/highlight.ts` via Prism) and this plan's Task 1 (`worker/src/figure.ts`) actually emit — `.token.keyword`/`.token.string`/`.token.comment`/`.token.function` (Prism's real classes, not `exBlog.html`'s hand-made `.kw`/`.str`/`.cm`/`.fn`), and `.fig-node-label`/`.fig-node-note`/`.fig-edge-label`/`.on-accent` (from `figure.ts`). No `--accent` custom property — per `docs/HANDOFF.md` §1.1 it's just an alias for `var(--ink)`, so every place `exBlog.html` used `var(--accent)` is written here as `var(--ink)` directly.

- [ ] **Step 2: Verify it's a valid, servable static file**

Run (from `pages/`): `python3 -m http.server 8935`, then: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8935/blog.css`
Expected: `200`.
Stop the server: `pkill -f "http.server 8935"`.

- [ ] **Step 3: Commit**

```bash
git add pages/blog.css
git commit -m "pages: add shared article/code/terminal/figure stylesheet"
```

---

### Task 3: Post detail page (`GET /posts/:slug`, Worker SSR)

**Files:**
- Create: `worker/src/routes/post-page.ts`
- Modify: `worker/src/index.ts` (add the route)

**Interfaces:**
- Consumes: `getPublishedPostBySlug(db, slug)` from `worker/src/db.ts` (Phase 1 Task 3), `renderMarkdown(md)` from `worker/src/render.ts` (this plan's Task 1 extends it, signature unchanged), `Env` from `worker/src/index.ts` (Phase 1 Task 1).

- [ ] **Step 1: Create `worker/src/routes/post-page.ts`**

```typescript
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

</body>
</html>`;

  return new Response(html, {
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  });
}
```

`GET /posts/:slug` returning a plain-text 404 (not JSON, not a styled HTML error page) is a deliberate scope decision — this route's success path is the only thing this plan builds a template for; a designed 404 page isn't part of the approved spec. D1 errors on this route fall through to `index.ts`'s existing global try/catch (Phase 1 Task 1) and return the same JSON 500 body the API uses — also deliberate, not a gap, since a separate HTML error page for this one route is out of scope.

- [ ] **Step 2: Wire the route into `worker/src/index.ts`**

```typescript
import { handleListPosts, handleGetPostBySlug } from './routes/posts';
import { handleRss } from './routes/rss';
import { handlePostPage } from './routes/post-page';

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

      const postPageMatch = pathname.match(/^\/posts\/([^/]+)$/);
      if (postPageMatch && request.method === 'GET') {
        return await handlePostPage(env.DB, postPageMatch[1]);
      }

      return Response.json({ error: 'not found' }, { status: 404 });
    } catch (err) {
      console.error(err);
      return Response.json({ error: 'internal error' }, { status: 500 });
    }
  },
};
```

- [ ] **Step 3: Verify the page renders**

Run: `npm run dev`, then: `curl -s http://localhost:8787/posts/figure-demo`
Expected: full HTML document, `<title>Figure Block Demo — chjnett.dev</title>`, `<link rel="stylesheet" href="/blog.css">`, `<img class="logo" src="/mark.jpg"`, `<div class="figure-block">` (the rendered figure from Task 1) somewhere in the body.

- [ ] **Step 4: Verify draft/nonexistent slugs still 404 on this route**

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8787/posts/draft-only`
Expected: `404`
Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8787/posts/does-not-exist`
Expected: `404`

- [ ] **Step 5: Commit**

```bash
git add worker/src/routes/post-page.ts worker/src/index.ts
git commit -m "worker: serve GET /posts/:slug as a server-rendered article page"
```

---

### Task 4: Worker Route for `/posts/*`

**Files:**
- Modify: `worker/wrangler.toml` (append one more `[[routes]]` block)

**Interfaces:** None — config only.

- [ ] **Step 1: Append the route**

`worker/wrangler.toml` already has two `[[routes]]` blocks (`/api/*`, `/rss.xml`) and a `[dev]` block from Phase 1. Append this after the existing `[[routes]]` blocks, before `[dev]`:

```toml

[[routes]]
pattern = "<YOUR_DOMAIN>/posts/*"
zone_name = "<YOUR_DOMAIN>"
```

`<YOUR_DOMAIN>` stays the literal placeholder, same as the other two route blocks — don't fill in a guessed domain.

- [ ] **Step 2: Verify `wrangler dev` still starts cleanly**

Run: `npm run dev`
Expected: starts without the `Cannot infer host from first route` error Phase 1 Task 7 hit — the existing `[dev] host = "localhost"` block already covers this, but confirm it still does after adding a third route pattern.
Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8787/posts/hello-world`
Expected: `200`

- [ ] **Step 3: Commit**

```bash
git add worker/wrangler.toml
git commit -m "worker: add /posts/* to Worker Routes"
```
