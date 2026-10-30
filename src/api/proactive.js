/* Eve proactive messaging (선톡) P1 — API layer.
 * Every server call for 선톡 / confirm cards / Web Push goes through this file, so swapping
 * a planned endpoint for the real one is a one-line change here.
 *
 * status: 'defined'  = contract written in eve-serving docs/tool-platform.md §10.3 (not implemented yet)
 *         'planned'  = named in docs/architecture/proactive-messaging.md, shape not defined yet
 *         'mock'     = invented by the UI (no backend design yet) — see README "선톡 API 상태"
 * The UI ships no client-side mock: a 404/501 means "server doesn't support it yet" and the
 * feature hides itself. The test mock lives server-side in tests/mock.py.
 */
export default function createProactiveAPI({ cleanBriefing }) {
  const E = encodeURIComponent;
  const ENDPOINTS = {
    unreadThreads:  { status: 'defined', method: 'GET',    path: () => '/v1/threads?unread=true&limit=100' }, // unread_count per thread (no /v1/notifications)
    threadMessages: { status: 'defined', method: 'GET',    path: id => `/v1/threads/${E(id)}/messages?limit=50` },   // locate push nid (= message_id): {data:[{id,thread_id,created_at,job_id}]}
    markThreadRead: { status: 'defined', method: 'POST',   path: id => `/v1/threads/${E(id)}/read` },        // CT Q6 → {unread_count:0}
    markRead:       { status: 'defined', method: 'POST',   path: id => `/v1/messages/${E(id)}/read` },
    getSettings:    { status: 'defined', method: 'GET',    path: () => '/v1/settings' },                      // architect: {proactive:{enabled, quiet_hours}, memory:{enabled}}; quiet_hours shape assumed {start:'HH:MM',end:'HH:MM'}
    patchSettings:  { status: 'defined', method: 'PATCH',  path: () => '/v1/settings' },                      // changed keys only, e.g. {proactive:{enabled:true}}
    getAction:      { status: 'assumed', method: 'GET',    path: id => `/v1/actions/${E(id)}` },             // single-action status after an ambiguous approve; not in CT yet (falls back to pendingActions)
    pendingActions: { status: 'defined', method: 'GET',    path: () => '/v1/actions?status=pending' },        // restore cards after reload (no tokens)
    reissue:        { status: 'defined', method: 'POST',   path: id => `/v1/actions/${E(id)}/reissue` },      // → {confirm_token, token_expires_at}
    approve:        { status: 'defined', method: 'POST',   path: id => `/v1/actions/${E(id)}/approve` },      // body {confirm_token, payload_hash}
    reject:         { status: 'defined', method: 'POST',   path: id => `/v1/actions/${E(id)}/reject` },
    revise:         { status: 'defined', method: 'POST',   path: id => `/v1/proposals/${E(id)}/revise` },     // body {item_ids} → new proposal (new payload_hash + token); Part B forget card
    vapidKey:       { status: 'defined',   method: 'GET',    path: () => '/v1/push/vapid-public-key' },         // → {key (base64url), key_id}
    subscribe:      { status: 'defined',   method: 'POST',   path: () => '/v1/push/subscriptions' },            // body {endpoint, keys:{p256dh,auth}, vapid_key_id}
    unsubscribe:    { status: 'defined',   method: 'DELETE', path: () => '/v1/push/subscriptions' },            // body {endpoint}
    briefingPreview: { status: 'defined',  method: 'POST',   path: () => '/v1/briefing/preview' }               // eve-serving #77: interactive scope; 200 {status,text,sections}, 502 {status,sections} (no text), 404 when off
  };
  /* Field mapping: the ONLY place that knows server field names (eve-serving PR #12
   * docs/architecture/ui-api-contract.md, not merged yet — "CT"). If the contract changes, edit here. */
  const S = v => (typeof v === 'string' ? v : null);
  const FIELDS = {
    msg(m) {                                            // CT Q1/Q3/Q4
      if (!m || m.origin !== 'proactive') return null;
      const pv = m.provenance || {};
      return { origin: 'proactive', readAt: m.read_at || null, jobId: S(m.job_id) || S(pv.job_id), jobName: S(pv.job_name), kind: m.kind === 'digest' ? 'digest' : null,
        templateKind: ['briefing', 'watch', 'followup'].includes(m.template_kind) ? m.template_kind : null,   // top-level only (backend answer)   // unknown kind → null
        briefing: cleanBriefing ? cleanBriefing(m.briefing) : null };   // eve-serving #66 §11.3: validated (schema 1 only, known section kinds, ≤10 items); anything else → null (content only)
    },
    memoryRefs: m => Array.isArray(m && m.memory_refs) ? m.memory_refs.filter(r => r && typeof r.id === 'string' && typeof r.text === 'string' && r.text.trim()).slice(0, 20).map(r => ({ id: r.id, text: r.text })) : [],   // DIRECTION-B §8.1 (field not confirmed server-side: absent → [] → chip hidden)
    unread: t => +(t && t.unread_count) || 0,           // CT Q2
    action(a) {                                         // CT Q10–Q14 (SSE confirmation / pending_actions / GET /v1/actions)
      const pv = a.provenance || {}, v = a.payload_view && typeof a.payload_view === 'object' ? a.payload_view : {};
      const verbs = (Array.isArray(a.scopes) ? a.scopes : []).map(x => String(x).split('.').pop());
      return {
        id: S(a.action_id), tool: S(a.tool) || '', summary: S(a.summary) || '', view: v, hash: a.payload_hash,
        expiresAt: Date.parse(a.expires_at || '') || 0,
        tainted: !!a.tainted, status: S(a.status), errorCode: S(a.error_code), verbs,
        actor: pv.actor === 'scheduler' ? 'scheduler' : 'user', jobName: S(pv.job_name), threadId: S(a.thread_id), messageId: S(a.message_id),
        op: S(v.op), items: Array.isArray(v.items) ? v.items.map(i => ({ id: i && i.id != null ? String(i.id) : null, text: S(i && i.text) || '', kind: S(i && i.kind), updatedAt: S(i && i.updated_at) })) : [],
        scopes: Array.isArray(a.scopes) ? a.scopes.map(String) : [],   // raw scope strings (e.g. reminders.write): the card labels pim rows by scope
        verb: S(v.verb), ambiguous: v.ambiguous === true, display: S(v.display), whenAt: S(v.when && v.when.at)
      };
    },
    briefing(j) {                                       // eve-serving #77 POST /v1/briefing/preview: {status, text?, sections:[{name, code?, count}]}; sections is null/absent when pim is off
      const o = j && typeof j === 'object' ? j : {}, n = v => (typeof v === 'number' && Number.isFinite(v) && v >= 0 ? Math.floor(v) : null);
      return { status: S(o.status) || '', text: S(o.text) || '',
        sections: (Array.isArray(o.sections) ? o.sections : []).filter(x => x && typeof x === 'object').map(x => ({ name: S(x.name) || '', code: S(x.code) || null, count: n(x.count) })) };
    },
    system: s => { const y = (s && s.system) || {}; return { proactive: y.proactive_available !== false, tools: y.tools_available !== false, memoryRO: false }; }   // memory read-only is never read from settings: only a 503 memory_read_only sets it (architect, 0cdadea)   // CT Q8/Q17, read-only
  };
  const UNSUPPORTED = new Set([404, 405, 501]);
  // Confirm-token + decision endpoints send no CORS headers: same-origin only (/ui/ → relative /v1). eve-serving PR #16.
  const SAME_ORIGIN_ONLY = new Set(['briefingPreview', 'reissue', 'approve', 'reject', 'revise', 'getAction', 'pendingActions']);
  function make(api, sameOrigin = () => true) {
    const call = (name, arg, body) => {
      const e = ENDPOINTS[name];
      if (SAME_ORIGIN_ONLY.has(name) && !sameOrigin()) return Promise.reject(Object.assign(new Error('cross-origin'), { code: 'cross_origin', http: 0 }));
      return api(e.path(arg), body === undefined ? { method: e.method } : { method: e.method, body: JSON.stringify(body) });
    };
    return {
      ENDPOINTS, unsupported: e => UNSUPPORTED.has(e && e.http),
      unreadThreads: () => call('unreadThreads'),
      threadMessages: id => call('threadMessages', id),
      markRead: id => call('markRead', id, {}),
      getSettings: () => call('getSettings'),
      patchSettings: changed => call('patchSettings', null, changed),
      revise: (id, itemIds) => call('revise', id, itemIds ? { item_ids: itemIds } : {}),   // body = {item_ids} only; none → {} ; → new confirmation object
      pendingActions: () => call('pendingActions'),
      getAction: id => call('getAction', id),
      reissue: id => call('reissue', id, {}),
      approve: (id, token, hash) => call('approve', id, { confirm_token: token, payload_hash: hash }),
      reject: id => call('reject', id, {}),
      markThreadRead: id => call('markThreadRead', id, {}),
      vapidKey: () => call('vapidKey'),
      subscribe: (sub, keyId) => call('subscribe', null, { endpoint: sub.endpoint, keys: sub.keys, vapid_key_id: keyId }),
      unsubscribe: endpoint => call('unsubscribe', null, { endpoint }),
      briefingPreview: () => call('briefingPreview', null, {})
    };
  }
  return { make, ENDPOINTS, FIELDS };
}
