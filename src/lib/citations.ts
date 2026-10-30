import { escapeHtml } from './text.js';

export interface Citation {
  url: string;
  title?: string;
  domain?: string;
  favicon?: string;
  icon?: string;
  published?: string;
}
export type CitationMap = Map<number, Citation>;

export function safeUrl(value: unknown): string {
  try {
    const url = new URL(value as string);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : '';
  } catch {
    return '';
  }
}

export function citeMap(sources: unknown): CitationMap | null {
  if (!Array.isArray(sources) || !sources.length) return null;
  const citations: CitationMap = new Map();
  sources.forEach((source) => {
    const url = source && safeUrl(source.url);
    if (url && Number.isFinite(+source.n))
      citations.set(+source.n, {
        url,
        title: source.title || '',
        domain: source.domain || '',
        favicon: source.favicon || source.icon || '',
      });
  });
  return citations.size ? citations : null;
}

export function srcDomain(citation: Citation): string {
  let domain = citation.domain;
  if (!domain)
    try {
      domain = new URL(citation.url).hostname;
    } catch {
      domain = '';
    }
  return String(domain).replace(/^www\./i, '');
}

export function srcFavicon(citation: Citation): string {
  const value = citation.favicon || citation.icon;
  if (typeof value !== 'string') return '';
  if (/^data:image\/(png|x-icon|vnd\.microsoft\.icon|svg\+xml|webp|gif|jpeg);base64,/i.test(value)) return value;
  return /^\/(?!\/)[\w\-./?=&%]+$/.test(value) ? value : '';
}

export function srcDate(value: unknown, now = new Date()): string {
  if (typeof value !== 'string' || !value) return '';
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  const date = match ? new Date(+match[1], +match[2] - 1, +match[3]) : new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const day = (entry: Date) => Date.UTC(entry.getFullYear(), entry.getMonth(), entry.getDate());
  const difference = Math.round((day(now) - day(date)) / 864e5);
  if (difference === 0) return '오늘';
  if (difference === 1) return '어제';
  return date.getFullYear() === now.getFullYear()
    ? `${date.getMonth() + 1}월 ${date.getDate()}일`
    : `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일`;
}

export function srcItem(number: number, citation: Citation): string {
  const domain = srcDomain(citation),
    title = citation.title || domain || citation.url;
  const date = srcDate(citation.published),
    subtitle = date ? `${domain} · ${date}` : domain;
  const label = escapeHtml(`${number}. ${title}, ${subtitle}, 새 창에서 열림`);
  return (
    `<li class="src-item" data-n="${number}"><a href="${escapeHtml(citation.url)}"` +
    ` target="_blank" rel="noopener noreferrer" aria-label="${label}"><span class="sn">${number}</span>` +
    `<span class="st">${escapeHtml(title)}</span><span class="sd">${escapeHtml(subtitle)}</span></a></li>`
  );
}
