import { render } from 'preact';
import { MessageIcon } from './parts-view.js';

type Flash = { timer: ReturnType<typeof setTimeout>; root: DocumentFragment; children: ChildNode[] };
export class MessageCopy {
  private flashes = new Map<HTMLButtonElement, Flash>();
  constructor(private toast: (text: string, action: string, callback: null, ms: number) => void) {}
  copy = async (button: HTMLButtonElement | null, text: string, label = false) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const input = document.createElement('textarea');
      input.value = text;
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      input.remove();
    }
    if (!button) return this.toast('복사됨', '', null, 1400);
    if (button.dataset.busy) return;
    button.dataset.busy = '1';
    const children = [...button.childNodes];
    const root = document.createDocumentFragment();
    render(
      <>
        <MessageIcon name="check" />
        {label && <span>복사됨</span>}
      </>,
      root,
    );
    button.replaceChildren(root);
    button.classList.add('done');
    this.flashes.set(button, { root, children, timer: setTimeout(() => this.restore(button), 1500) });
  };
  private restore(button: HTMLButtonElement) {
    const flash = this.flashes.get(button);
    if (!flash) return;
    clearTimeout(flash.timer);
    render(null, flash.root);
    button.replaceChildren(...flash.children);
    button.classList.remove('done');
    delete button.dataset.busy;
    this.flashes.delete(button);
  }
  disposeWithin(element: Element) {
    for (const button of this.flashes.keys()) if (element === button || element.contains(button)) this.restore(button);
  }
  disposeAll() {
    for (const button of this.flashes.keys()) this.restore(button);
  }
}
