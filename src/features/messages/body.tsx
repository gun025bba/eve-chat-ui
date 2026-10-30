import { render } from 'preact';
import { prepareSources } from '../../lib/sources.js';
import { MemoryChips, type MemoryRef } from './memory-chips.js';
import { SourceSection } from './sources/view.js';
import { type Note, ToolNote } from './tool-note.js';

type Body = {
  think: string | null;
  answer: string;
  live: boolean;
  thinking: boolean;
  open: boolean;
  user?: string;
  thinkSecs?: number;
  waiting: boolean;
  toolLine: boolean;
  slow: boolean;
  sources?: unknown;
  tools?: unknown;
  refs?: MemoryRef[];
  memoryActive: boolean;
  note: Note | null;
  nextSourceId: () => string;
};
function Think({ model }: { model: Body }) {
  if (model.think === null) return null;
  const label =
    model.live && model.thinking ? '생각하는 중…' : `생각 과정${model.thinkSecs ? ` · ${model.thinkSecs}초` : ''}`;
  return (
    <details
      class={`think${model.live && model.thinking ? ' live' : ''}`}
      open={model.open}
      data-user={model.user || undefined}
    >
      {/* biome-ignore lint/a11y/noStaticElementInteractions: Preserve native summary click bookkeeping. */}
      <summary
        onClick={(event) => {
          const details = event.currentTarget.parentElement;
          if (details) details.dataset.user = '1';
        }}
      >
        <svg class="i chev" aria-hidden="true">
          <use href="#i-chevron-right" />
        </svg>
        <span>{label}</span>
      </summary>
      <div class="think-body">{model.think}</div>
    </details>
  );
}
function Content({ model }: { model: Body }) {
  if (model.waiting)
    return model.toolLine ? null : (
      <>
        <span class="typing">
          <i />
          <i />
          <i />
        </span>
        {model.slow && <div class="warming">모델 준비 중…</div>}
      </>
    );
  if (model.live)
    return model.answer.trim() ? (
      <div class="md cursor">
        <div class="stable" />
        <div class="tail" />
      </div>
    ) : null;
  const sources = prepareSources(model.sources, model.tools);
  return (
    <>
      <div class="md" />
      {sources && <SourceSection model={sources} id={model.nextSourceId()} tools={model.tools} />}
      <MemoryChips refs={model.refs} active={model.memoryActive} />
      {model.note && <ToolNote note={model.note} />}
    </>
  );
}
const bodies = new WeakSet<HTMLElement>();
export function renderAssistantBody(root: HTMLElement, model: Body) {
  render(null, root);
  root.replaceChildren();
  bodies.add(root);
  render(
    <>
      <Think model={model} />
      <Content model={model} />
    </>,
    root,
  );
}

export function disposeAssistantBodiesWithin(element: Element) {
  const roots = [...element.querySelectorAll<HTMLElement>('.bubble')];
  if (element instanceof HTMLElement && element.matches('.bubble')) roots.unshift(element);
  for (const root of roots)
    if (bodies.has(root)) {
      render(null, root);
      bodies.delete(root);
    }
}
