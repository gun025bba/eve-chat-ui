import type { TargetedKeyboardEvent } from 'preact';
import { FB_CHIPS, FB_MAX } from './model.js';
export type PanelViewState = {
  kind: 'up' | 'down';
  picks: Set<string>;
  comment: string;
  note: boolean;
  id: string;
};
type Actions = {
  pick: (key: string) => void;
  note: () => void;
  input: (value: string) => void;
  submit: () => void;
  key: (event: TargetedKeyboardEvent<HTMLInputElement>) => void;
};
function Note({ state, actions }: { state: PanelViewState; actions: Actions }) {
  return (
    <div class="fbp-note" hidden={!state.note}>
      <label for={state.id} class="sr-only">
        메모
      </label>
      <input
        id={state.id}
        class="fbp-input"
        type="text"
        maxLength={FB_MAX}
        enterKeyHint="send"
        autoComplete="off"
        autoCorrect="on"
        autoCapitalize="sentences"
        data-1p-ignore
        data-lpignore="true"
        data-form-type="other"
        placeholder="한 줄로 남겨 주세요"
        value={state.comment}
        onInput={(event) => actions.input(event.currentTarget.value)}
        onKeyDown={actions.key}
      />
      <span class="fbp-count" hidden={state.comment.length <= 120}>
        {FB_MAX - state.comment.length}
      </span>
    </div>
  );
}
export function PanelView({ state, actions }: { state: PanelViewState; actions: Actions }) {
  const any = state.picks.size > 0 || !!state.comment.trim();
  return (
    <div class="fbp-in">
      <p class="fbp-hint">{state.kind === 'down' ? '어떤 점이 아쉬웠나요? (선택)' : '어떤 점이 좋았나요? (선택)'}</p>
      {/* biome-ignore lint/a11y/useSemanticElements: Preserve the existing group markup. */}
      <div class="fbp-chips" role="group" aria-label={state.kind === 'down' ? '아쉬운 점' : '좋았던 점'}>
        {FB_CHIPS[state.kind].map(([key, text]) => (
          <button
            key={key}
            type="button"
            class="fbchip"
            data-k={key}
            aria-pressed={state.picks.has(key)}
            onClick={() => actions.pick(key)}
          >
            <svg class="i" aria-hidden="true">
              <use href="#i-check" />
            </svg>
            <span>{text}</span>
          </button>
        ))}
      </div>
      <Note state={state} actions={actions} />
      <div class="fbp-foot">
        <button type="button" class="fbp-memo text-btn" hidden={state.note} onClick={actions.note}>
          메모 추가
        </button>
        <button type="button" class={any ? 'fbp-done primary-text' : 'fbp-done'} onClick={actions.submit}>
          {any ? '완료' : '건너뛰기'}
        </button>
      </div>
    </div>
  );
}
