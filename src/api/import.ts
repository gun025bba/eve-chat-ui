import { splitThink } from '../lib/think.js';

export type LocalMessage = { role: string; content?: string; created?: number };
export type LocalConversation = {
  id: string;
  title?: string;
  created?: number;
  updated?: number;
  archived?: boolean;
  messages: LocalMessage[];
};
export type ImportFailure = { id: string; title?: unknown; reason?: unknown };
type Result = { client_id?: string; thread_id?: string; status?: string; error?: { message?: unknown } };
type Response = { results?: Result[]; mapping?: { client_id?: string; id?: string }[] };
function toImport(conversation: LocalConversation, model: string) {
  const c = conversation,
    base = (c.created || c.updated || Date.now()) - c.messages.length * 1000;
  return {
    client_id: `local:${c.id}`,
    title: c.title || '대화',
    created_at: new Date(base).toISOString(),
    archived: !!c.archived,
    messages: c.messages
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((message, index) => {
        const m = message;
        const row: {
          client_id: string;
          role: string;
          created_at: string;
          content?: string;
          reasoning?: string;
          model?: string;
        } = {
          client_id: `local:${c.id}:${index}`,
          role: m.role,
          created_at: new Date(m.created || base + index * 1000).toISOString(),
        };
        if (m.role === 'assistant') {
          const think = splitThink(m.content || '');
          row.content = think.answer;
          if (think.think) row.reasoning = think.think;
          row.model = model;
        } else row.content = m.content || '';
        return row;
      }),
  };
}
export function createImportBody(items: LocalConversation[], model: () => string) {
  return JSON.stringify({ threads: items.map((item) => toImport(item, model())) });
}
export function importOutcome(value: unknown, items: LocalConversation[]) {
  const response = value as Response | null;
  const res: Result[] =
    response?.results ||
    (response?.mapping || []).map((m) => ({ client_id: m.client_id, thread_id: m.id, status: 'created' }));
  const ok: string[] = [],
    fail: ImportFailure[] = [];
  for (const c of items) {
    const r = res.find((row) => row.client_id === `local:${c.id}`);
    if (r && (r.status === 'created' || r.status === 'exists' || r.thread_id)) ok.push(c.id);
    else fail.push({ id: c.id, title: c.title, reason: r?.error?.message || r?.status || '응답에 결과가 없어요' });
  }
  return { ok, fail };
}
