import { type Citation, type CitationMap, srcDomain } from './citations.js';
import { escapeHtml } from './text.js';

function citationCapsule(value: string, citations: CitationMap): string {
  const numbers = [...new Set((value.match(/\d{1,3}/g) || []).map(Number))];
  if (!numbers.every((number) => citations.has(number))) return value;
  const first = citations.get(numbers[0]) as Citation;
  const label = numbers.map((number) => `출처 ${number}, ${srcDomain(citations.get(number) as Citation)}`).join('; ');
  return (
    `<sup class="cite"><a href="${escapeHtml(first.url)}" target="_blank" rel="noopener noreferrer"` +
    ` data-n="${numbers.join(',')}" aria-label="${escapeHtml(label)}">${numbers.join('·')}</a></sup>`
  );
}

export function inlineMd(value: string, citations: CitationMap | null): string {
  const codes: string[] = [];
  let text = value.replace(/`([^`\n]+)`/g, (_, code: string) => `\u0000${codes.push(code) - 1}\u0000`);
  text = text
    .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(
      /!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g,
      (_, alt: string, url: string) =>
        `<a class="img-link" href="${url}" target="_blank" rel="noopener noreferrer">${alt || '이미지'}</a>`,
    )
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  if (citations) {
    text = text.replace(/(?:\[\d{1,3}(?:\s*,\s*\d{1,3})*\](?!\())+/g, (all) => citationCapsule(all, citations));
    text = text.replace(
      /([^\s<>]*)(<sup class="cite">[\s\S]*?<\/sup>)([.,!?)」]*)/g,
      (_all, word: string, capsule: string, punctuation: string) => {
        // biome-ignore lint/suspicious/noControlCharactersInRegex: NUL delimiters isolate code spans.
        const length = [...word.replace(/\u0000\d+\u0000/g, 'x').replace(/&(?:#\d+|\w+);/g, 'x')].length;
        return length > 12
          ? `${word}<span class="cite-glue">${capsule}${punctuation}</span>`
          : `<span class="cite-glue">${word}${capsule}${punctuation}</span>`;
      },
    );
  }
  // biome-ignore lint/suspicious/noControlCharactersInRegex: Restore the original NUL code placeholders.
  return text.replace(/\u0000(\d+)\u0000/g, (_, index: string) => `<code>${codes[+index]}</code>`);
}
