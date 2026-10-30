export type MemoryRef = { id: string; text: string };
export function MemoryChips({ refs, active }: { refs?: MemoryRef[]; active: boolean }) {
  if (!refs?.length || !active) return null;
  const label = (text: string) => {
    const points = [...String(text)];
    return points.length > 14 ? `${points.slice(0, 14).join('')}…` : points.join('');
  };
  const shown = refs.slice(0, 2),
    more = refs.length - shown.length;
  return (
    // biome-ignore lint/a11y/useSemanticElements: Preserve the existing memory chip group and CSS contract.
    <div class="mchips" role="group" aria-label="참고한 기억">
      {shown.map((ref) => (
        <button type="button" class="chp m" data-ref={ref.id} aria-label={`참고한 기억: ${ref.text}`}>
          <svg class="i" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M7 4h10a1 1 0 0 1 1 1v15l-6-4-6 4V5a1 1 0 0 1 1-1z" />
          </svg>
          <span>{label(ref.text)}</span>
        </button>
      ))}
      {more > 0 && <span class="chp-more">+{more}</span>}
    </div>
  );
}
