import { marked, type Tokens } from 'marked';
import { highlightCode } from './highlight';
import { renderTerminalBlock } from './terminal-block';
import { renderFigure } from './figure';

function escapeAttr(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

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
  <button class="code-expand" type="button" hidden>더 보기</button>
</div>`;
};

// markdown 이미지 → figure-block 구조로 변환 (alt 텍스트를 캡션으로 사용)
renderer.image = (token: Tokens.Image) => {
  const src  = escapeAttr(token.href ?? '');
  const alt  = escapeAttr(token.text ?? '');
  const caption = alt ? `<p class="figure-caption">${alt}</p>` : '';
  return `<div class="figure-block">
  <img class="fig-image" src="${src}" alt="${alt}" loading="lazy">
  ${caption}
</div>`;
};

marked.use({ renderer, useNewRenderer: true });

export function renderMarkdown(md: string): string {
  const html = marked.parse(md) as string;
  return html.replace(/<table>/g, '<div class="table-wrap"><table>').replace(/<\/table>/g, '</table></div>');
}
