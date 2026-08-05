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
  <button class="code-expand" type="button" hidden>더 보기</button>
</div>`;
};

marked.use({ renderer, useNewRenderer: true });

export function renderMarkdown(md: string): string {
  const html = marked.parse(md) as string;
  return html.replace(/<table>/g, '<div class="table-wrap"><table>').replace(/<\/table>/g, '</table></div>');
}
