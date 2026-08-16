import './prism-global-shim';
import Prism from 'prismjs';
import 'prismjs/components/prism-clike';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-json';
import { escapeHtml } from './utils';

const SUPPORTED_LANGUAGES = new Set(['python', 'javascript', 'typescript', 'bash', 'json']);

export function highlightCode(code: string, lang: string): { html: string; lang: string } {
  const normalized = lang.toLowerCase().trim();
  const grammar = Prism.languages[normalized];

  if (!grammar || !SUPPORTED_LANGUAGES.has(normalized)) {
    return { html: escapeHtml(code), lang: escapeHtml(normalized || 'text') };
  }

  return { html: Prism.highlight(code, grammar, normalized), lang: escapeHtml(normalized) };
}
