import { type ComponentChildren, render } from 'preact';
import { type Conversation, ConversationRow, type RowHost } from './row.js';
import type { SearchHit } from './search.js';
import { Snippet } from './snippet.js';

type Options<C> = {
  list: C[];
  query: string;
  flat: boolean;
  hits: SearchHit[] | null;
  pending: boolean;
  loading: boolean;
  server: boolean;
  host: RowHost<C>;
  hitTime: (date?: string) => string;
};
function Label({ text, count, day }: { text: string; count: number; day: string }) {
  return (
    <li class="group-label" data-day={day || undefined}>
      <span class="gl-n">{text}</span>
      <span class="gl-c">{count ? `대화 ${count}` : ''}</span>
    </li>
  );
}
function Hit({ hit, time }: { hit: SearchHit; time: (date?: string) => string }) {
  return (
    <li class="hit" data-tid={hit.thread_id} data-mid={hit.message_id || undefined}>
      <div class="row-main">
        <time class="r-tm">{time(hit.created_at)}</time>
        <div class="r-bd">
          <div class="row-top">
            <span class="row-title">{hit.thread_title || '대화'}</span>
          </div>
          <div class="row-sub snippet">
            <Snippet text={hit.snippet} />
          </div>
        </div>
      </div>
    </li>
  );
}
function Skeleton() {
  return (
    <li class="skel">
      <i />
      <i />
    </li>
  );
}
function grouped<C extends Conversation>(list: C[], host: RowHost<C>) {
  const counts = new Map<string, number>();
  const group = (item: C) => (item.pinned ? 'pin' : host.kstDay(item.updated || 0));
  for (const item of list) counts.set(group(item), (counts.get(group(item)) || 0) + 1);
  let last: string | null = null;
  const children: ComponentChildren[] = [];
  for (const item of list) {
    const key = group(item);
    if (key !== last) {
      children.push(
        <Label
          text={key === 'pin' ? '고정됨' : host.daySepText(item.updated || 0)}
          count={counts.get(key) || 0}
          day={key === 'pin' ? '' : key}
        />,
      );
      last = key;
    }
    children.push(<ConversationRow conversation={item} options={{ day: key === 'pin' }} host={host} />);
  }
  return children;
}
function List<C extends Conversation>(options: Options<C>) {
  const { list, query, flat, hits, host, hitTime, loading, server, pending } = options;
  const children: ComponentChildren[] = flat
    ? list.map((item) => <ConversationRow conversation={item} options={{ date: true }} host={host} />)
    : grouped(list, host);
  if (query && hits) {
    const matches = hits.filter((hit) => hit.match === 'content' || !list.some((item) => item.id === hit.thread_id));
    children.push(...matches.map((hit) => <Hit hit={hit} time={hitTime} />));
    if (!list.length && !matches.length) return <li class="no-results">결과 없음</li>;
  } else if (query && !list.length && !(server && pending)) return <li class="no-results">결과 없음</li>;
  if (loading && !query) for (let i = 0; i < 3; i++) children.push(<Skeleton />);
  return <>{children}</>;
}
function roundRows(root: HTMLElement) {
  let run: Element[] = [];
  const flush = () => {
    run[0]?.classList.add('g1');
    run[run.length - 1]?.classList.add('g9');
    run = [];
  };
  for (const child of root.children) {
    if (child.classList.contains('group-label') || child.classList.contains('no-results')) flush();
    else run.push(child);
  }
  flush();
}
export function renderList<C extends Conversation>(root: HTMLElement, options: Options<C>) {
  render(null, root);
  render(<List {...options} />, root);
  roundRows(root);
}
export function renderArchive<C extends Conversation>(root: HTMLElement, list: C[], host: RowHost<C>) {
  render(null, root);
  render(
    list
      .sort((a, b) => Number(b.updated) - Number(a.updated))
      .map((item) => <ConversationRow conversation={item} cls=" archived" host={host} />),
    root,
  );
  root.firstElementChild?.classList.add('g1');
  root.lastElementChild?.classList.add('g9');
}
export function renderArchiveLoading(root: HTMLElement) {
  render(null, root);
  render(<Skeleton />, root);
}
