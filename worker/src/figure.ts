import type { FigureEdge, FigureSpec, PositionedNode } from './figure-layout';
import { computeLayout, NODE_WIDTH } from './figure-layout';
import type { GroupsSpec } from './figure-groups';
import { renderGroupsFigure } from './figure-groups';
import { escapeHtml } from './utils';

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

function validateGroupsSpec(raw: unknown): GroupsSpec {
  const spec = raw as GroupsSpec;
  if (!Array.isArray(spec.groups) || spec.groups.length === 0) {
    throw new Error('groups figure requires at least one group');
  }
  for (const g of spec.groups) {
    if (typeof g.label !== 'string' || !Number.isInteger(g.queryCount) || !Number.isInteger(g.kvCount)) {
      throw new Error('each group needs a label, integer queryCount, integer kvCount');
    }
    if (g.queryCount < 1 || g.kvCount < 1) {
      throw new Error('queryCount and kvCount must each be at least 1');
    }
  }
  return spec;
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

function renderFromParsed(parsed: unknown): string {
  const margin = 20;

  if (typeof parsed === 'object' && parsed !== null && (parsed as { type?: string }).type === 'groups') {
    const spec = validateGroupsSpec(parsed);
    const { svg, width, height } = renderGroupsFigure(spec);
    const viewW = width + margin * 2;
    const viewH = height + margin * 2;
    const captionHtml = spec.caption
      ? `<div class="figure-caption">${escapeHtml(spec.caption)}</div>`
      : '';

    return `<div class="figure-block">
  <svg viewBox="0 0 ${viewW} ${viewH}" xmlns="http://www.w3.org/2000/svg">
    <g transform="translate(${margin}, ${margin})">
      ${svg}
    </g>
  </svg>
  ${captionHtml}
</div>`;
  }

  const spec = validateSpec(parsed);
  const { positioned, width, height, vertical } = computeLayout(spec);

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
}

export function renderFigure(jsonText: string): string {
  try {
    return renderFromParsed(JSON.parse(jsonText));
  } catch {
    return `<pre><code>${escapeHtml(jsonText)}</code></pre>`;
  }
}
