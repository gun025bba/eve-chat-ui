// node tests/sw_push.js — sw.js push/notificationclick: strict payload schema, fixed text only
const fs = require('fs'), vm = require('vm');
const H = {}, shown = [], posted = [], opened = []; let R = [];
const check = (n, ok, x = '') => { R.push(!!ok); console.log((ok ? 'PASS ' : 'FAIL ') + n, x); };
const clientsList = [];
const self = { addEventListener: (t, f) => { H[t] = f; }, registration: { scope: 'https://app.example/ui/', showNotification: (t, o) => { shown.push([t, o]); return Promise.resolve(); } },
  clients: { matchAll: async () => clientsList, openWindow: async u => { opened.push(u); } }, skipWaiting() {}, location: { origin: 'https://app.example' } };
vm.runInNewContext(fs.readFileSync(__dirname + '/../sw.js', 'utf8'), { self, caches: {}, fetch() {}, URL, Response: function () {}, console, Promise, clients: self.clients, registration: self.registration, location: self.location });
const push = async d => { const ps = []; shown.length = 0; H.push({ data: d === undefined ? null : { json: () => { if (typeof d === 'string') throw 0; return d; }, text: () => String(d) }, waitUntil: p => ps.push(p) }); await Promise.all(ps); return shown.slice(); };
(async () => {
  const NID = '01JABCDEFGHJKMNPQRSTVWXYZ0';
  let s = await push({ v: 1, type: 'proactive', nid: NID });
  check('valid payload → fixed notification', s.length === 1 && s[0][0] === 'Eve' && s[0][1].body === 'Eve에게서 새 메시지가 있어요' && s[0][1].data.nid === NID, JSON.stringify(s));
  s = await push({ v: 1, type: 'proactive', nid: NID, body: '비밀 내용' });
  check('extra keys: content never shown', s.every(x => !JSON.stringify(x).includes('비밀')), JSON.stringify(s));
  for (const bad of [{ v: 2, type: 'proactive', nid: NID }, { v: 1, type: 'x', nid: NID }, { v: 1, type: 'proactive', nid: '../x' }, 'garbage', undefined]) {
    s = await push(bad); check('bad payload → no nid leaks ' + JSON.stringify(bad), s.every(x => x[1].body === 'Eve에게서 새 메시지가 있어요' && !(x[1].data && x[1].data.nid && x[1].data.nid !== NID)), JSON.stringify(s));
  }
  const ps = []; H.notificationclick({ notification: { data: { nid: NID }, close() {} }, waitUntil: p => ps.push(p) }); await Promise.all(ps);
  check('click without client → openWindow(scope?nid=)', opened[0] === 'https://app.example/ui/?nid=' + NID, opened);
  console.log(R.every(Boolean) ? 'ALL PASS' : 'SOME FAIL'); process.exit(R.every(Boolean) ? 0 : 1);
})();
