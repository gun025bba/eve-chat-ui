/* Eve service worker — network-first HTML, immutable versioned assets, network-only API */
const CACHE = 'llmchat-1.10.0';
const VER = CACHE.slice('llmchat-'.length);
// 1.5.1: versioned asset URLs (same ?v= as index.html) + cache:'reload' so precache never comes from the HTTP cache
const ASSETS = ['app.js', 'today.js', 'shell.js', 'proactive-api.js', 'pim.js', 'proactive.js', 'briefing.js', 'memory-api.js', 'memory.js', 'styles.css'].map(f => `${f}?v=${VER}`);
const SHELL = ['index.html', ...ASSETS, 'manifest.webmanifest', 'offline.html', 'offline.css?v=16', 'offline.js?v=16',
  'favicon.ico', 'favicon.svg', 'icons/favicon-16.png', 'icons/favicon-32.png', 'icons/apple-touch-icon.png', 'apple-touch-icon.png', 'apple-touch-icon-precomposed.png', 'icons/icon-192.png', 'icons/icon-512.png',
  'icons/icon-maskable-192.png', 'icons/icon-maskable-512.png', 'icons/shortcut-new.png', 'icons/mark-dark.svg', 'icons/mark-light.svg'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL.map(u => new Request(u, { cache: 'reload' })))));
  self.skipWaiting();   // v11: activate updates immediately; the page reloads once on controllerchange
});
self.addEventListener('message', e => { if (e.data === 'SKIP_WAITING') self.skipWaiting(); else if (e.data === 'GET_VERSION' && e.ports && e.ports[0]) e.ports[0].postMessage({ version: CACHE }); });
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith('llmchat-') && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request, u = new URL(req.url);
  if (req.method !== 'GET' || u.origin !== location.origin) return;
  if (u.pathname.includes('/v1/')) return;                 // API: network-only, never cached
  const scope = new URL(self.registration.scope).pathname;
  if (!u.pathname.startsWith(scope)) return;

  const isRoot = u.pathname === scope || u.pathname === scope + 'index.html';
  if (req.mode === 'navigate' || isRoot) {                  // 1.5.1: HTML is network-first (bypassing the HTTP cache); cache only offline
    e.respondWith((async () => {
      const c = await caches.open(CACHE);
      try { const r = await fetch(req, { cache: 'no-store' }); if (r.ok && isRoot) c.put('index.html', r.clone()); return r; }
      catch { return (isRoot ? await c.match('index.html') : await c.match(req, { ignoreSearch: true })) || (await c.match('offline.html')) || Response.error(); }
    })());
    return;
  }
  // 1.5.1: versioned (?v=) assets are immutable → exact-URL cache-first (never ignoreSearch, so an old ?v= can't satisfy a new one);
  // unversioned static → network-first with cache fallback
  e.respondWith((async () => {
    const c = await caches.open(CACHE);
    if (u.searchParams.has('v')) {
      const hit = await c.match(req); if (hit) return hit;
      const r = await fetch(req, { cache: 'reload' }); if (r.ok) c.put(req, r.clone()); return r;
    }
    try { const r = await fetch(req, { cache: 'no-cache' }); if (r.ok) c.put(req, r.clone()); return r; }
    catch { return (await c.match(req)) || Response.error(); }
  })());
});

/* 선톡 Web Push (design §2.4): the payload is never displayed. Only {v:1,type,nid} is accepted, and only nid is kept
 * (to open the right thread). The notification text is fixed so lock-screen previews never show message content. */
const NID = /^[0-9A-HJKMNP-TV-Z]{26}$/, PUSH_TYPES = ['proactive'];
function pushNid(e) {
  try {
    const d = e.data && e.data.json();
    if (!d || typeof d !== 'object' || Object.keys(d).length !== 3 || d.v !== 1 || !PUSH_TYPES.includes(d.type) || !NID.test(d.nid)) return null;
    return d.nid;
  } catch { return null; }
}
self.addEventListener('push', e => {
  const nid = pushNid(e);   // always show a notification: Safari revokes permission after silent pushes
  e.waitUntil(self.registration.showNotification('Eve', { body: 'Eve에게서 새 메시지가 있어요', tag: 'eve-proactive', icon: 'icons/icon-192.png', data: { nid } }));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const nid = e.notification.data && NID.test(e.notification.data.nid || '') ? e.notification.data.nid : null;
  e.waitUntil((async () => {
    const scope = self.registration.scope;
    const cs = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const c = cs.find(x => x.url.startsWith(scope));
    if (c) { if (nid) c.postMessage({ type: 'eve-open', nid }); return c.focus(); }
    return self.clients.openWindow(scope + (nid ? '?nid=' + nid : ''));
  })());
});
