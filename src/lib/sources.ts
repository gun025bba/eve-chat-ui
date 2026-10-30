import { type Citation, citeMap, srcDomain, srcFavicon, srcItem } from './citations.js';
import { escapeHtml } from './text.js';
import { renderToolQueries } from './tool-status.js';

type Domain = { name: string; favicon: string };
interface SourceModel {
  all: [number, Citation][];
  domains: Domain[];
  shown: Domain[];
  rest: number;
  queries: string;
}

export function prepareSources(sources: unknown, tools?: unknown): SourceModel | null {
  const citations = citeMap(sources);
  if (!citations) return null;
  const queries = renderToolQueries(tools),
    all = [...citations.entries()].sort((a, b) => a[0] - b[0]);
  const domains: Domain[] = [];
  for (const [, citation] of all) {
    const name = srcDomain(citation);
    if (!domains.some((domain) => domain.name === name)) domains.push({ name, favicon: srcFavicon(citation) });
  }
  const shown = domains.slice(0, 2),
    visible = new Set(shown.map((domain) => domain.name));
  const rest = new Set(all.filter(([, citation]) => !visible.has(srcDomain(citation))).map(([, c]) => c.url)).size;
  return { all, domains, shown, rest, queries };
}

function favicon(domain: Domain): string {
  const mono = escapeHtml((domain.name[0] || '?').toUpperCase());
  return domain.favicon
    ? `<span class="fav"><img src="${escapeHtml(domain.favicon)}" alt=""` +
        ` referrerpolicy="no-referrer" loading="lazy" data-mono="${mono}"></span>`
    : `<span class="fav mono">${mono}</span>`;
}
function chip(domain: Domain, id: string): string {
  return (
    `<button type="button" class="sc" aria-expanded="false" aria-controls="${id}"` +
    ` aria-label="${escapeHtml(`출처 ${domain.name}`)}"><span class="sc-in">${favicon(domain)}` +
    `<span class="sc-n">${escapeHtml(domain.name)}</span></span></button>`
  );
}
function moreChip(rest: number, id: string): string {
  return rest
    ? `<button type="button" class="sc sc-more" aria-expanded="false" aria-controls="${id}"` +
        ` aria-label="출처 ${rest}개 더 보기"><span class="sc-in">+${rest}</span></button>`
    : '';
}

export function renderSourceHtml(model: SourceModel, id: string): string {
  const { all, domains, shown, rest, queries } = model;
  const many = all.length > 6,
    items = many ? all.slice(0, 5) : all;
  const list = (entries: [number, Citation][]) =>
    entries.map(([number, citation]) => srcItem(number, citation)).join('');
  const more = many ? `<button type="button" class="src-all">모두 보기 <span>${all.length}</span></button>` : '';
  const chips = domains.map((domain) => `<span class="src-chip">${escapeHtml(domain.name)}</span>`).join('');
  return (
    '<section class="sources" aria-label="출처"><div class="src-row">' +
    shown.map((domain) => chip(domain, id)).join('') +
    moreChip(rest, id) +
    '</div>' +
    `<div class="src-list" id="${id}" hidden>${queries}<ol role="list">${list(items)}</ol>${more}</div>` +
    `<template class="src-all-tpl">${queries}<ol role="list">${list(all)}</ol><div class="src-chips">` +
    `${chips}</div></template></section>`
  );
}
