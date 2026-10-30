import { type ComponentChildren, h, render } from 'preact';
import { renderMarkdown } from '../../lib/markdown.js';

const TAGS = new Set([
  'p',
  'br',
  'strong',
  'em',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'ul',
  'ol',
  'li',
  'div',
  'span',
  'button',
  'pre',
  'code',
  'a',
  'sup',
  'svg',
  'use',
]);
const ATTRIBUTES = new Set([
  'class',
  'target',
  'rel',
  'href',
  'data-n',
  'aria-label',
  'aria-hidden',
  'type',
  'data-lang',
  'start',
]);
function allowedLink(tag: string, value: string) {
  if (tag === 'use') return /^#i-[\w-]+$/.test(value);
  try {
    const protocol = new URL(value).protocol;
    return protocol === 'http:' || protocol === 'https:';
  } catch {
    return false;
  }
}
// Private adapter for the existing escaped Markdown renderer's output; never accepts arbitrary HTML.
function nodeView(node: Node): ComponentChildren {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent;
  if (!(node instanceof Element)) return null;
  const tag = node.localName;
  if (!TAGS.has(tag)) throw new Error('Unexpected generated Markdown element');
  const attributes: Record<string, string> = {};
  for (const attribute of node.attributes) {
    const { name, value } = attribute;
    if (!ATTRIBUTES.has(name)) throw new Error('Unexpected generated Markdown attribute');
    if (name !== 'href' || allowedLink(tag, value)) attributes[name] = value;
  }
  return h(tag, attributes, [...node.childNodes].map(nodeView));
}
function Markdown({ text, sources }: { text: string; sources?: unknown }) {
  const generated = renderMarkdown(text, sources);
  const document = new DOMParser().parseFromString(generated, 'text/html');
  return <>{[...document.body.childNodes].map(nodeView)}</>;
}
export function renderMarkdownBody(root: HTMLElement, text: string, sources?: unknown) {
  render(<Markdown text={text} sources={sources} />, root);
}
