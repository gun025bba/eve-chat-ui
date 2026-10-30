export type Conversation = {
  id: string;
  title: string;
  pinned?: boolean;
  updated?: number;
  unread?: number;
  messages?: { origin?: string; content?: string }[];
  preview?: string;
  archived?: boolean;
};
export type RowHost<C> = {
  currentId: string | null;
  local: boolean;
  generatingId: string | null;
  hhmm: (time: number) => string;
  kstDay: (time: number) => string;
  daySepText: (time: number) => string;
  preview: (conversation: C) => string;
  decorate: (row: HTMLElement, conversation: C) => void;
};
export type RowOptions = { day?: boolean; date?: boolean };
function EveMark() {
  return (
    <svg class="r-eve" viewBox="0 0 100 100" aria-hidden="true">
      <path
        d="M14 54V36a16 16 0 0 1 16-16h40a16 16 0 0 1 16 16v28a16 16 0 0 1-16 16H34"
        fill="none"
        stroke="currentColor"
        stroke-width="9"
      />
      <rect x="32" y="37" width="10" height="26" rx="5" fill="var(--brand)" />
    </svg>
  );
}
function RowActions({ archived, local }: { archived: boolean; local: boolean }) {
  return (
    <div class="row-actions">
      {archived ? (
        <>
          <button type="button" class="ra-restore" tabIndex={-1}>
            복원
          </button>
          {local && (
            <button type="button" class="ra-del" tabIndex={-1}>
              삭제
            </button>
          )}
        </>
      ) : (
        <>
          <button type="button" class="ra-rename" tabIndex={-1}>
            이름 변경
          </button>
          <button type="button" class="ra-archive" tabIndex={-1}>
            보관
          </button>
        </>
      )}
    </div>
  );
}
function shortDate(day: string) {
  const [, month, date] = day.split('-').map(Number);
  return `${month}.${date}`;
}
type Props<C> = { conversation: C; cls?: string; options?: RowOptions; host: RowHost<C> };
function decorate<C>(row: HTMLLIElement | null, conversation: C, host: RowHost<C>) {
  if (!row) return;
  host.decorate(row, conversation);
  const mark = row.querySelector('.r-eve');
  if (mark) row.querySelector('.row-top')?.appendChild(mark);
}
export function ConversationRow<C extends Conversation>({ conversation: c, cls = '', options = {}, host }: Props<C>) {
  const time = c.updated || Date.now();
  const label =
    options.day && host.kstDay(time) !== host.kstDay(Date.now()) ? shortDate(host.kstDay(time)) : host.hhmm(time);
  const proactive = (c.unread || 0) > 0 || (c.messages || []).some((m) => m.origin === 'proactive');
  return (
    <li
      class={`row${cls}${c.id === host.currentId ? ' active' : ''}`}
      data-id={c.id}
      ref={(row) => decorate(row, c, host)}
    >
      <RowActions archived={cls.includes('archived')} local={host.local} />
      <div class="row-main">
        <time class="r-tm" dateTime={new Date(time).toISOString()}>
          {label}
        </time>
        <div class="r-bd">
          <div class="row-top">
            <span class="row-title">{(c.pinned ? '📌 ' : '') + c.title}</span>
            {proactive && <EveMark />}
          </div>
          <div class="row-sub">
            {host.generatingId === c.id ? (
              <>
                <span class="spin" aria-hidden="true" />
                답변 중…
              </>
            ) : (
              (options.date ? `${host.daySepText(time).replace(/ · .*/, '')} · ` : '') + host.preview(c)
            )}
          </div>
        </div>
      </div>
    </li>
  );
}
