// 렌더러/라우트 전역에서 재사용하는 공용 헬퍼.
// 이전에는 escapeHtml/escapeXml/parseTags가 여러 파일에 각각 중복 정의되어 있었다.

const HTML_ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

/** HTML 텍스트/속성값에 쓰는 이스케이프. */
export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch]);
}

/** XML/RSS 텍스트에 쓰는 이스케이프 (아포스트로피는 &apos;). */
export function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

/** tags 컬럼(TEXT에 담긴 JSON 배열)을 string[]로 파싱. 깨진 값은 빈 배열. */
export function parseTags(tags: string | null): string[] {
  if (!tags) return [];
  try {
    const parsed = JSON.parse(tags);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}
