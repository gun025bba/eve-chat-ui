import { type FeedbackMessage, feedbackPayload, type Rating } from '../../api/feedback.js';
import { FeedbackControls } from './controls.js';
import { FB_MAX, type Snapshot, snapshot } from './model.js';
import { PanelGroup, type PanelSession } from './panels.js';

type Error = { code?: string } | undefined;
type Host = {
  persist: () => void;
  isServer: () => boolean;
  buzz: (value: number) => void;
  convs: () => { messages?: FeedbackMessage[] }[];
  showToast: (text: string, action?: string, callback?: (() => void) | null, ms?: number) => void;
  write: (
    operation: string,
    key: string,
    payload: ReturnType<typeof feedbackPayload>,
    failed?: (error: Error) => 'handled' | undefined,
    message?: string,
  ) => Promise<unknown>;
};
class Feedback {
  private host!: Host;
  private controls = new Map<HTMLElement, FeedbackControls>();
  private panels: PanelGroup;
  constructor(
    box: HTMLElement,
    private live: HTMLElement | null,
  ) {
    this.panels = new PanelGroup(box);
  }
  init(host: Host) {
    this.host = host;
  }
  private announce(text: string) {
    if (!this.live) return;
    const live = this.live;
    live.textContent = '';
    setTimeout(() => {
      live.textContent = text;
    }, 30);
  }
  attach(actions: HTMLElement, message: FeedbackMessage) {
    this.controls.set(
      actions,
      new FeedbackControls(
        actions,
        {
          vote: (rating, button) => this.setFeedback(message, rating, actions, button),
          reasons: () => this.openPanel(message, actions),
        },
        message,
      ),
    );
  }
  private paint(actions: HTMLElement, message: FeedbackMessage) {
    this.controls.get(actions)?.paint(message.feedback, message);
  }
  private save(message: FeedbackMessage, actions: HTMLElement, previous: Snapshot): Promise<unknown> {
    this.host.persist();
    if (!this.host.isServer()) return Promise.resolve();
    const send = () => this.host.write('feedback', `fb:${message.id}`, feedbackPayload(message));
    return this.host.write(
      'feedback',
      `fb:${message.id}`,
      feedbackPayload(message),
      (error) => {
        if (error?.code === 'invalid_feedback_reason' && message.feedback) {
          message.fbReasons = [];
          this.host.persist();
          if (actions.isConnected) this.paint(actions, message);
          send();
          this.host.showToast('사유를 저장하지 못했어요. 평가는 저장됐어요', '', null, 2400);
          return 'handled';
        }
        if (error?.code === 'feedback_comment_too_long' && message.feedback) {
          message.fbComment = (message.fbComment || '').trim().slice(0, FB_MAX - 1);
          this.host.persist();
          send();
          this.host.showToast('메모가 너무 길어 줄여서 저장했어요', '', null, 2400);
          return 'handled';
        }
        Object.assign(message, previous);
        this.host.persist();
        if (actions.isConnected) {
          this.paint(actions, message);
          const former = previous.feedback || 'up';
          if (former === 'up' || former === 'down') this.controls.get(actions)?.flag(former, 'err', true);
          this.panels.close(actions, false);
        }
      },
      '피드백을 저장하지 못했어요',
    );
  }
  reasonRejected = (id?: string) => {
    for (const conversation of this.host.convs())
      for (const message of conversation.messages || []) {
        if (message.id === id) {
          message.fbReasons = [];
          this.host.persist();
        }
      }
    this.host.showToast('사유를 저장하지 못했어요. 평가는 저장됐어요', '', null, 2400);
  };
  private setFeedback(
    message: FeedbackMessage,
    rating: Exclude<Rating, null>,
    actions: HTMLElement,
    button: HTMLButtonElement,
  ) {
    const previous = snapshot(message),
      next = previous.feedback === rating ? null : rating;
    message.feedback = next;
    if (next !== previous.feedback) {
      message.fbReasons = [];
      message.fbComment = '';
    }
    this.paint(actions, message);
    this.host.buzz(8);
    const controls = this.controls.get(actions);
    if (next) controls?.pop(rating, button);
    controls?.clearErrors();
    controls?.flag(rating, 'sending', true);
    Promise.resolve(this.save(message, actions, previous)).finally(() => controls?.flag(rating, 'sending', false));
    if (next) {
      this.openPanel(message, actions);
      this.announce('피드백을 저장했어요. 사유를 고를 수 있어요');
    } else this.panels.close(actions, false);
  }
  private openPanel(message: FeedbackMessage, actions: HTMLElement) {
    const panel = this.panels.open(message, actions, {
      submit: (session) => this.submit(message, actions, session),
      paint: () => {
        if (actions.isConnected) this.paint(actions, message);
      },
    });
    if (panel) this.paint(actions, message);
  }
  private submit(message: FeedbackMessage, actions: HTMLElement, session: PanelSession) {
    const { comment, reasons } = session.selection(),
      previous = snapshot(message);
    const changed = comment !== previous.fbComment || reasons.join() !== previous.fbReasons?.join();
    message.fbReasons = reasons;
    message.fbComment = comment;
    session.collapse();
    if (changed) this.save(message, actions, previous);
    this.paint(actions, message);
    if (reasons.length || comment) this.thanks(actions);
  }
  private thanks(actions: HTMLElement) {
    const thanks = document.createElement('div');
    thanks.className = 'fb-thanks';
    thanks.textContent = '고마워요';
    actions.insertAdjacentElement('afterend', thanks);
    this.announce('고마워요');
    setTimeout(() => {
      thanks.classList.add('out');
      setTimeout(() => thanks.remove(), 300);
    }, 1500);
  }
  closeAll = () => this.panels.closeAll();
  detach(actions: HTMLElement) {
    this.panels.disposeFor(actions);
    this.controls.get(actions)?.dispose();
    this.controls.delete(actions);
  }
  disposeAll() {
    for (const actions of this.controls.keys()) this.detach(actions);
    this.panels.disposeAll();
  }
}
export function createFeedback(box: HTMLElement, live: HTMLElement | null) {
  return new Feedback(box, live);
}
