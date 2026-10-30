import { type ComponentChildren, render } from 'preact';
import { DateSeparator, MessageFrame, NowEvent, Older } from './timeline-view.js';

type Message = { id?: string; created?: number };
type Host = {
  time: (time: number) => string;
  day: (time: number) => string;
  separator: (time: number) => string;
  userName: () => string;
};
class Timeline {
  private roots = new Map<Element, DocumentFragment>();
  private last: HTMLElement | null = null;
  constructor(
    private box: HTMLElement,
    private host: Host,
  ) {}
  private mount(view: ComponentChildren) {
    const root = document.createDocumentFragment();
    render(view, root);
    const element = root.firstElementChild as HTMLElement;
    this.roots.set(element, root);
    return element;
  }
  add = (role: string, content: string, message?: Message) => {
    const time = message?.created && message.created > 0 ? message.created : Date.now();
    const who = role === 'user' ? this.host.userName() : 'Eve';
    const wrapper = this.mount(
      <MessageFrame
        role={role}
        content={content}
        time={time}
        label={this.host.time(time)}
        who={who}
        id={message?.id}
      />,
    );
    if (role !== 'error') this.separate(wrapper, time);
    if (!this.box.classList.contains('no-anim')) {
      for (const node of this.box.querySelectorAll(':scope > .msg.enter')) node.classList.remove('enter');
      wrapper.classList.add('enter');
    }
    this.box.appendChild(wrapper);
    const bubble = wrapper.querySelector<HTMLElement>('.bubble');
    if (!bubble) throw new Error('Missing message body');
    return bubble;
  };
  private separate(wrapper: HTMLElement, time: number) {
    const previous =
      this.last && this.box.contains(this.last)
        ? this.last
        : [...this.box.querySelectorAll<HTMLElement>(':scope > .msg:not(.error)')].pop();
    const changed = previous
      ? previous.dataset.t && this.host.day(+previous.dataset.t) !== this.host.day(time)
      : this.host.day(time) !== this.host.day(Date.now());
    if (changed) this.box.appendChild(this.mount(<DateSeparator text={this.host.separator(time)} />));
    this.last = wrapper;
  }
  now() {
    this.box.appendChild(this.mount(<NowEvent label={this.host.time(Date.now())} />));
  }
  tick() {
    const now = this.box.querySelector('.rail-now');
    if (!now || document.hidden) return;
    const label = this.host.time(Date.now());
    const time = now.querySelector('time');
    if (time) time.textContent = label;
    now.setAttribute('aria-label', `${label} 지금`);
  }
  loading() {
    this.box.appendChild(this.mount(<Older loading />));
  }
  older() {
    this.box.prepend(this.mount(<Older />));
  }
  remove(element: Element | null | undefined) {
    if (!element) return;
    const root = this.roots.get(element);
    if (root) render(null, root);
    this.roots.delete(element);
    element.remove();
  }
  clear() {
    for (const root of this.roots.values()) render(null, root);
    this.roots.clear();
    this.last = null;
    this.box.replaceChildren();
  }
}
export function createTimeline(box: HTMLElement, host: Host) {
  return new Timeline(box, host);
}
