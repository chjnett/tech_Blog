export interface FigureGroup {
  label: string;
  note?: string;
  queryCount: number;
  kvCount: number;
}

export interface GroupsSpec {
  type: 'groups';
  caption?: string;
  groups: FigureGroup[];
}

const SQUARE = 34;
const SQUARE_GAP = 12;
const ROW_GAP = 46;
const HEADER_H = 30;
const FOOTER_H = 26;
const PAD = 18;
const GROUP_GAP = 24;

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function rowWidth(count: number): number {
  return count * SQUARE + Math.max(0, count - 1) * SQUARE_GAP;
}

function renderGroup(group: FigureGroup, offsetX: number): { svg: string; width: number; height: number } {
  const innerWidth = Math.max(rowWidth(group.queryCount), rowWidth(group.kvCount));
  const width = innerWidth + PAD * 2;
  const topRowY = PAD + HEADER_H;
  const bottomRowY = topRowY + SQUARE + ROW_GAP;
  const height = bottomRowY + SQUARE + FOOTER_H + PAD;

  const queryStartX = PAD + (innerWidth - rowWidth(group.queryCount)) / 2;
  const kvStartX = PAD + (innerWidth - rowWidth(group.kvCount)) / 2;
  const queryX = (i: number) => queryStartX + i * (SQUARE + SQUARE_GAP);
  const kvX = (j: number) => kvStartX + j * (SQUARE + SQUARE_GAP);

  const lines: string[] = [];
  for (let i = 0; i < group.queryCount; i++) {
    const owner = Math.floor((i * group.kvCount) / group.queryCount);
    const x1 = offsetX + queryX(i) + SQUARE / 2;
    const y1 = topRowY + SQUARE;
    const x2 = offsetX + kvX(owner) + SQUARE / 2;
    const y2 = bottomRowY;
    lines.push(
      `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="var(--ink)" stroke-width="1.2" opacity="0.55"/>`
    );
  }

  const querySquares = Array.from({ length: group.queryCount }, (_, i) => {
    const x = offsetX + queryX(i);
    return `<rect x="${x}" y="${topRowY}" width="${SQUARE}" height="${SQUARE}" rx="7" fill="#fff" stroke="var(--ink)" stroke-width="1.6"/>`;
  }).join('');

  const kvSquares = Array.from({ length: group.kvCount }, (_, j) => {
    const x = offsetX + kvX(j);
    return `<rect x="${x}" y="${bottomRowY}" width="${SQUARE}" height="${SQUARE}" rx="7" fill="var(--ink)" stroke="var(--ink)" stroke-width="1.6"/>`;
  }).join('');

  const container = `<rect x="${offsetX}" y="0" width="${width}" height="${height}" rx="14" fill="var(--bg-soft)" stroke="var(--line)" stroke-width="1.4"/>`;
  const labelText = `<text x="${offsetX + width / 2}" y="${PAD + 13}" text-anchor="middle" class="fig-group-label">${escapeHtml(group.label)}</text>`;
  const noteText = group.note
    ? `<text x="${offsetX + width / 2}" y="${height - PAD + 6}" text-anchor="middle" class="fig-group-note">${escapeHtml(group.note)}</text>`
    : '';

  const svg = [container, labelText, ...lines, querySquares, kvSquares, noteText].join('\n');
  return { svg, width, height };
}

export function renderGroupsFigure(spec: GroupsSpec): { svg: string; width: number; height: number } {
  let offsetX = 0;
  const parts: string[] = [];
  let maxHeight = 0;
  for (const group of spec.groups) {
    const { svg, width, height } = renderGroup(group, offsetX);
    parts.push(svg);
    offsetX += width + GROUP_GAP;
    maxHeight = Math.max(maxHeight, height);
  }
  const totalWidth = Math.max(offsetX - GROUP_GAP, 0);
  return { svg: parts.join('\n'), width: totalWidth, height: maxHeight };
}
