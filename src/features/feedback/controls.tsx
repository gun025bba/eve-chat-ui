import { createPortal, render } from 'preact';
import type { FeedbackMessage, Rating } from '../../api/feedback.js';

type Kind = 'up' | 'down';
type Flag = 'pop' | 'sending' | 'err';
type Actions = { vote: (rating: Kind, button: HTMLButtonElement) => void; reasons: () => void };
type State = { rating: Rating | undefined; count: number; hidden: boolean; up: Set<Flag>; down: Set<Flag> };
function Controls({ state, actions }: { state: State; actions: Actions }) {
  return (
    <>
      {(['up', 'down'] as const).map((kind) => {
        const on = kind === (state.rating === 'up' ? 'up' : 'down') && !!state.rating;
        const classes = ['fb', kind, on && 'on', !!state.rating && !on && 'dim', ...state[kind]]
          .filter(Boolean)
          .join(' ');
        return (
          <button
            key={kind}
            type="button"
            class={classes}
            aria-label={kind === 'up' ? '좋아요' : '별로예요'}
            aria-pressed={on}
            onClick={(event) => actions.vote(kind, event.currentTarget)}
          >
            <svg class="i" aria-hidden="true">
              <use href={kind === 'up' ? '#i-thumb-up' : '#i-thumb-down'} />
            </svg>
          </button>
        );
      })}
      <button
        type="button"
        class="fb-why"
        hidden={state.hidden}
        aria-label={state.count ? `피드백 사유 ${state.count}개 수정` : '피드백 사유 고르기'}
        onClick={actions.reasons}
      >
        {state.count ? `사유 ${state.count}` : '사유'}
      </button>
    </>
  );
}
export class FeedbackControls {
  private root = document.createDocumentFragment();
  private state: State = { rating: undefined, count: 0, hidden: true, up: new Set(), down: new Set() };
  private disposed = false;
  constructor(
    private target: HTMLElement,
    private actions: Actions,
    message: FeedbackMessage,
  ) {
    this.paint(message.feedback, message);
  }
  private draw() {
    if (!this.disposed)
      render(createPortal(<Controls state={this.state} actions={this.actions} />, this.target), this.root);
  }
  paint(rating: Rating | undefined, message: FeedbackMessage) {
    this.state.rating = rating;
    this.state.count = (message.fbReasons?.length || 0) + (message.fbComment ? 1 : 0);
    this.state.hidden = !rating || !!this.target.parentElement?.querySelector('.fbp:not(.closing)');
    this.draw();
  }
  flag(kind: Kind, flag: Flag, value: boolean) {
    if (value) this.state[kind].add(flag);
    else this.state[kind].delete(flag);
    this.draw();
  }
  clearErrors() {
    this.state.up.delete('err');
    this.state.down.delete('err');
    this.draw();
  }
  pop(kind: Kind, button: HTMLButtonElement) {
    this.flag(kind, 'pop', false);
    void button.offsetWidth;
    this.flag(kind, 'pop', true);
  }
  dispose() {
    this.disposed = true;
    render(null, this.root);
  }
}
