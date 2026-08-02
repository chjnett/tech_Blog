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
