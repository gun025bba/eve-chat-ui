/* Eve memory (Part B) — API layer + field mapping. The ONLY file that knows memory endpoint paths and
 * server field names (eve-serving docs/architecture/memory.md §4, ui-api-contract.md §1 Q7/Q8/Q17, §2, §3.3).
 * The schemas are not final: if the backend renames anything, edit ENDPOINTS / FIELDS here only.
 * status: 'defined' = in the contract docs; 'assumed' = UI guess, listed in README "메모리 API 가정". */
(function () {
  const E = encodeURIComponent;
  const ENDPOINTS = {
    getSettings:  { status: 'defined', method: 'GET',    path: () => '/v1/settings' },               // CT §2: {memory:{enabled}, system:{memory_read_only,…}}
    patchSettings:{ status: 'defined', method: 'PATCH',  path: () => '/v1/settings' },               // body {memory:{enabled:bool}} only (strict decode)
    list:         { status: 'defined', method: 'GET',    path: () => '/v1/memory' },                  // MEM §4; response shape assumed (see FIELDS.list)
    deleteItem:   { status: 'defined', method: 'DELETE', path: id => `/v1/memory/items/${E(id)}` }    // MEM §4; 204 assumed, 404 = already gone
  };
  const S = v => (typeof v === 'string' ? v : null);
  const KINDS = ['profile', 'preference', 'fact', 'task'];
  const FIELDS = {
    // assumed: GET /v1/memory returns the file document {items:[…]} (MEM §1); {data:[…]} also accepted
    list(j) { const arr = Array.isArray(j?.items) ? j.items : Array.isArray(j?.data) ? j.data : []; return arr.map(FIELDS.item).filter(x => x.id); },
    item: i => ({ id: i && i.id != null ? String(i.id) : null, kind: KINDS.includes(i?.kind) ? i.kind : 'fact', text: S(i?.text) || '', pinned: i?.pinned === true,
      confidence: i?.confidence === 'confirmed' ? 'confirmed' : 'user', updatedAt: Date.parse(i?.updated_at || '') || 0, expiresAt: Date.parse(i?.expires_at || '') || 0 }),
    settings(s) {
      const y = (s && s.system) || {};
      return { enabled: s?.memory?.enabled !== false,                // CT §2 default true
        readOnly: y.memory_read_only === true,                         // CT Q17
        available: y.memory_available !== false };                     // assumed key (kill switch GW_MEMORY_ENABLED); absent → available
    },
    patch: on => ({ memory: { enabled: !!on } })
  };
  // error → UI state (CT §3.3). Branch on the body error_code, then HTTP.
  function errState(e) {
    if (!e || !e.http) return 'network';
    if (e.code === 'memory_read_only' || e.http === 503) return 'read_only';
    if (e.code === 'kill_switch' || e.http === 404 || e.http === 405 || e.http === 501) return 'unavailable';
    if (e.code === 'not_found') return 'not_found';
    return 'error';
  }
  function make(api) {
    const call = (name, arg, body) => { const e = ENDPOINTS[name]; return api(e.path(arg), body === undefined ? { method: e.method } : { method: e.method, body: JSON.stringify(body) }); };
    return {
      getSettings: () => call('getSettings'),
      setEnabled: on => call('patchSettings', null, FIELDS.patch(on)),
      list: () => call('list').then(FIELDS.list),
      deleteItem: id => call('deleteItem', id)            // api() adds X-Eve-Request (CSRF) + JSON Content-Type
    };
  }
  self.EveMemoryAPI = { make, ENDPOINTS, FIELDS, errState };
})();
