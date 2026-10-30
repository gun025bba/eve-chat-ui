import { splitThink, stripStopMark } from '../../lib/think.js';
import { freshNote } from '../../lib/tool-status.js';
import { disposeAssistantBodiesWithin, renderAssistantBody } from './body.js';
import { createLiveBody, disposeMarkdownWithin, renderLiveMarkdown, renderMarkdownBody } from './markdown.js';
import type { Bubble, RenderHost, RenderOptions, ToolInfo } from './models.js';
import { messageStatus } from './status.js';

class Messages {
  readonly toolInfo = new Map<string, ToolInfo>();
  constructor(private host: RenderHost) {
    host.box.addEventListener('click', (event) => {
      if (!(event.target instanceof Element)) return;
      const memory = event.target.closest<HTMLElement>('.chp.m');
      if (memory) host.memoryClick(memory.dataset.ref || '');
      const button = event.target.closest<HTMLButtonElement>('.code-head .copy');
      const code = button?.closest('.codeblock')?.querySelector('code');
      if (button && code) host.parts.copy(button, code.textContent || '', true);
    });
    setInterval(() => host.timeline.tick(), 60000);
  }
  clear() {
    this.host.feedbackClear();
    this.host.parts.disposeAll();
    disposeMarkdownWithin(this.host.box);
    disposeAssistantBodiesWithin(this.host.box);
    this.host.timeline.clear();
  }
  remove(element: Element | null | undefined) {
    if (!element) return;
    const actions = element.querySelector<HTMLElement>('.actions');
    if (actions) this.host.feedbackDetach(actions);
    this.host.parts.disposeWithin(element);
    disposeMarkdownWithin(element);
    disposeAssistantBodiesWithin(element);
    this.host.timeline.remove(element);
  }
  now() {
    this.clear();
    this.host.timeline.now();
  }
  fill = (bubble: Bubble, text: string, options: RenderOptions = {}) => {
    const { think, answer, thinking } = splitThink(stripStopMark(text));
    const live = !!options.live;
    if (live) bubble._streamed = true;
    if (live && bubble._live && !options.slow && !options.resuming && this.patchLive(bubble, think, answer, thinking))
      return;
    this.body(bubble, think, answer, thinking, options);
    this.decorate(bubble, answer, think, options);
  };
  private patchThink(details: HTMLDetailsElement, think: string, thinking: boolean) {
    const body = details.querySelector<HTMLElement>('.think-body');
    const label = details.querySelector('summary span');
    if (!body || !label) return false;
    if (body.textContent.length !== think.length) {
      const atEnd = body.scrollHeight - body.scrollTop - body.clientHeight < 20;
      body.textContent = think;
      if (atEnd) body.scrollTop = body.scrollHeight;
    }
    details.classList.toggle('live', thinking);
    const text = thinking ? '생각하는 중…' : '생각 과정';
    if (label.textContent !== text) label.textContent = text;
    if (!thinking && !details.dataset.user && !this.host.showThink() && details.open) details.open = false;
    return true;
  }
  private patchLive(bubble: Bubble, think: string | null, answer: string, thinking: boolean): boolean {
    const details = bubble.querySelector<HTMLDetailsElement>('details.think');
    if ((think !== null) !== !!details) return false;
    if (details && think !== null && !this.patchThink(details, think, thinking)) return false;
    const markdown = bubble.querySelector<HTMLElement>('.md');
    if (!answer.trim()) return !markdown && (!!bubble.querySelector('.typing,.tline') || (!!details && thinking));
    if (!markdown) {
      for (const node of bubble.querySelectorAll('.typing,.warming')) node.remove();
      bubble._tsDrop?.();
      bubble.appendChild(createLiveBody());
      return this.patchLive(bubble, think, answer, thinking);
    }
    renderLiveMarkdown(markdown, answer, bubble._sources, (root) => this.host.parts.disposeWithin(root));
    return true;
  }
  private body(bubble: Bubble, think: string | null, answer: string, thinking: boolean, options: RenderOptions) {
    const live = !!options.live,
      previous = bubble.querySelector<HTMLDetailsElement>('details.think');
    const user = previous?.dataset.user;
    const sources = options.sources || options.msg?.sources || (live ? bubble._sources : null);
    const info = !live ? (options.msg?.id && this.toolInfo.get(options.msg.id)) || bubble._ti || null : null;
    const wasLive = bubble._streamed;
    bubble._streamed = live;
    bubble._live = live;
    if (bubble._tline && (!live || answer.trim())) bubble._tsDrop?.();
    this.host.parts.disposeWithin(bubble);
    disposeMarkdownWithin(bubble);
    renderAssistantBody(bubble, {
      think,
      answer,
      live,
      thinking,
      waiting: live && !answer.trim() && (think === null || !thinking),
      slow: !!options.slow,
      toolLine: !!bubble._tline,
      open: user && previous ? previous.open : (live && thinking) || this.host.showThink(),
      user,
      thinkSecs: options.thinkSecs,
      sources,
      tools: info?.tools || options.msg?.tools,
      refs: options.msg?.memoryRefs,
      memoryActive: this.host.memoryActive(),
      note: (info ? info.note : freshNote(options.msg)) || null,
      nextSourceId: this.host.nextSourceId,
    });
    const markdown = bubble.querySelector<HTMLElement>('.md');
    if (markdown) {
      if (live) renderLiveMarkdown(markdown, answer, sources, (root) => this.host.parts.disposeWithin(root));
      else renderMarkdownBody(markdown, answer, sources);
    }
    if (live && bubble._tline && !answer.trim()) {
      bubble.appendChild(bubble._tline);
      requestAnimationFrame(() => bubble._tline?.classList.add('in'));
    }
    if (wasLive && !live) bubble._freshAt = performance.now();
    this.fresh(bubble, live);
  }
  private fresh(bubble: Bubble, live: boolean) {
    const sections = !live && bubble._freshAt ? bubble.querySelectorAll<HTMLElement>('.sources, .mchips') : [];
    const elapsed = sections.length ? performance.now() - (bubble._freshAt || 0) : 1e9;
    if (elapsed < 120)
      for (const section of sections) {
        section.classList.add('fresh');
        if (elapsed > 1) section.style.animationDelay = `-${Math.round(elapsed)}ms`;
      }
  }
  private decorate(bubble: Bubble, answer: string, think: string | null, options: RenderOptions) {
    const wrapper = bubble.parentElement;
    if (!wrapper) return;
    const actions = wrapper.querySelector<HTMLElement>('.actions');
    if (actions) {
      this.host.feedbackDetach(actions);
      this.host.parts.disposeWithin(actions);
      actions.remove();
    }
    for (const node of wrapper.querySelectorAll('.stopped,.msg-note')) {
      this.host.parts.disposeWithin(node);
      node.remove();
    }
    const status = messageStatus(answer, think, options, this.host);
    if (status)
      wrapper.appendChild(
        this.host.parts.status(status.text, status.cls, status.role, status.retry ? this.host.regenerate : undefined),
      );
    if (options.live || options.actions === false) return;
    const row = this.host.parts.actions(answer, options.regen ? this.host.regenerate : undefined);
    const message = options.msg;
    if (message && (!this.host.isServer() || !!message.id)) this.host.feedbackAttach(row, message);
    if (options.usage) {
      const usage = document.createElement('span');
      usage.className = 'usage';
      usage.textContent = options.usage;
      row.appendChild(usage);
    }
    wrapper.appendChild(row);
  }
}
export function createMessages(host: RenderHost) {
  return new Messages(host);
}
