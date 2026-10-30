import { mapTools } from '../lib/tool-status.js';
export const toMs = (t) => {
  const v = Date.parse(t || '');
  return isNaN(v) ? Date.now() : v;
};
// confirm tokens must never reach localStorage, even if proactive.js failed to load (security review Low 1)
export const scrubAction = (a) => {
  const o = Object.assign({}, a);
  delete o.confirm_token;
  delete o.token_expires_at;
  return o;
};
export function createThreadModels({ fields, pinSet, usageText }) {
  function fromServerMsg(m) {
    let content = m.reasoning ? `<think>${m.reasoning}</think>${m.content || ''}` : m.content || '';
    const o = {
      id: m.id,
      role: m.role,
      content,
      feedback: m.feedback?.rating || null,
      fbReasons: Array.isArray(m.feedback?.reasons) ? m.feedback.reasons : [],
      fbComment: m.feedback?.comment || '',
      status: m.status || 'complete',
      errorCode: m.error_code || m.incomplete_reason || m.metadata?.reason || null,
      created: toMs(m.created_at),
    };
    const srcs = m.sources || m.metadata?.sources;
    if (Array.isArray(srcs) && srcs.length) o.sources = srcs;
    {
      const f = m.metadata?.fresh ?? m.fresh;
      if (f === 'unverified' || f === 'ok') o.fresh = f;
      const tl = mapTools(m.metadata?.tools ?? m.tools);
      if (tl) o.tools = tl;
    } // #134: the note (and a joined query) come back after a reload
    {
      const r = fields?.memoryRefs(m);
      if (r?.length) o.memoryRefs = r;
    } // DIRECTION-B §8.1: absent field → no chip
    const pm = fields?.msg(m);
    if (pm) Object.assign(o, pm);
    if (Array.isArray(m.pending_actions) && m.pending_actions.length)
      o.pendingActions = m.pending_actions.map(scrubAction);
    if (m.usage) {
      o.usage = m.usage;
      o.usageText = usageText(m.usage, m.latency_ms ? m.latency_ms / 1000 : 0);
    }
    return o;
  }
  function fromServerThread(t, old) {
    const updated = toMs(t.updated_at);
    return {
      id: t.id,
      srv: true,
      title: t.title || '새 대화',
      updated,
      created: toMs(t.created_at),
      archived: !!t.archived,
      preview: t.last_message_preview || '',
      count: t.message_count || 0,
      unread: fields ? fields.unread(t) : 0,
      pinned: pinSet().has(t.id),
      messages: old?.messages || [],
      hasMore: !!old?.hasMore,
      loaded: !!old?.loaded && old.updated === updated,
    };
  }
  return { fromServerMsg, fromServerThread };
}
