import type { Conversation } from './row.js';
export function selectList<C extends Conversation>(conversations: C[], query: string) {
  const live = conversations.filter((item) => !item.archived);
  live.sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned) || Number(b.updated) - Number(a.updated));
  const list = live.filter(
    (item) =>
      !query ||
      item.title.toLowerCase().includes(query) ||
      (item.messages || []).some((message) => (message.content || '').toLowerCase().includes(query)) ||
      (item.preview || '').toLowerCase().includes(query),
  );
  return { live, list };
}
