import { citeMap } from './citations.js';
import { COPY_SVG } from './icons.js';
import { mdBlocks } from './markdown-blocks.js';
import { escapeHtml } from './text.js';

function codeBlock(part: string): string {
  const newline = part.indexOf('\n');
  const language = newline >= 0 ? part.slice(0, newline).trim() : '';
  const code = newline >= 0 ? part.slice(newline + 1) : part;
  return (
    '<div class="codeblock"><div class="code-head"><span class="lang">' +
    `${escapeHtml(language || 'code')}</span><button class="copy" type="button" aria-label="코드 복사">` +
    `${COPY_SVG}<span>복사</span></button></div><pre><code data-lang="${escapeHtml(language)}">` +
    `${escapeHtml(code.replace(/\n$/, ''))}</code></pre></div>`
  );
}

export function renderMarkdown(source: string, sources?: unknown): string {
  const citations = citeMap(sources);
  return source
    .split(/```/)
    .map((part, index) =>
      index % 2 === 1 ? codeBlock(part) : mdBlocks(escapeHtml(part).replace(/\t/g, '    ').split('\n'), citations),
    )
    .join('');
}
