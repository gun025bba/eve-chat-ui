/* Eve memory (Part B) — API layer + field mapping. The ONLY file that knows memory endpoint paths and
 * server field names. Schema frozen in eve-serving ui-api-contract §3.9 (PR #32).
 * Exception still open: where memory.enabled lives in /v1/settings (awaiting architect) — isolated in SETTINGS below. */
(function () {
  const E = encodeURIComponent;
  const ENDPOINTS = {                                                    // §3.9.2 / §3.9.3
    list:       { method: 'GET',    path: () => '/v1/memory' },
    exportAll:  { method: 'GET',    path: () => '/v1/memory/export' },
    addItem:    { method: 'POST',   path: () => '/v1/memory/items' },
    editItem:   { method: 'PATCH',  path: id => `/v1/memory/items/${E(id)}` },
    deleteItem: { method: 'DELETE', path: id => `/v1/memory/items/${E(id)}` },   // 204, no body
    deleteAll:  { method: 'DELETE', path: () => '/v1/memory' },                  // 204, no body
    getSettings:  { method: 'GET',   path: () => '/v1/settings' },
    patchSettings:{ method: 'PATCH', path: () => '/v1/settings' }
  };
  const S = v => (typeof v === 'string' ? v : null);
  const KINDS = ['profile', 'preference', 'fact', 'task'];
  const ms = t => Date.parse(t || '') || 0;
  const FIELDS = {
    list: j => (Array.isArray(j?.items) ? j.items : []).map(FIELDS.item).filter(x => x.id),        // {object:'memory', updated_at, items}
    item: i => ({ id: i && i.id != null ? String(i.id) : null, kind: KINDS.includes(i?.kind) ? i.kind : 'fact', text: S(i?.text) || '',
      pinned: i?.pinned === true, confidence: i?.confidence === 'confirmed' ? 'confirmed' : 'user',
      updatedAtRaw: S(i?.updated_at), updatedAt: ms(i?.updated_at), expiresAt: ms(i?.expires_at) }),
    add: (kind, text) => ({ kind, text }),                                 // strict body: unknown fields → 400
    edit: (it, text) => ({ text, if_updated_at: it.updatedAtRaw || undefined })   // 409 conflict if changed meanwhile
  };
  // §3.9.7 — PLACEMENT NOT CONFIRMED (architect). Only this object reads/writes the settings shape.
  const SETTINGS = {
    read(s) {
      const m = s && s.memory;
      return { serverOn: !!m && typeof m === 'object',                   // GW_MEMORY_ENABLED=false → no memory block at all
        enabled: m?.enabled !== false, readOnly: s?.system?.memory_read_only === true };
    },
    patch: on => ({ memory: { enabled: !!on } })
  };
  // Error code from either body format: {error_code} (4xx) or legacy gateway {error:{code}} (500/503, §3.9.8).
  // api() already merges both into e.code; the raw-body fallback keeps this file correct on its own.
  function codeOf(e) {
    if (!e) return '';
    if (e.code) return String(e.code);
    try { const j = JSON.parse(e.body || ''); return String(j.error_code || j.error?.code || ''); } catch { return ''; }
  }
  // → 'network' | 'off' (server kill switch: bare 404, feature unavailable, not an error) | 'kill_switch' | 'read_only'
  //   | 'internal' | 'not_found' | 'conflict' | 'item_gone' | 'secret_detected' | 'cap_exceeded' | 'invalid'
  function errState(e) {
    if (!e || !e.http) return 'network';
    const c = codeOf(e);
    if (c === 'memory_read_only') return 'read_only';
    if (c === 'kill_switch') return 'kill_switch';
    if (c === 'internal_error') return 'internal';
    if (['not_found', 'conflict', 'item_gone', 'secret_detected', 'cap_exceeded'].includes(c)) return c;
    if (e.http === 404) return 'off';                                    // route absent (byte-identical legacy 404)
    if (e.http >= 500) return 'internal';
    return 'invalid';                                                     // unknown code → invalid text
  }
  function make(api) {
    const call = (name, arg, body, extra) => { const e = ENDPOINTS[name]; return api(e.path(arg), Object.assign({ method: e.method }, body === undefined ? {} : { body: JSON.stringify(body) }, extra || {})); };
    return {
      getSettings: () => call('getSettings').then(SETTINGS.read),
      setEnabled: on => call('patchSettings', null, SETTINGS.patch(on)),
      list: () => call('list').then(FIELDS.list),
      exportAll: () => call('exportAll'),
      add: (kind, text) => call('addItem', null, FIELDS.add(kind, text)).then(FIELDS.item),
      edit: (it, text) => call('editItem', it.id, FIELDS.edit(it, text)).then(FIELDS.item),
      deleteItem: (id, keepalive) => call('deleteItem', id, undefined, keepalive ? { keepalive: true } : null),
      deleteAll: () => call('deleteAll')
    };
  }
  self.EveMemoryAPI = { make, ENDPOINTS, FIELDS, SETTINGS, codeOf, errState };
})();
