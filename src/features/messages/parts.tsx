import { render } from 'preact';
import { MessageCopy } from './copy.js';
import { ActionButtons, ErrorContent, StatusContent } from './parts-view.js';

type Part = { timer?: ReturnType<typeof setTimeout> };
class MessageParts {
  private parts = new Map<Element, Part>();
  private clipboard: MessageCopy;
  constructor(toast: (text: string, action: string, callback: null, ms: number) => void) {
    this.clipboard = new MessageCopy(toast);
  }
  copy = (button: HTMLButtonElement | null, text: string, label = false) => this.clipboard.copy(button, text, label);
  actions(answer: string, regenerate?: () => void) {
    const root = document.createElement('div');
    root.className = 'actions';
    render(<ActionButtons copy={(button) => this.copy(button, answer.trim())} regenerate={regenerate} />, root);
    this.parts.set(root, {});
    return root;
  }
  error(root: HTMLElement, text: string, retry?: () => void, retryAfter = 0) {
    const draw = (disabled: boolean) => render(<ErrorContent text={text} retry={retry} disabled={disabled} />, root);
    draw(!!retry && retryAfter > 0);
    const timer = retry && retryAfter > 0 ? setTimeout(() => draw(false), retryAfter * 1000) : undefined;
    this.parts.set(root, { timer });
  }
  status(text: string, className: string, role: 'note' | 'status', retry?: () => void) {
    const root = document.createElement('div');
    root.className = className;
    root.setAttribute('role', role);
    render(<StatusContent text={text} retry={retry} />, root);
    this.parts.set(root, {});
    return root;
  }
  private dispose(root: Element, part: Part) {
    clearTimeout(part.timer);
    render(null, root);
    this.parts.delete(root);
  }
  disposeWithin(element: Element) {
    this.clipboard.disposeWithin(element);
    for (const [root, part] of this.parts) if (element === root || element.contains(root)) this.dispose(root, part);
  }
  disposeAll() {
    this.clipboard.disposeAll();
    for (const [root, part] of this.parts) this.dispose(root, part);
  }
}
export function createMessageParts(toast: (text: string, action: string, callback: null, ms: number) => void) {
  return new MessageParts(toast);
}
