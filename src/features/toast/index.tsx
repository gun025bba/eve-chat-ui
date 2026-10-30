import { render } from 'preact';

type ToastState = { text: string; action: string; hidden: boolean; shown: boolean };
type Callback = (() => void) | null | undefined;

function Toast({ state, onAction }: { state: ToastState; onAction: () => void }) {
  return (
    <div id="toast" hidden={state.hidden} role="status" class={state.shown ? 'show' : undefined}>
      <span id="toastText">{state.text}</span>
      <button type="button" id="toastAct" class="text-btn" hidden={!state.action} onClick={onAction}>
        {state.action}
      </button>
    </div>
  );
}

export function mountToast(root: Element) {
  const state: ToastState = { text: '', action: '', hidden: true, shown: false };
  let timer = 0;
  let callback: Callback;
  const draw = () => render(<Toast state={state} onAction={act} />, root);
  function hideToast() {
    state.shown = false;
    draw();
    setTimeout(() => {
      if (!state.shown) {
        state.hidden = true;
        draw();
      }
    }, 300);
  }
  function act() {
    hideToast();
    callback?.();
  }
  function showToast(text: string, action?: string, fn?: Callback, ms?: number) {
    state.text = text;
    state.action = action || '';
    callback = fn;
    state.hidden = false;
    draw();
    requestAnimationFrame(() => {
      state.shown = true;
      draw();
    });
    clearTimeout(timer);
    if (ms) timer = window.setTimeout(hideToast, ms);
  }
  draw();
  return { showToast, hideToast };
}
