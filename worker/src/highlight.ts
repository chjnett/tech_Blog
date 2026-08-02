import Prism from 'prismjs';
import 'prismjs/components/prism-clike';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-json';

const SUPPORTED_LANGUAGES = new Set(['python', 'javascript', 'typescript', 'bash', 'json']);

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export function highlightCode(code: string, lang: string): { html: string; lang: string } {
  const normalized = lang.toLowerCase().trim();
  const grammar = Prism.languages[normalized];

  if (!grammar || !SUPPORTED_LANGUAGES.has(normalized)) {
    return { html: escapeHtml(code), lang: normalized || 'text' };
  }

  return { html: Prism.highlight(code, grammar, normalized), lang: normalized };
}
