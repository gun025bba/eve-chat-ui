/* Eve service worker — app shell precache, SWR static, network-only API */
const CACHE = 'llmchat-v15';
const SHELL = ['./', 'index.html', 'app.js', 'styles.css', 'manifest.webmanifest', 'offline.html', 'offline.css', 'offline.js',
  'favicon.ico', 'favicon.svg', 'icons/favicon-16.png', 'icons/favicon-32.png', 'icons/apple-touch-icon.png', 'apple-touch-icon.png', 'apple-touch-icon-precomposed.png', 'icons/icon-192.png', 'icons/icon-512.png',
  'icons/icon-maskable-192.png', 'icons/icon-maskable-512.png', 'icons/shortcut-new.png', 'icons/mark-dark.svg', 'icons/mark-light.svg'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
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

  if (req.mode === 'navigate') {                             // app shell: SWR on index, offline page as last resort
    e.respondWith((async () => {
      const c = await caches.open(CACHE);
      const isRoot = u.pathname === scope || u.pathname === scope + 'index.html';
      const cached = isRoot ? (await c.match('./') || await c.match('index.html')) : await c.match(req, { ignoreSearch: true });
      const net = fetch(req).then(r => { if (r.ok && isRoot) c.put('./', r.clone()); return r; });
      if (cached) { e.waitUntil(net.catch(() => {})); return cached; }
      try { return await net; } catch { return (await c.match('offline.html')) || Response.error(); }
    })());
    return;
  }
  // static: stale-while-revalidate
  e.respondWith((async () => {
    const c = await caches.open(CACHE);
    const cached = await c.match(req, { ignoreSearch: true });
    const net = fetch(req).then(r => { if (r.ok) c.put(req, r.clone()); return r; });
    if (cached) { e.waitUntil(net.catch(() => {})); return cached; }
    return net;
  })());
});
