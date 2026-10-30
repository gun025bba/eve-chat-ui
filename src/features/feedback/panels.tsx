import { render } from 'preact';
import type { FeedbackMessage } from '../../api/feedback.js';
import { FB_CHIPS, FB_MAX } from './model.js';
import { PanelView, type PanelViewState } from './view.js';

type Bindings = { submit: (session: PanelSession) => void; paint: () => void };
export class PanelSession {
  readonly element = document.createElement('div');
  readonly input: HTMLInputElement;
  readonly state: PanelViewState;
  closing = false;
  dirty = false;
  seen = false;
  scroll = 0;
  constructor(
    readonly actions: HTMLElement,
    message: FeedbackMessage,
    private group: PanelGroup,
    private bindings: Bindings,
  ) {
    this.element.className = 'fbp';
    this.state = {
      kind: message.feedback as 'up' | 'down',
      picks: new Set(message.fbReasons || []),
      comment: String(message.fbComment || ''),
      note: !!message.fbComment,
      id: `fbn${Math.random().toString(36).slice(2, 8)}`,
    };
    this.draw();
    const input = this.element.querySelector<HTMLInputElement>('.fbp-input');
    if (!input) throw new Error('Missing feedback input');
    this.input = input;
    actions.insertAdjacentElement('afterend', this.element);
    this.element.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !event.isComposing) {
        event.preventDefault();
        event.stopPropagation();
        group.close(actions, true);
      }
    });
    requestAnimationFrame(() => requestAnimationFrame(() => this.element.classList.add('open')));
  }
  private draw() {
    render(
      <PanelView
        state={this.state}
        actions={{
          pick: this.pick,
          note: this.showNote,
          input: (value) => {
            this.state.comment = value;
            this.dirty = true;
            this.draw();
          },
          submit: this.submit,
          key: (event) => {
            if (event.key === 'Enter' && !event.isComposing && event.keyCode !== 229) {
              event.preventDefault();
              this.submit();
            }
          },
        }}
      />,
      this.element,
    );
  }
  private pick = (key: string) => {
    const on = !this.state.picks.has(key);
    if (on) this.state.picks.add(key);
    else this.state.picks.delete(key);
    this.dirty = true;
    if (key === 'other' && on) this.showNote();
    else this.draw();
  };
  private showNote = () => {
    this.state.note = true;
    this.draw();
    this.input.focus({ preventScroll: true });
  };
  selection() {
    return {
      comment: this.input.value.trim().slice(0, FB_MAX),
      reasons: FB_CHIPS[this.state.kind].map((chip) => chip[0]).filter((key) => this.state.picks.has(key)),
    };
  }
  submit = () => this.bindings.submit(this);
  collapse() {
    this.closing = true;
    this.group.unobserve(this.element);
    this.element.classList.remove('open');
    this.element.classList.add('closing');
    setTimeout(() => this.dispose(), 280);
  }
  close(skip: boolean) {
    if (this.closing) return;
    if (skip && (this.state.picks.size || this.input.value.trim()) && this.dirty) return this.submit();
    this.collapse();
    setTimeout(this.bindings.paint, 290);
  }
  dispose() {
    this.group.unobserve(this.element);
    render(null, this.element);
    this.element.remove();
    this.group.forget(this.element);
  }
}
export class PanelGroup {
  private sessions = new Map<HTMLElement, PanelSession>();
  private escapes = new WeakSet<HTMLElement>();
  private observer: IntersectionObserver | null = null;
  constructor(private box: HTMLElement) {}
  open(message: FeedbackMessage, actions: HTMLElement, bindings: Bindings) {
    const parent = actions.parentElement;
    const previous = parent?.querySelector<HTMLElement>('.fbp');
    if (previous) this.sessions.get(previous)?.dispose();
    parent?.querySelector('.fb-thanks')?.remove();
    if (!message.feedback) return;
    const session = new PanelSession(actions, message, this, bindings);
    this.sessions.set(session.element, session);
    if (!this.escapes.has(actions)) {
      this.escapes.add(actions);
      actions.addEventListener('keydown', (event) => {
        if (
          event.key === 'Escape' &&
          !event.isComposing &&
          actions.parentElement?.querySelector('.fbp:not(.closing)')
        ) {
          event.preventDefault();
          event.stopPropagation();
          this.close(actions, true);
        }
      });
    }
    this.observe(session);
    return session;
  }
  private observe(session: PanelSession) {
    if (!('IntersectionObserver' in window)) return;
    this.observer ||= new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const state = this.sessions.get(entry.target as HTMLElement);
          if (!state) continue;
          if (entry.isIntersecting) {
            state.seen = true;
            continue;
          }
          if (
            state.seen &&
            !state.closing &&
            document.activeElement !== state.input &&
            Math.abs(this.box.scrollTop - state.scroll) > 40
          )
            this.close(state.actions, true);
        }
      },
      { root: this.box, threshold: 0 },
    );
    setTimeout(() => {
      if (session.element.isConnected && !session.closing) {
        session.scroll = this.box.scrollTop;
        this.observer?.observe(session.element);
      }
    }, 320);
  }
  unobserve(element: HTMLElement) {
    this.observer?.unobserve(element);
  }
  forget(element: HTMLElement) {
    this.sessions.delete(element);
  }
  close(actions: HTMLElement, skip: boolean) {
    const panel = actions.parentElement?.querySelector<HTMLElement>('.fbp');
    if (panel) this.sessions.get(panel)?.close(skip);
  }
  closeAll() {
    for (const session of this.sessions.values()) if (session.element.isConnected) session.close(true);
  }
  disposeAll() {
    for (const session of this.sessions.values()) session.dispose();
  }
}
