import sanitizeHtml from 'sanitize-html';

// content_md는 지금까지 신뢰된 수동 콘텐츠뿐이라 marked가 원본 HTML을 그대로
// 통과시켜도 문제가 없었다. 하지만 Phase 3(논문 자동 초안)·4(깃허브 커밋 초안)부터는
// 기계 생성 콘텐츠가 posts에 들어오므로, 렌더 결과를 allowlist 기반으로 sanitize한다.
//
// 허용 범위 = 이 블로그 디자인 시스템이 실제로 만들어내는 HTML:
//   - 마크다운 표준 태그 + 취소선(<del>)
//   - code/terminal/figure 블록이 만드는 div/span/pre/button
//   - figure SVG(svg/g/rect/line/polygon/text/tspan)
//   - 콘텐츠에서 직접 쓰는 툴팁 <span class="tooltip" data-tooltip="...">
// 그 외(script/iframe/on*/javascript: 등)는 제거된다.

const EXTRA_TAGS = ['del', 'img', 'button', 'svg', 'g', 'rect', 'line', 'polygon', 'text', 'tspan'];

export function sanitizeRenderedHtml(html: string): string {
  const sanitized = sanitizeHtml(html, {
    allowedTags: sanitizeHtml.defaults.allowedTags.concat(EXTRA_TAGS),
    allowedAttributes: {
      ...sanitizeHtml.defaults.allowedAttributes,
      // 모든 태그에 공통으로 허용되는 속성 (class는 렌더러가 광범위하게 사용)
      '*': ['class', 'title', 'aria-label', 'aria-hidden', 'aria-pressed', 'role', 'tabindex', 'hidden'],
      a: ['href', 'name', 'target', 'rel'],
      img: ['src', 'srcset', 'alt', 'width', 'height', 'loading'],
      span: ['data-tooltip'],
      button: ['type'],
      th: ['align'],
      td: ['align'],
      // figure 블록 SVG. sanitize-html(htmlparser2)은 속성명을 소문자화하므로
      // camelCase인 viewBox는 'viewbox'로 매칭해야 살아남는다 (아래에서 복원).
      svg: ['viewbox', 'xmlns', 'width', 'height', 'preserveAspectRatio'],
      g: ['transform'],
      rect: ['x', 'y', 'width', 'height', 'rx', 'ry', 'fill', 'stroke', 'stroke-width', 'opacity'],
      line: ['x1', 'y1', 'x2', 'y2', 'stroke', 'stroke-width', 'opacity'],
      polygon: ['points', 'fill', 'stroke', 'stroke-width'],
      text: ['x', 'y', 'text-anchor', 'fill'],
      tspan: ['x', 'dy'],
    },
    allowedSchemes: ['http', 'https', 'mailto'],
    allowProtocolRelative: true,
  });

  // SVG는 속성명이 대소문자 구분이라, 소문자로 살아남은 viewbox를 viewBox로 복원.
  // figure 렌더러가 만들어내는 유일한 camelCase 속성이므로 전역 치환해도 안전하다.
  return sanitized.replace(/viewbox=/g, 'viewBox=');
}
