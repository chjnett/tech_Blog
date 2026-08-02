import { marked, type Tokens } from 'marked';
import { renderTerminalBlock } from './terminal-block';

const defaultRenderer = new marked.Renderer();
const renderer = new marked.Renderer();

renderer.code = (token: Tokens.Code) => {
  const infostring = (token.lang ?? '').trim();

  if (infostring === 'terminal') {
    return renderTerminalBlock(token.text);
  }

  return defaultRenderer.code(token);
};

marked.use({ renderer, useNewRenderer: true });

export function renderMarkdown(md: string): string {
  return marked.parse(md) as string;
}
