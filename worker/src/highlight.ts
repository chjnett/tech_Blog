// 코드 하이라이팅 — Shiki (VS Code 문법 기반).
// 최적화: 'shiki' 전체(10MB+) 대신 'shiki/core' + 필요한 언어만 개별 import → ~1MB.
// Worker top-level await로 하이라이터 준비, 동기 highlightCode 사용.
// 디자인 시스템: 코드 블록 안에서만 팔레트(keyword/string/comment/function).
import { createHighlighterCore, type HighlighterCore } from 'shiki/core';
import { createJavaScriptRegexEngine } from '@shikijs/engine-javascript';
import type { ThemeInput, LanguageRegistration } from 'shiki';import bash from '@shikijs/langs/bash';
import css from '@shikijs/langs/css';
import dockerfile from '@shikijs/langs/dockerfile';
import go from '@shikijs/langs/go';
import html from '@shikijs/langs/html';
import javascript from '@shikijs/langs/javascript';
import json from '@shikijs/langs/json';
import markdown from '@shikijs/langs/markdown';
import python from '@shikijs/langs/python';
import sql from '@shikijs/langs/sql';
import typescript from '@shikijs/langs/typescript';
import { escapeHtml } from './utils';

// 블로그 코드 팔레트 (blog.css .code-block 토큰과 동일)
// keyword #E2A33D, string #6FBF8B, comment #7A8290(italic), function #F6F7F9
const BLOG_THEME: ThemeInput = {
  name: 'chjnett-blog',
  type: 'dark',
  bg: '#10131A',
  fg: '#F6F7F9',
  tokenColors: [
    { scope: ['keyword', 'keyword.control', 'storage', 'keyword.operator.expression'], settings: { foreground: '#E2A33D' } },
    { scope: ['string', 'string.quoted', 'string.template', 'constant'], settings: { foreground: '#6FBF8B' } },
    { scope: ['comment'], settings: { foreground: '#7A8290', fontStyle: 'italic' } },
    { scope: ['entity.name.function', 'support.function', 'function'], settings: { foreground: '#F6F7F9' } },
    { scope: ['punctuation', 'operator', 'number'], settings: { foreground: '#F6F7F9' } },
  ],
};

export const SUPPORTED_LANGUAGES = [
  'python', 'javascript', 'typescript', 'json', 'bash',
  'css', 'markdown', 'html', 'dockerfile', 'go', 'sql',
] as const;

type Lang = (typeof SUPPORTED_LANGUAGES)[number];

// 지원 언어별 실제 문법 모듈 매핑
// 각 언어 모듈은 해당 언어 문법(들)을 LanguageRegistration[]로 export한다.
const LANG_LOADERS: Record<Lang, LanguageRegistration[]> = {
  python, javascript, typescript, json, bash,
  css, markdown, html, dockerfile, go, sql,
};

// 언어 배열을 평면화해 하이라이터에 등록
const ALL_LANGS: LanguageRegistration[] = Object.values(LANG_LOADERS).flat();

// top-level await: 모듈 초기화 시 하이라이터 1회 생성 (Worker 요청 간 재사용).
const highlighter: HighlighterCore = await createHighlighterCore({
  themes: [BLOG_THEME],
  langs: ALL_LANGS,
  engine: createJavaScriptRegexEngine(),
});

export function highlightCode(code: string, lang: string): { html: string; lang: string } {
  const normalized = (lang || '').toLowerCase().trim() || 'text';

  if (!(SUPPORTED_LANGUAGES as readonly string[]).includes(normalized)) {
    return { html: escapeHtml(code), lang: escapeHtml(normalized) };
  }

  try {
    // Shiki는 완전한 <pre class="shiki"><code>…</code></pre>를 준다.
    // render.ts가 자체 <pre><code>를 감싸므로, <code> 내부(행+토큰)만 추출한다.
    const full = highlighter.codeToHtml(code, { lang: normalized as Lang, theme: 'chjnett-blog' });
    const m = full.match(/<code[^>]*>([\s\S]*)<\/code>/);
    const html = m ? m[1] : full;
    return { html, lang: escapeHtml(normalized) };
  } catch (err) {
    // 배포 진단용: 라이브에서 실제 폴백 사유를 로그로 남긴다.
    console.error('[highlight] Shiki fail:', normalized, (err as Error)?.message ?? String(err));
    return { html: escapeHtml(code), lang: escapeHtml(normalized) };
  }
}
