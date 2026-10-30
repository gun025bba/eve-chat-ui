type FrameProps = { role: string; content: string; time: number; label: string; who: string; id?: string };
export function MessageFrame({ role, content, time, label, who, id }: FrameProps) {
  return (
    // biome-ignore lint/a11y/useSemanticElements: Preserve the timeline div/listitem DOM contract.
    <div
      class={`msg ev ${role}${role === 'user' ? ' me' : role === 'assistant' ? ' e' : ''}`}
      data-t={String(time)}
      data-mid={id || undefined}
      role="listitem"
      aria-label={`${label} ${who}`}
    >
      <time class="tm" dateTime={new Date(time).toISOString()}>
        {label}
      </time>
      <span class="dot" aria-hidden="true" />
      <div class="who">
        <span class="who-n">{who}</span>
      </div>
      <div class="bubble tx">{role === 'user' ? content : null}</div>
    </div>
  );
}
export function NowEvent({ label }: { label: string }) {
  return (
    // biome-ignore lint/a11y/useSemanticElements: Preserve the timeline div/listitem DOM contract.
    <div class="rail-now" role="listitem" aria-label={`${label} 지금`}>
      <time class="tm">{label}</time>
      <span class="dot" aria-hidden="true" />
      <div class="who">
        <span class="who-n">지금</span>
      </div>
      <div class="tx d">아래에 한 줄로 남기면 오늘 기록에 쌓여요.</div>
    </div>
  );
}
export function Older({ loading = false }: { loading?: boolean }) {
  return (
    <div class={`older${loading ? ' loading' : ''}`}>
      <span class="spin" />
    </div>
  );
}
export function DateSeparator({ text }: { text: string }) {
  return <div class="day-sep">{text}</div>;
}
