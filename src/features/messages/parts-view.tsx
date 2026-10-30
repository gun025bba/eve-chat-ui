export function MessageIcon({ name }: { name: string }) {
  return (
    <svg class="i" aria-hidden="true">
      <use href={`#i-${name}`} />
    </svg>
  );
}
export function ActionButtons({
  copy,
  regenerate,
}: {
  copy: (button: HTMLButtonElement) => void;
  regenerate?: () => void;
}) {
  return (
    <>
      <button type="button" class="c" aria-label="복사" onClick={(event) => copy(event.currentTarget)}>
        <MessageIcon name="copy" />
      </button>
      {regenerate && (
        <button type="button" class="r" aria-label="다시 생성" onClick={regenerate}>
          <MessageIcon name="regenerate" />
        </button>
      )}
    </>
  );
}
export function ErrorContent({ text, retry, disabled }: { text: string; retry?: () => void; disabled: boolean }) {
  return (
    <>
      <MessageIcon name="warning" />
      <span class="err-text">{text}</span>
      {retry && (
        <button type="button" class="btn retry" disabled={disabled} onClick={retry}>
          다시 시도
        </button>
      )}
    </>
  );
}
