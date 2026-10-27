/* Eve iOS shell bridge v1 (eve-serving #64 docs/architecture/ios-shell.md §3; eve-ios shell-v0.1.0 README).
   Web → shell: window.webkit.messageHandlers.eve.postMessage({v:1,id,type,payload}); shell → web: window.__eveShell.receive(msg).
   No handler, or a capabilities.bridge major ≠ ours → plain PWA (bridge unused). No secrets, tokens or cookies cross the bridge. */
(() => {
  'use strict';
  const BRIDGE = '1.0.0', MAJOR = 1;
  const h = (() => { try { return window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.eve; } catch { return null; } })();
  const st = { present: !!(h && typeof h.postMessage === 'function'), active: false, bridge: '', shell: '', features: [] };
  const uuid = () => (self.crypto && crypto.randomUUID) ? crypto.randomUUID() : 'x' + Date.now().toString(36) + Math.random().toString(36).slice(2);
  function post(type, payload) {
    if (!st.present) return false;
    try { h.postMessage({ v: 1, id: uuid(), type, payload: payload || {} }); return true; } catch { return false; }
  }
  const majorOf = v => { const m = /^(\d+)\./.exec(String(v || '')); return m ? +m[1] : NaN; };
  // DELETE /v1/session (eve-serving #65): revoke this browser session server-side, then let the shell wipe website data.
  async function logout() {
    try { await fetch('/v1/session', { method: 'DELETE', cache: 'no-store', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-Eve-Request': '1' } }); } catch {}
    try { localStorage.removeItem('eve.paired'); } catch {}
  }
  function receive(m) {
    try {
      if (!m || typeof m !== 'object' || m.v !== 1) return;
      if (m.type === 'capabilities') {
        const p = m.payload || {};
        st.active = majorOf(p.bridge) === MAJOR;
        st.bridge = String(p.bridge || ''); st.shell = String(p.shell || '');
        st.features = st.active && Array.isArray(p.features) ? p.features.filter(x => typeof x === 'string') : [];
        document.documentElement.classList.toggle('in-shell', st.active);
        return;
      }
      if (m.type === 'logout_requested') {   // shell clears website data ~2s later: call logout right away
        logout().then(() => { if (st.active && st.features.includes('unpair')) post('unpair'); });
        return;
      }
      // replies ({re, ok}) and unknown types: ignore, never throw
    } catch {}
  }
  Object.defineProperty(window, '__eveShell', { value: Object.freeze({ receive }), configurable: false, writable: false });
  const api = {
    state: () => ({ present: st.present, active: st.active, bridge: st.bridge, shell: st.shell, features: st.features.slice() }),
    has: f => st.active && st.features.includes(f),
    haptic(style) { return api.has('haptics') && post('haptics', { style: style === 'light' || style === 'heavy' ? style : 'medium' }); },
    logout
  };
  self.EveShell = Object.freeze(api);
  if (st.present) post('hello', { bridge: BRIDGE });
})();
