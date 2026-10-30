import { Component, type ComponentChildren, h, render } from 'preact';
import { renderMarkdown } from '../../lib/markdown.js';
import { stableCut } from '../../lib/markdown-stream.js';

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
type GeneratedProps = { html: string };
class MarkdownPart extends Component<GeneratedProps> {
  shouldComponentUpdate(next: GeneratedProps) {
    return next.html !== this.props.html;
  }
  render() {
    const document = new DOMParser().parseFromString(this.props.html, 'text/html');
    return <>{[...document.body.childNodes].map(nodeView)}</>;
  }
}
const mounted = new WeakSet<HTMLElement>();
function mount(root: HTMLElement, view: ComponentChildren) {
  render(view, root);
  mounted.add(root);
}
export function renderMarkdownBody(root: HTMLElement, text: string, sources?: unknown) {
  mount(root, <MarkdownPart html={renderMarkdown(text, sources)} />);
}
type StreamState = { cut: number; chunks: ComponentChildren[]; tail: string | null };
const streams = new WeakMap<HTMLElement, StreamState>();
export function createLiveBody() {
  const root = document.createDocumentFragment();
  render(
    <div class="md cursor">
      <div class="stable" />
      <div class="tail" />
    </div>,
    root,
  );
  return root.firstElementChild as HTMLElement;
}
export function renderLiveMarkdown(
  root: HTMLElement,
  answer: string,
  sources: unknown,
  beforeReplace: (root: HTMLElement) => void,
) {
  const stable = root.querySelector<HTMLElement>('.stable');
  const tail = root.querySelector<HTMLElement>('.tail');
  if (!stable || !tail) throw new Error('Missing streaming Markdown slots');
  const state = streams.get(root) || { cut: 0, chunks: [], tail: null };
  const cut = stableCut(answer),
    previous = state.cut;
  if (cut < previous) {
    beforeReplace(stable);
    render(null, stable);
    state.chunks = cut ? [<MarkdownPart key={0} html={renderMarkdown(answer.slice(0, cut), sources)} />] : [];
  } else if (cut > previous)
    state.chunks = [
      ...state.chunks,
      <MarkdownPart key={state.chunks.length} html={renderMarkdown(answer.slice(previous, cut), sources)} />,
    ];
  if (cut !== previous) mount(stable, state.chunks);
  const html = renderMarkdown(answer.slice(cut), sources);
  if (html !== state.tail || cut !== previous) {
    beforeReplace(tail);
    mount(tail, <MarkdownPart key={cut} html={html} />);
    state.tail = html;
  }
  state.cut = cut;
  streams.set(root, state);
}
export function disposeMarkdownWithin(element: Element) {
  const roots = [...element.querySelectorAll<HTMLElement>('.md, .stable, .tail')];
  if (element instanceof HTMLElement && element.matches('.md, .stable, .tail')) roots.unshift(element);
  const detached: HTMLElement[] = [];
  for (const root of roots) {
    if (mounted.has(root)) {
      detached.push(root);
      mounted.delete(root);
    }
    streams.delete(root);
  }
  // The caller replaces/removes the enclosing DOM synchronously. Unmount block roots only once detached.
  if (detached.length)
    setTimeout(() => {
      for (const root of detached) render(null, root);
    }, 0);
}
