import type { CitationMap } from './citations.js';
import { inlineMd } from './markdown-inline.js';

export const MD_LI = /^( *)([-*+]|\d{1,9}[.)])\s+(.*)$/;
export const mdInd = (line: string): number => (line.match(/^ */) as RegExpMatchArray)[0].length;
type SameItem = (line: string) => RegExpMatchArray | null;

export function mdBlocks(lines: string[], citations: CitationMap | null): string {
  const output: string[] = [];
  let paragraph: string[] = [],
    index = 0;
  const flush = () => {
    if (paragraph.length) {
      output.push(`<p>${inlineMd(paragraph.join('<br>'), citations)}</p>`);
      paragraph = [];
    }
  };
  while (index < lines.length) {
    const line = lines[index],
      heading = line.match(/^(#{1,6})\s+(.*)/),
      item = line.match(MD_LI);
    if (!line.trim()) {
      flush();
      index++;
      continue;
    }
    if (heading) {
      flush();
      const level = Math.min(heading[1].length + 2, 6);
      output.push(`<h${level}>${inlineMd(heading[2], citations)}</h${level}>`);
      index++;
      continue;
    }
    if (item && item[1].length < 4) {
      flush();
      index = mdList(lines, index, output, citations);
      continue;
    }
    paragraph.push(line.trim() ? line.replace(/^ +/, '') : line);
    index++;
  }
  flush();
  return output.join('');
}

function itemBody(lines: string[], index: number, initial: string, base: number, indent: number, same: SameItem) {
  const body = [initial];
  let next = false;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      let end = index;
      while (end < lines.length && !lines[end].trim()) end++;
      if (end >= lines.length) {
        index = end;
        break;
      }
      if (mdInd(lines[end]) >= base + 2 && !same(lines[end])) {
        for (; index < end; index++) body.push('');
        continue;
      }
      if (same(lines[end])) {
        index = end;
        next = true;
      }
      break;
    }
    if (same(line)) {
      next = true;
      break;
    }
    const width = mdInd(line);
    if (width >= base + 2) {
      body.push(line.slice(Math.min(width, indent)));
      index++;
      continue;
    }
    if (MD_LI.test(line) || /^#{1,6}\s/.test(line) || !body[body.length - 1]) break;
    body.push(line);
    index++;
  }
  return { body, index, next };
}

function mdList(lines: string[], index: number, output: string[], citations: CitationMap | null): number {
  const first = lines[index].match(MD_LI) as RegExpMatchArray;
  const base = first[1].length,
    ordered = /\d/.test(first[2]),
    tag = ordered ? 'ol' : 'ul';
  const same: SameItem = (line) => {
    const match = line.match(MD_LI);
    return match && match[1].length <= base + 1 && /\d/.test(match[2]) === ordered ? match : null;
  };
  const items: string[] = [];
  while (index < lines.length) {
    const match = same(lines[index]);
    if (!match) break;
    const indent = match[1].length + match[2].length + 1;
    const item = itemBody(lines, index + 1, match[3], base, indent, same);
    index = item.index;
    items.push(mdBlocks(item.body, citations).replace(/^<p>([\s\S]*?)<\/p>/, '$1'));
    if (!item.next) break;
  }
  const start = ordered ? parseInt(first[2], 10) : 1;
  output.push(
    `<${tag}${ordered && start !== 1 ? ` start="${start}"` : ''}>` +
      items.map((item) => `<li>${item}</li>`).join('') +
      `</${tag}>`,
  );
  return index;
}
