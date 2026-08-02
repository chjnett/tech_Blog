function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export function renderTerminalBlock(text: string): string {
  const lines = text.replace(/\n$/, '').split('\n');
  const body = lines
    .map((line) =>
      line.startsWith('$')
        ? `<span class="cmd">${escapeHtml(line)}</span>`
        : `<span class="out">${escapeHtml(line)}</span>`
    )
    .join('\n');

  return `<div class="terminal">
  <div class="terminal-bar">
    <span></span><span></span><span></span>
  </div>
  <pre>${body}</pre>
</div>`;
}
