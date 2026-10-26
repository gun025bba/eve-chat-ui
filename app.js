'use strict';
const COPY_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/></svg>';
/* ---------- pure helpers (also tested in node) ---------- */
function createSSEParser(onData) {
  let buf = '';
  return {
    push(chunk) {
      buf += chunk;
      let idx;
      while ((idx = buf.search(/\r?\n\r?\n/)) !== -1) {
        const block = buf.slice(0, idx);
        buf = buf.slice(idx).replace(/^\r?\n\r?\n/, '');
        const data = block.split(/\r?\n/).filter(l => l.startsWith('data:')).map(l => l.slice(5).replace(/^ /, '')).join('\n');
        if (data) onData(data);
      }
    },
    flush() { if (buf.trim()) { const b = buf; buf = ''; this.push(b + '\n\n'); } }
  };
}
// Split "<think>...</think>answer" (think may be unterminated while streaming)
function splitThink(text) {
  const m = text.match(/^\s*<think>([\s\S]*?)(<\/think>|$)([\s\S]*)$/);
  if (!m) return { think: null, answer: text, thinking: false };
  return { think: m[1].trim(), answer: m[3].replace(/^\s+/, ''), thinking: m[2] === '' };
}
const STOP_RE = /\n*\*\(중지됨\)\*\s*$/;
function stripStopMark(s) { return String(s || '').replace(STOP_RE, ''); }
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function inlineMd(s) { // s already escaped; code spans are protected from emphasis
  const codes = [];
  s = s.replace(/`([^`\n]+)`/g, (_, c) => `\u0000${codes.push(c) - 1}\u0000`);
  s = s
    .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g, (_, alt, u) => `<a class="img-link" href="${u}" target="_blank" rel="noopener noreferrer">${alt || '이미지'}</a>`)
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  if (_cites) s = s.replace(/\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\](?!\()/g, (all, list) => {
    const ns = list.split(',').map(x => +x.trim()); if (!ns.every(n => _cites.has(n))) return all;
    return ns.map(n => { const c = _cites.get(n); return `<sup class="cite"><a href="${escapeHtml(c.url)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(c.title || c.domain || '')}" aria-label="출처 ${n}">${n}</a></sup>`; }).join('');
  });
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[i]}</code>`);
}
// Index where the "stable" (completed) markdown ends: last blank line outside any code fence.
// v16 block parser: lists survive blank lines (loose), indented continuations and nesting; <ol start> keeps source numbers
const MD_LI = /^( *)([-*+]|\d{1,9}[.)])\s+(.*)$/;
const mdInd = l => l.match(/^ */)[0].length;
function mdBlocks(lines) {
  const out = []; let para = [], i = 0;
  const flushP = () => { if (para.length) { out.push('<p>' + inlineMd(para.join('<br>')) + '</p>'); para = []; } };
  while (i < lines.length) {
    const line = lines[i]; let m;
    if (!line.trim()) { flushP(); i++; continue; }
    if ((m = line.match(/^(#{1,6})\s+(.*)/))) { flushP(); const n = Math.min(m[1].length + 2, 6); out.push(`<h${n}>${inlineMd(m[2])}</h${n}>`); i++; continue; }
    if ((m = line.match(MD_LI)) && m[1].length < 4) { flushP(); i = mdList(lines, i, out); continue; }
    para.push(line.trim() ? line.replace(/^ +/, '') : line); i++;
  }
  flushP();
  return out.join('');
}
function mdList(lines, i, out) {
  const m0 = lines[i].match(MD_LI), base = m0[1].length, ol = /\d/.test(m0[2]), t = ol ? 'ol' : 'ul';
  const same = l => { const m = l.match(MD_LI); return m && m[1].length <= base + 1 && /\d/.test(m[2]) === ol ? m : null; };
  const items = [];
  while (i < lines.length) {
    const mm = same(lines[i]); if (!mm) break;
    const ci = mm[1].length + mm[2].length + 1, body = [mm[3]]; i++;
    let next = false;
    while (i < lines.length) {
      const l = lines[i];
      if (!l.trim()) {
        let j = i; while (j < lines.length && !lines[j].trim()) j++;
        if (j >= lines.length) { i = j; break; }
        if (mdInd(lines[j]) >= base + 2 && !same(lines[j])) { for (; i < j; i++) body.push(''); continue; }
        if (same(lines[j])) { i = j; next = true; }
        break;
      }
      if (same(l)) { next = true; break; }
      const ind = mdInd(l);
      if (ind >= base + 2) { body.push(l.slice(Math.min(ind, ci))); i++; continue; }
      if (MD_LI.test(l) || /^#{1,6}\s/.test(l) || !body[body.length - 1]) break;
      body.push(l); i++; // lazy continuation
    }
    items.push(mdBlocks(body).replace(/^<p>([\s\S]*?)<\/p>/, '$1'));
    if (!next) break;
  }
  const start = ol ? parseInt(m0[2], 10) : 1;
  out.push(`<${t}${ol && start !== 1 ? ` start="${start}"` : ''}>` + items.map(x => '<li>' + x + '</li>').join('') + `</${t}>`);
  return i;
}
// streaming cut: never inside a code fence, never right after a list block (a later item may still join it)
function stableCut(s) {
  let i = s.length;
  while ((i = s.lastIndexOf('\n\n', i - 1)) >= 0) {
    const fences = (s.slice(0, i).match(/```/g) || []).length;
    if (fences % 2 === 0 && !mdAfterList(s.slice(0, i))) return i + 2;
    if (i === 0) break;
  }
  return 0;
}
function mdAfterList(head) {
  const lines = head.replace(/\t/g, '    ').split('\n');
  let k = lines.length - 1; while (k >= 0 && !lines[k].trim()) k--;
  for (; k >= 0; k--) { // walk up the current block run; any list item or indented line => list may continue
    const l = lines[k];
    if (!l.trim()) { let j = k; while (j >= 0 && !lines[j].trim()) j--; if (j < 0) return false; const p = lines[j]; if (MD_LI.test(p) || mdInd(p) >= 2) { k = j + 1; continue; } return false; }
    if (MD_LI.test(l) || mdInd(l) >= 2) return true;
    if (l.includes('```')) return false;
  }
  return false;
}
// [n] citation map for the current renderMarkdown call (web search sources; http/https only)
let _cites = null;
function safeUrl(u) { try { const x = new URL(u); return x.protocol === 'http:' || x.protocol === 'https:' ? x.href : ''; } catch { return ''; } }
function citeMap(sources) {
  if (!Array.isArray(sources) || !sources.length) return null;
  const m = new Map(); sources.forEach(c => { const url = c && safeUrl(c.url); if (url && Number.isFinite(+c.n)) m.set(+c.n, { url, title: c.title || '', domain: c.domain || '' }); });
  return m.size ? m : null;
}
function srcDomain(c) { if (c.domain) return c.domain; try { return new URL(c.url).hostname.replace(/^www\./, ''); } catch { return ''; } }
function renderSources(sources) {
  const m = citeMap(sources); if (!m) return '';
  const items = [...m.entries()].sort((a, b) => a[0] - b[0]).map(([n, c]) => { const d = srcDomain(c);
    return `<li><a href="${escapeHtml(c.url)}" target="_blank" rel="noopener noreferrer"><span class="sn">${n}</span><span class="st">${escapeHtml(c.title || d || c.url)}</span><span class="sd">${escapeHtml(d)}</span></a></li>`; }).join('');
  return `<section class="sources" aria-label="출처"><h4>출처</h4><ol>${items}</ol></section>`;
}
function renderMarkdown(src, sources) {
  _cites = citeMap(sources);
  try { return renderMd(src); } finally { _cites = null; }
}
function renderMd(src) {
  const out = [];
  const parts = src.split(/```/);
  parts.forEach((part, i) => {
    if (i % 2 === 1) { // code
      const nl = part.indexOf('\n');
      const lang = nl >= 0 ? part.slice(0, nl).trim() : '';
      const code = nl >= 0 ? part.slice(nl + 1) : part;
      out.push(`<div class="codeblock"><div class="code-head"><span class="lang">${escapeHtml(lang || 'code')}</span><button class="copy" type="button" aria-label="코드 복사">${COPY_SVG}<span>복사</span></button></div><pre><code data-lang="${escapeHtml(lang)}">${escapeHtml(code.replace(/\n$/, ''))}</code></pre></div>`);
      return;
    }
    out.push(mdBlocks(escapeHtml(part).replace(/\t/g, '    ').split('\n')));
  });
  return out.join('');
}
if (typeof module !== 'undefined') module.exports = { createSSEParser, splitThink, renderMarkdown, renderSources, escapeHtml, stableCut, stripStopMark };

/* ---------- app ---------- */
if (typeof document !== 'undefined') (function () {
  const $ = s => document.querySelector(s);
  const svg = d => `<svg viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
  const ICON = {
    copy: COPY_SVG,
    globe: svg('<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z"/>'),
    check: svg('<path d="M5 12l5 5 9-10"/>'),
    regen: svg('<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>'),
    warn: svg('<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16.5v.01"/>'),
    chev: '<svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>',
    spark: svg('<path d="M12 3l1.9 5.6 5.6 1.9-5.6 1.9L12 18l-1.9-5.6-5.6-1.9 5.6-1.9Z"/>'),
    edit: svg('<path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>'),
    up: svg('<path d="M7 10v10H4V10zM7 10l4-7a2 2 0 0 1 2 2v4h5.5a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 17.3 20H7"/>'),
    down: svg('<path d="M7 14V4H4v10zM7 14l4 7a2 2 0 0 0 2-2v-4h5.5a2 2 0 0 0 2-2.3l-1.2-7A2 2 0 0 0 17.3 4H7"/>'),
    trash: svg('<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>')
  };
  const LS = { settings: 'llmchat.settings', convs: 'llmchat.convs', current: 'llmchat.current', route: 'llmchat.route', scroll: 'llmchat.scroll', draft: 'llmchat.draft:',
    mode: 'llmchat.mode', srv: 'llmchat.srvcache', pins: 'llmchat.pins', outbox: 'llmchat.outbox', migrated: 'llmchat.migrated', snooze: 'llmchat.migrateSnooze', bak: 'llmchat.convs.bak', fbSkip: 'llmchat.fbSkip' };
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } };
  const save = (k, v) => localStorage.setItem(k, JSON.stringify(v));

  const DEFAULT_MODEL = 'mlx-community/Qwen3-30B-A3B-4bit';
  let settings = Object.assign({ base: '', model: DEFAULT_MODEL, system: '', showThink: false, noThink: false }, load(LS.settings, {}));
  // Tailscale identity auth: the browser never holds an API key. Drop any legacy key and
  // any Base URL override pointing at the old :8000 port or a raw IP (default = same origin).
  {
    const legacyBase = b => /:8000(\/|$)/.test(b || '') || /^https?:\/\/(\d{1,3}\.){3}\d{1,3}(:|\/|$)/.test(b || '') || /^https?:\/\/\[/.test(b || '');
    let dirty = 'key' in settings; delete settings.key;
    if (settings.base && legacyBase(settings.base)) { settings.base = ''; dirty = true; }
    if (dirty) save(LS.settings, settings);
    ['llmchat.key', 'apiKey', 'api_key'].forEach(k => localStorage.removeItem(k));
  }
  // Storage mode: 'server' = threads API (GET /v1/threads ok), 'local' = this device only (503 persistence_disabled / no API).
  let mode = load(LS.mode, 'local') === 'server' ? 'server' : 'local';
  let convs = mode === 'server' ? load(LS.srv, []) : load(LS.convs, []);
  let archivedList = [];            // archive screen contents
  let nextCursor = null, threadsLoading = false, persistOff = false;
  let currentId = load(LS.current, null);
  let controller = null;

  const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  const cur = () => convs.find(c => c.id === currentId) || archivedList.find(c => c.id === currentId);
  const persist = () => { try { save(mode === 'server' ? LS.srv : LS.convs, convs); } catch {} save(LS.current, currentId); };
  const normBase = b => (b || '').trim().replace(/\/+$/, '').replace(/\/v1$/, ''); // '' => relative /v1/... (same origin)
  const apiBase = () => normBase(settings.base);
  const MUTATING = /^(POST|PUT|PATCH|DELETE)$/i;
  const headers = (method = 'GET') => ({ 'Content-Type': 'application/json', ...(MUTATING.test(method) ? { 'X-Eve-Request': '1' } : {}) });  // X-Eve-Request: server CSRF check on mutating requests   // no Authorization: gateway trusts Tailscale identity
  let whoami = null;
  const shortModel = () => (settings.model || '').split('/').pop();
  const isTouch = matchMedia('(pointer:coarse)').matches;
  const box = $('#messages'), input = $('#input'), sendBtn = $('#sendBtn');
  /* web search toggle (persisted; on => web_search:'auto') */
  const webBtn = $('#webBtn'), LS_WEB = 'llmchat.webSearch';
  const webOn = () => localStorage.getItem(LS_WEB) === '1';
  function setWebOn(on) { if (on) localStorage.setItem(LS_WEB, '1'); else localStorage.removeItem(LS_WEB); webBtn.setAttribute('aria-pressed', String(on)); webBtn.classList.toggle('on', on); webBtn.title = on ? '웹 검색 켜짐' : '웹 검색 꺼짐'; }
  setWebOn(webOn());
  webBtn.addEventListener('click', () => { const on = !webOn(); setWebOn(on); if (navigator.vibrate) try { navigator.vibrate(8); } catch {} showToast(on ? '웹 검색 켜짐 · 필요할 때 검색해요' : '웹 검색 꺼짐', '', null, 1400); });

  /* ---------- viewport / keyboard (NATIVE §9) ---------- */
  const root = document.documentElement.style;
  const vv = window.visualViewport;
  let vvRaf = 0;
  function syncVV() {
    if (vvRaf) return;
    vvRaf = requestAnimationFrame(() => {
      vvRaf = 0; const h = vv ? vv.height : window.innerHeight;
      root.setProperty('--vvh', h + 'px');
      const wasKb = document.body.classList.contains('kb-open'), kb = window.innerHeight - h > 120;
      document.body.classList.toggle('kb-open', kb);
      if (kb && !wasKb && document.activeElement?.classList.contains('fbp-input')) document.activeElement.scrollIntoView({ block: 'nearest' });   // N2: keep note above keyboard
      if (window.scrollY) window.scrollTo(0, 0);
      if (stick) scrollBottom();
    });
  }
  if (vv) { vv.addEventListener('resize', syncVV); vv.addEventListener('scroll', () => { if (window.scrollY) window.scrollTo(0, 0); syncVV(); }); }
  window.addEventListener('resize', syncVV);
  input.addEventListener('focus', () => { stick = true; setTimeout(() => { window.scrollTo(0, 0); scrollBottom(); }, 50); setTimeout(() => { if (stick) scrollBottom(); }, 400); });
  input.addEventListener('blur', () => setTimeout(syncVV, 60));
  if ('ResizeObserver' in window) new ResizeObserver(() => root.setProperty('--composer-h', $('#composer').offsetHeight + 'px')).observe($('#composer'));
  document.addEventListener('touchstart', () => {}, { passive: true }); // enables :active on iOS

  /* ---------- environment ---------- */
  const isStandalone = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  const isIOS = /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  document.documentElement.classList.toggle('standalone', isStandalone());
  document.documentElement.classList.toggle('ios', isIOS);
  const buzz = n => { if (!isIOS && navigator.vibrate) try { navigator.vibrate(n); } catch {} };
  const wide = matchMedia('(min-width: 761px)');
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');

  /* ---------- scroll ---------- */
  let stick = true;
  function scrollBottom(smooth) { box.scrollTo({ top: box.scrollHeight, behavior: smooth ? 'smooth' : 'auto' }); }
  box.addEventListener('scroll', () => {
    const d = box.scrollHeight - box.scrollTop - box.clientHeight;
    stick = d < 80;
    $('#toBottom').classList.toggle('show', d > 200);
    $('#topbar').classList.toggle('scrolled', box.scrollTop > 4);
    if (box.scrollTop < 200) loadOlder();
  }, { passive: true });
  $('#toBottom').onclick = () => { stick = true; scrollBottom(true); };
  syncVV();

  /* ---------- server API (threads, THREADS-SPEC §0 / backend contract) ---------- */
  async function api(path, opts = {}) {
    const r = await fetch(apiBase() + path, { cache: 'no-store', ...opts, headers: { ...headers(opts.method), ...(opts.headers || {}) } });
    if (r.status === 204) return null;
    const t = await r.text(); let j = null; try { j = JSON.parse(t); } catch {}
    if (!r.ok) {
      const code = j?.error?.code;
      if (r.status === 401) showAuthNotice(null, code);
      throw Object.assign(new Error(errMsg(r.status, t)), { http: r.status, code });
    }
    return j;
  }
  const isNet = e => !e.http;                       // fetch failed: offline / unreachable
  const toMs = t => { const v = Date.parse(t || ''); return isNaN(v) ? Date.now() : v; };
  const pinSet = () => new Set(load(LS.pins, []));
  function fromServerMsg(m) {
    let content = m.reasoning ? `<think>${m.reasoning}</think>${m.content || ''}` : (m.content || '');
    const o = { id: m.id, role: m.role, content, feedback: m.feedback?.rating || null, fbReasons: Array.isArray(m.feedback?.reasons) ? m.feedback.reasons : [], fbComment: m.feedback?.comment || '', status: m.status || 'complete', created: toMs(m.created_at) };
    const srcs = m.sources || m.metadata?.sources; if (Array.isArray(srcs) && srcs.length) o.sources = srcs;
    if (m.usage) { o.usage = m.usage; o.usageText = usageText(m.usage, m.latency_ms ? m.latency_ms / 1000 : 0); }
    return o;
  }
  function fromServerThread(t, old) {
    const updated = toMs(t.updated_at);
    return { id: t.id, srv: true, title: t.title || '새 대화', updated, created: toMs(t.created_at), archived: !!t.archived,
      preview: t.last_message_preview || '', count: t.message_count || 0, pinned: pinSet().has(t.id),
      messages: old?.messages || [], hasMore: !!old?.hasMore, loaded: !!old?.loaded && old.updated === updated };
  }
  async function initServer() {
    try {
      const j = await api('/v1/threads?limit=20&archived=false');
      const prev = mode === 'server' ? convs : [];
      const wasLocal = mode !== 'server';
      mode = 'server'; save(LS.mode, 'server'); persistOff = false;
      const mapped = (j.data || []).map(t => fromServerThread(t, prev.find(p => p.id === t.id)));
      convs = prev.filter(c => c.fresh).concat(mapped); nextCursor = j.next_cursor || null;
      if (wasLocal || (currentId && !cur())) currentId = cur() ? currentId : null;
      persist(); renderAll(); loadDraft();
      if (cur()) ensureMessages(cur());
      maybeMigrate(); flushOutbox(); fillListIfShort();
    } catch (e) {
      if (e.code === 'persistence_disabled' || e.http === 404 || (e.http === 503 && !e.code)) {
        persistOff = true;
        if (mode === 'server') { mode = 'local'; convs = load(LS.convs, []); if (!cur()) currentId = convs[0]?.id || null; renderAll(); loadDraft(); }
        save(LS.mode, 'local');
      }
      renderSync();
    }
  }
  async function loadMoreThreads() {
    if (mode !== 'server' || !nextCursor || threadsLoading || listQuery()) return;
    threadsLoading = true; renderList();
    try {
      const j = await api('/v1/threads?limit=20&archived=false&cursor=' + encodeURIComponent(nextCursor));
      (j.data || []).forEach(t => { if (!convs.some(c => c.id === t.id)) convs.push(fromServerThread(t)); });
      nextCursor = j.next_cursor || null; persist();
    } catch {} finally { threadsLoading = false; renderList(); fillListIfShort(); }
  }
  function fillListIfShort() { requestAnimationFrame(() => { if (nextCursor && scroller.scrollHeight - scroller.clientHeight < 400) loadMoreThreads(); }); }
  async function ensureMessages(c) {
    if (mode !== 'server' || !c || !c.srv || c.fresh || c.loaded || c.loading) return;
    c.loading = true; if (c === cur() && !c.messages.length) box.innerHTML = '<div class="older loading"><span class="spin"></span></div>';
    try {
      const j = await api(`/v1/threads/${encodeURIComponent(c.id)}/messages?limit=50`);
      c.messages = (j.data || []).filter(m => m.role !== 'system').map(fromServerMsg); c.hasMore = !!j.has_more; c.loaded = true; persist();
    } catch (e) { if (!c.messages.length && c === cur()) showToast('대화를 불러오지 못했어요', '다시 시도', () => ensureMessages(c), 4000); }
    finally { c.loading = false; if (c === cur()) renderMessages(); }
  }
  async function loadOlder() {
    const c = cur(); if (!c || !c.hasMore || c.loadingOlder || mode !== 'server' || !c.messages[0]?.id) return;
    c.loadingOlder = true;
    try {
      const j = await api(`/v1/threads/${encodeURIComponent(c.id)}/messages?limit=50&before=${encodeURIComponent(c.messages[0].id)}`);
      const older = (j.data || []).filter(m => m.role !== 'system').map(fromServerMsg).filter(m => !c.messages.some(x => x.id === m.id));
      c.messages = older.concat(c.messages); c.hasMore = !!j.has_more;
      if (c === cur()) { const h = box.scrollHeight, top = box.scrollTop; renderMessages(true); box.scrollTop = box.scrollHeight - h + top; }
    } catch {} finally { c.loadingOlder = false; }
  }
  function adoptThreadId(c, id) {
    if (!id || c.id === id) { if (c) c.fresh = false; return; }
    const old = c.id; c.id = id; c.fresh = false; c.srv = true;
    if (currentId === old) { currentId = id; if (app.dataset.route === 'chat') history.replaceState({ route: 'chat', id }, '', '#/c/' + id); }
    if (genId === old) genId = id;
    const d = localStorage.getItem(LS.draft + old); if (d) { localStorage.setItem(LS.draft + id, d); localStorage.removeItem(LS.draft + old); }
    persist();
  }

  /* ---------- outbox (offline-first writes, backoff 2..60s, THREADS-SPEC §0) ---------- */
  let outbox = load(LS.outbox, []), obTimer = 0, obFailed = 0, migrateProg = null;
  const saveOutbox = () => save(LS.outbox, outbox);
  function enqueue(op, key, payload) { outbox = outbox.filter(o => o.key !== key); outbox.push({ op, key, payload, tries: 0, nextAt: 0 }); saveOutbox(); renderSync(); scheduleOutbox(0); }
  function scheduleOutbox(ms) { clearTimeout(obTimer); obTimer = setTimeout(flushOutbox, ms); }
  async function runOp(o) {
    const p = o.payload, id = encodeURIComponent(p.id);
    if (o.op === 'feedback') return p.rating ? api(`/v1/messages/${id}/feedback`, { method: 'PUT', body: JSON.stringify({ rating: p.rating, reasons: p.reasons || [], comment: p.comment || '' }) }) : api(`/v1/messages/${id}/feedback`, { method: 'DELETE' });
    if (o.op === 'patch') return api(`/v1/threads/${id}`, { method: 'PATCH', body: JSON.stringify(p.patch) });
    if (o.op === 'archive') return api(`/v1/threads/${id}`, { method: 'DELETE' });
  }
  async function flushOutbox() {
    if (mode !== 'server' || flushOutbox.busy) return; flushOutbox.busy = true;
    try {
      for (const o of [...outbox]) {
        if (o.nextAt > Date.now()) continue;
        try { await runOp(o); outbox = outbox.filter(x => x !== o); }
        catch (e) {
          if (isNet(e) || e.http >= 500 || e.http === 429) { o.tries++; o.nextAt = Date.now() + Math.min(60, 2 ** o.tries) * 1000; }
          else if (o.op === 'feedback' && e.code === 'feedback_comment_too_long' && o.payload.comment) { o.payload = { ...o.payload, comment: o.payload.comment.trim().slice(0, 139) }; o.tries = 0; o.nextAt = 0; }
          else if (o.op === 'feedback' && e.code === 'invalid_feedback_reason' && o.payload.reasons?.length) { o.payload = { ...o.payload, reasons: [] }; o.tries = 0; o.nextAt = 0; fbReasonRejected(o.payload.id); }
          else { outbox = outbox.filter(x => x !== o); obFailed++; o.onFail?.(); }
        }
      }
    } finally { flushOutbox.busy = false; saveOutbox(); renderSync(); }
    const next = outbox.reduce((m, o) => Math.min(m, o.nextAt), Infinity);
    if (next < Infinity) scheduleOutbox(Math.max(500, next - Date.now()));
  }
  // write now; if offline/5xx keep it queued, if rejected roll back
  async function write(op, key, payload, rollback, failText) {
    if (mode !== 'server') return;
    try { await runOp({ op, payload }); outbox = outbox.filter(o => o.key !== key); saveOutbox(); renderSync(); }
    catch (e) {
      if (isNet(e) || e.http >= 500 || e.http === 429) return enqueue(op, key, payload);
      if (rollback?.(e) === 'handled') return;
      showToast(failText || '저장하지 못했어요', '다시 시도', () => write(op, key, payload, rollback, failText), 4000);
    }
  }
  setInterval(() => { if (outbox.length) flushOutbox(); }, 30000);
  function renderSync() {
    const el = $('#syncStatus'); if (!el) return;
    let html = '';
    if (migrateProg) html = `<span class="spin"></span>대화 옮기는 중 ${migrateProg.done}/${migrateProg.total}`;
    else if (persistOff) html = mode === 'local' ? '서버 저장이 꺼져 있어 이 기기에만 저장돼요' : '서버 저장이 일시적으로 꺼져 있어요';
    else if (obFailed) html = `<i class="dot bad"></i>${obFailed}개 저장 실패 · <button type="button" class="sync-retry">다시 시도</button>`;
    else if (outbox.length) html = `<i class="dot"></i>변경 사항 ${outbox.length}개 대기 중`;
    el.innerHTML = html; el.hidden = !html;
    el.querySelector('.sync-retry')?.addEventListener('click', () => { obFailed = 0; outbox.forEach(o => o.nextAt = 0); flushOutbox(); });
    const ss = $('#sSync'); if (ss) ss.textContent = mode === 'server' ? (outbox.length ? `대기 ${outbox.length}개` : '서버에 저장 중') : '이 기기에만 저장';
  }

  /* ---------- conversation list (NATIVE §3, THREADS-SPEC §2) ---------- */
  const CHEV_R = '<svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>';
  let genId = null;
  const blankConv = () => ({ id: (mode === 'server' ? 'tmp-' : '') + uid(), title: '새 대화', messages: [], updated: Date.now(), fresh: mode === 'server' });
  function newConv() {
    const c0 = cur();
    if (c0 && !c0.messages.length && !controller && !c0.archived) { openConv(c0.id); if (!isTouch) input.focus(); return; } // reuse empty chat
    if (controller) controller.abort();
    saveDraft();
    const c = blankConv();
    convs.unshift(c); currentId = c.id; persist(); input.value = ''; grow(); renderAll(); go('chat'); if (!isTouch) input.focus();
  }
  function openConv(id, from) {
    chatFrom = from || 'list';
    if (id !== currentId) { saveDraft(); currentId = id; persist(); renderAll(); loadDraft(); }
    else renderMessages();
    ensureMessages(cur());
    go('chat');
  }
  function updateThread(c, patch) {
    const before = { title: c.title }; Object.assign(c, patch); persist(); renderList(); if (c === cur()) $('#title').textContent = c.title;
    if (mode === 'server' && !c.fresh) write('patch', 'patch:' + c.id, { id: c.id, patch }, () => { Object.assign(c, before); persist(); renderAll(); }, '이름을 저장하지 못했어요');
  }
  function startRename(row, c) {
    if (!row) return openRenameSheet(c);
    row.classList.add('editing'); closeSwipe();
    const t = row.querySelector('.row-title');
    const inp = Object.assign(document.createElement('input'), { className: 'row-edit', value: c.title, enterKeyHint: 'done' });
    inp.setAttribute('aria-label', '대화 제목'); Object.entries({ autocomplete: 'off', autocorrect: 'on', autocapitalize: 'sentences', 'data-1p-ignore': '', 'data-lpignore': 'true', 'data-form-type': 'other' }).forEach(([k, v]) => inp.setAttribute(k, v)); t.replaceWith(inp); inp.focus(); inp.select();
    inp.scrollIntoView?.({ block: 'center' });
    const done = ok => { inp.onblur = null; const v = inp.value.trim(); row.classList.remove('editing');
      if (ok && v && v !== c.title) updateThread(c, { title: v }); else renderList(); };
    inp.onkeydown = e => { if (e.key === 'Enter' && !e.isComposing && e.keyCode !== 229) { e.preventDefault(); done(true); } if (e.key === 'Escape') done(false); };
    inp.onblur = () => done(true);
    inp.onclick = e => e.stopPropagation();
  }
  const renameConv = c => startRename($(`#convList li.row[data-id="${CSS.escape(c.id)}"]`), c);
  /* archive with 2.8s undo, deferred commit (THREADS-SPEC §2.4) */
  let pendingArchive = null;
  function commitArchive() {
    const p = pendingArchive; if (!p) return; pendingArchive = null; clearTimeout(p.timer);
    if (mode === 'server' && !p.c.fresh) write('archive', 'archive:' + p.c.id, { id: p.c.id }, () => { convs.splice(Math.min(p.idx, convs.length), 0, p.c); p.c.archived = false; persist(); renderList(); }, '보관하지 못했어요');
    else if (mode === 'local') { p.c.archived = true; if (!convs.includes(p.c)) convs.splice(Math.min(p.idx, convs.length), 0, p.c); persist(); }
  }
  function archiveConv(c) {
    if (pendingArchive) commitArchive();
    if (genId === c.id && controller) controller.abort();
    const idx = convs.indexOf(c); if (idx < 0) return;
    convs.splice(idx, 1); c.archived = true;
    if (currentId === c.id) { currentId = convs.find(x => !x.archived)?.id || null; loadDraft(); }
    persist(); renderAll(); buzz(15);
    pendingArchive = { c, idx, timer: setTimeout(() => { hideToast(); commitArchive(); }, 2800) };
    showToast('보관됨', '되돌리기', () => {
      const p = pendingArchive; if (!p || p.c !== c) return; clearTimeout(p.timer); pendingArchive = null;
      c.archived = false; convs.splice(Math.min(p.idx, convs.length), 0, c); persist(); renderList();
      const r = $(`#convList li.row[data-id="${CSS.escape(c.id)}"]`); r?.classList.add('expanding'); setTimeout(() => r?.classList.remove('expanding'), 300);
    }, 2800);
  }
  function deleteConv(c) {   // permanent delete: local mode only (backend DELETE = archive)
    if (genId === c.id && controller) controller.abort();
    convs = convs.filter(x => x.id !== c.id); archivedList = archivedList.filter(x => x.id !== c.id); localStorage.removeItem(LS.draft + c.id);
    if (currentId === c.id) { currentId = convs[0]?.id || null; loadDraft(); }
    persist(); renderAll(); renderArchive(); buzz(15);
  }
  async function restoreConv(c) {
    archivedList = archivedList.filter(x => x !== c); c.archived = false;
    if (mode === 'local') { if (!convs.includes(c)) convs.push(c); }
    else { convs.push(c); write('patch', 'patch:' + c.id, { id: c.id, patch: { archived: false } }, () => { convs = convs.filter(x => x !== c); c.archived = true; archivedList.unshift(c); persist(); renderAll(); renderArchive(); }, '복원하지 못했어요'); }
    persist(); renderList(); renderArchive(); if (c === cur()) renderMessages(); showToast('복원됨', '', null, 1600);
  }
  function groupLabel(t) {
    const d0 = new Date(); d0.setHours(0, 0, 0, 0); const day = 864e5;
    if (t >= d0) return '오늘'; if (t >= d0 - day) return '어제'; if (t >= d0 - 6 * day) return '지난 7일'; if (t >= d0 - 29 * day) return '지난 30일';
    const d = new Date(t); return d.getFullYear() === d0.getFullYear() ? `${d.getMonth() + 1}월` : `${d.getFullYear()}년 ${d.getMonth() + 1}월`;
  }
  function fmtTime(t) {
    const d = new Date(t), d0 = new Date(); d0.setHours(0, 0, 0, 0);
    if (t >= d0) return d.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' });
    if (t >= d0 - 864e5) return '어제';
    return `${d.getMonth() + 1}월 ${d.getDate()}일`;
  }
  const clean = t => t.replace(/```[\s\S]*?(```|$)/g, ' [코드] ').replace(/[#*`>_|]+/g, '').replace(/\s+/g, ' ').trim().slice(0, 140);
  function preview(c) {
    for (let i = c.messages.length - 1; i >= 0; i--) {
      const m = c.messages[i]; const t = m.role === 'assistant' ? splitThink(m.content).answer : m.content;
      if (t && t.trim()) return clean(t);
    }
    return c.preview ? clean(c.preview) : '메시지 없음';
  }
  // server snippet: escaped except <mark>; re-sanitize defensively
  const safeSnippet = s => escapeHtml(String(s || '')).replace(/&lt;(\/?)mark&gt;/g, '<$1mark>');
  const listQuery = () => ($('#search').value || '').trim();
  let searchHits = null, searchT = 0, searchSeq = 0;
  function rowEl(c, cls = '') {
    const li = document.createElement('li'); li.className = 'row' + cls + (c.id === currentId ? ' active' : ''); li.dataset.id = c.id;
    const arch = cls.includes('archived');
    li.innerHTML = `<div class="row-actions">${arch ? '<button type="button" class="ra-restore" tabindex="-1">복원</button>' + (mode === 'local' ? '<button type="button" class="ra-del" tabindex="-1">삭제</button>' : '') : '<button type="button" class="ra-rename" tabindex="-1">이름 변경</button><button type="button" class="ra-archive" tabindex="-1">보관</button>'}</div>
      <div class="row-main"><div class="row-top"><span class="row-title"></span><time></time>${CHEV_R}</div><div class="row-sub"></div></div>`;
    li.querySelector('.row-title').textContent = (c.pinned ? '📌 ' : '') + c.title;
    li.querySelector('time').textContent = fmtTime(c.updated || Date.now());
    const sub = li.querySelector('.row-sub');
    if (genId === c.id) sub.innerHTML = '<span class="spin" aria-hidden="true"></span>답변 중…'; else sub.textContent = preview(c);
    return li;
  }
  function renderList() {
    const ul = $('#convList'); if (ul.querySelector('.row.editing')) return; ul.innerHTML = '';
    const q = listQuery().toLowerCase();
    const live = convs.filter(c => !c.archived);
    live.sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0) || b.updated - a.updated);
    const list = live.filter(c => !q || c.title.toLowerCase().includes(q) || c.messages.some(m => (m.content || '').toLowerCase().includes(q)) || (c.preview || '').toLowerCase().includes(q));
    $('#listEmpty').hidden = !!live.length || threadsLoading || !!q;
    let lastG = null;
    list.forEach(c => {
      const g = c.pinned ? '고정됨' : groupLabel(c.updated || 0);
      if (g !== lastG && !q) { const h = document.createElement('li'); h.className = 'group-label'; h.textContent = g; ul.appendChild(h); lastG = g; }
      ul.appendChild(rowEl(c));
    });
    if (q && searchHits) {   // server results (title + content), deduped against local rows
      const hits = searchHits.filter(h => h.match === 'content' || !list.some(c => c.id === h.thread_id));
      if (hits.length) { const h = document.createElement('li'); h.className = 'group-label'; h.textContent = '메시지'; ul.appendChild(h); }
      hits.forEach(hit => {
        const li = document.createElement('li'); li.className = 'hit'; li.dataset.tid = hit.thread_id; if (hit.message_id) li.dataset.mid = hit.message_id;
        li.innerHTML = `<div class="row-main"><div class="row-top"><span class="row-title"></span><time></time></div><div class="row-sub snippet">${safeSnippet(hit.snippet)}</div></div>`;
        li.querySelector('.row-title').textContent = hit.thread_title || '대화'; li.querySelector('time').textContent = fmtTime(toMs(hit.created_at));
        ul.appendChild(li);
      });
      if (!list.length && !hits.length) ul.innerHTML = '<li class="no-results">결과 없음</li>';
    } else if (q && !list.length && !(mode === 'server' && searchT)) ul.innerHTML = '<li class="no-results">결과 없음</li>';
    if (threadsLoading && !q) for (let i = 0; i < 3; i++) { const s = document.createElement('li'); s.className = 'skel'; s.innerHTML = '<i></i><i></i>'; ul.appendChild(s); }
    const ar = $('#archivedRow'); if (ar) { ar.hidden = !!q; const n = mode === 'local' ? convs.filter(c => c.archived).length : 0; $('#archivedCount').textContent = n ? String(n) : ''; }
  }
  function onSearch() {
    renderList(); clearTimeout(searchT); searchT = 0; searchHits = null;
    const q = listQuery(); $('#searchProgress').classList.remove('on');
    if (!q || mode !== 'server') return renderList();
    searchT = setTimeout(async () => {
      const seq = ++searchSeq; $('#searchProgress').classList.add('on');
      try { const j = await api('/v1/search?limit=20&q=' + encodeURIComponent(q)); if (seq !== searchSeq || listQuery() !== q) return; searchHits = j.data || []; }
      catch { if (seq === searchSeq) searchHits = []; }
      finally { if (seq === searchSeq) { searchT = 0; $('#searchProgress').classList.remove('on'); renderList(); } }
    }, 250);
  }
  $('#search').addEventListener('input', onSearch);
  $('#search').addEventListener('search', onSearch);
  async function openHit(tid, mid) {
    let c = convs.find(x => x.id === tid) || archivedList.find(x => x.id === tid);
    if (!c) { try { const t = await api('/v1/threads/' + encodeURIComponent(tid)); c = fromServerThread(t); (c.archived ? archivedList : convs).push(c); } catch { return showToast('대화를 열 수 없어요', '', null, 2000); } }
    openConv(c.id);
    if (!mid) return;
    for (let i = 0; i < 40 && !(c.loaded && !c.loading); i++) await new Promise(r => setTimeout(r, 50));
    for (let n = 0; n < 10 && !c.messages.some(m => m.id === mid) && c.hasMore; n++) await loadOlder();
    requestAnimationFrame(() => { const el = box.querySelector(`.msg[data-mid="${CSS.escape(mid)}"]`); if (!el) return; stick = false; el.scrollIntoView({ block: 'center' }); el.classList.add('flash'); setTimeout(() => el.classList.remove('flash'), 1600); });
  }
  const convOf = el => { const id = el.closest('.row')?.dataset.id; return convs.find(c => c.id === id) || archivedList.find(c => c.id === id); };
  $('#convList').addEventListener('click', e => {
    if (suppressClick) return;
    const hit = e.target.closest('.hit'); if (hit) return openHit(hit.dataset.tid, hit.dataset.mid);
    const row = e.target.closest('.row'); if (!row || row.classList.contains('editing')) return; const c = convOf(row); if (!c) return;
    if (e.target.closest('.ra-rename')) { closeSwipe(); return startRename(row, c); }
    if (e.target.closest('.ra-archive')) return swipeArchive(row, c);
    if (openRow) return closeSwipe();
    openConv(c.id);
  });

  /* ---------- archive screen (#/archive) ---------- */
  let chatFrom = 'list';
  async function loadArchive() {
    if (mode === 'local') { archivedList = convs.filter(c => c.archived); return renderArchive(); }
    $('#archList').innerHTML = '<li class="skel"><i></i><i></i></li>';
    try { const j = await api('/v1/threads?limit=50&archived=true'); archivedList = (j.data || []).map(t => fromServerThread(t, archivedList.find(a => a.id === t.id))); archivedList.forEach(c => c.archived = true); }
    catch {} renderArchive();
  }
  function renderArchive() {
    const ul = $('#archList'); if (!ul) return; ul.innerHTML = '';
    const list = mode === 'local' ? convs.filter(c => c.archived) : archivedList;
    if (mode === 'local') archivedList = list;
    list.sort((a, b) => b.updated - a.updated).forEach(c => ul.appendChild(rowEl(c, ' archived')));
    $('#archEmpty').hidden = !!list.length;
  }
  $('#archList').addEventListener('click', e => {
    if (suppressClick) return;
    const row = e.target.closest('.row'); if (!row) return; const c = convOf(row); if (!c) return;
    if (e.target.closest('.ra-restore')) return restoreConv(c);
    if (e.target.closest('.ra-del')) return confirmDelete(c);
    if (openRow) return closeSwipe();
    openConv(c.id, 'archive');
  });
  function confirmDelete(c) {
    closeSwipe();
    showMenu(null, [{ label: '대화 영구 삭제', danger: true, act: () => deleteConv(c) }, { label: '취소', act: () => {} }], { sheet: true, title: '대화를 영구 삭제할까요? 이 작업은 되돌릴 수 없어요.' });
  }
  $('#archivedRow').onclick = () => { history.pushState({ route: 'archive' }, '', '#/archive'); loadArchive(); animateTo('archive', 'push'); };
  $('#archBack').onclick = () => back();

  /* ---------- messages ---------- */
  function addMsgEl(role, content, m) {
    const wrap = document.createElement('div'); wrap.className = 'msg ' + role; if (m?.id) wrap.dataset.mid = m.id;
    const b = document.createElement('div'); b.className = 'bubble'; wrap.appendChild(b);
    if (role === 'user') b.textContent = content;
    box.appendChild(wrap); return b;
  }
  // opts: { live, thinkSecs, usage, actions }
  function freshen(tail) { // unused since v15: re-creating a .fresh span every frame restarted its fade = flicker
  }
  function _freshenOld(tail) { // token fade on the newest text of the tail block
    const last = tail.lastElementChild; const t = last && last.lastChild;
    if (t && t.nodeType === 3 && t.data.length) { const n = Math.min(12, t.data.length); const sp = document.createElement('span'); sp.className = 'fresh'; sp.textContent = t.data.slice(-n); t.data = t.data.slice(0, -n); last.appendChild(sp); }
  }
  // Streaming fast path (REVIEW M1): only touch think text + unfinished tail block.
  function patchLive(bubble, think, answer, thinking) {
    const det = bubble.querySelector('details.think');
    if ((think !== null) !== !!det) return false;
    if (det) {
      const tb = det.querySelector('.think-body');
      if (tb.textContent.length !== think.length) { const atEnd = tb.scrollHeight - tb.scrollTop - tb.clientHeight < 20; tb.textContent = think; if (atEnd) tb.scrollTop = tb.scrollHeight; }
      det.classList.toggle('live', thinking);
      const sp = det.querySelector('summary span'), lbl = thinking ? '생각하는 중…' : '생각 과정';
      if (sp.textContent !== lbl) sp.textContent = lbl;
      if (!thinking && !det.dataset.user && !settings.showThink && det.open) det.open = false;
    }
    const md = bubble.querySelector('.md');
    if (!answer.trim()) return !md && (!!bubble.querySelector('.typing') || (!!det && thinking));
    if (!md) { // first answer token: append answer container without touching the think block
      bubble.querySelectorAll('.typing,.warming,.ws-status').forEach(n => n.remove());
      const nm = document.createElement('div'); nm.className = 'md cursor'; nm.innerHTML = '<div class="stable"></div><div class="tail"></div>';
      bubble.appendChild(nm); bubble._cut = 0; return patchLive(bubble, think, answer, thinking);
    }
    const cut = stableCut(answer);
    // completed blocks are frozen: append only newly completed ones, never re-render what is already on screen
    const stable = md.querySelector('.stable'), prev = bubble._cut || 0;
    if (cut > prev) stable.insertAdjacentHTML('beforeend', renderMarkdown(answer.slice(prev, cut), bubble._sources));
    else if (cut < prev) stable.innerHTML = renderMarkdown(answer.slice(0, cut), bubble._sources);
    bubble._cut = cut;
    const tail = md.querySelector('.tail'), th = renderMarkdown(answer.slice(cut), bubble._sources);
    if (th !== bubble._tailHtml || cut !== prev) { tail.innerHTML = th; bubble._tailHtml = th; }
    return true;
  }
  function fillAssistant(bubble, text, opts = {}) {
    const { think, answer, thinking } = splitThink(stripStopMark(text));
    const live = !!opts.live;
    if (live && bubble._live && !opts.slow && patchLive(bubble, think, answer, live && thinking)) return;
    const prev = bubble.querySelector('details.think');
    let html = '';
    if (think !== null) {
      const isThinking = live && thinking;
      const open = prev && prev.dataset.user ? prev.open : (isThinking || settings.showThink);
      const label = isThinking ? '생각하는 중…' : ('생각 과정' + (opts.thinkSecs ? ` · ${opts.thinkSecs}초` : ''));
      html += `<details class="think${isThinking ? ' live' : ''}"${open ? ' open' : ''}><summary>${ICON.chev}<span>${label}</span></summary><div class="think-body">${escapeHtml(think)}</div></details>`;
    }
    const waiting = live && !answer.trim() && (think === null || !thinking);
    const srcs = opts.sources || opts.msg?.sources || (live ? bubble._sources : null);
    if (waiting && bubble._ws) html += `<div class="ws-status" role="status">${ICON.globe}<span>${escapeHtml(bubble._ws)}</span></div>`;
    else if (waiting) html += `<span class="typing"><i></i><i></i><i></i></span>${opts.slow ? '<div class="warming">모델 준비 중…</div>' : ''}`;
    else if (live && !answer.trim()) { /* still thinking: no answer container yet */ }
    else if (live) { const cut = stableCut(answer); bubble._cut = cut; html += `<div class="md cursor"><div class="stable">${renderMarkdown(answer.slice(0, cut), srcs)}</div><div class="tail">${renderMarkdown(answer.slice(cut), srcs)}</div></div>`; }
    else html += `<div class="md">${renderMarkdown(answer, srcs)}</div>${renderSources(srcs)}`;
    bubble._live = live;
    const userToggled = prev?.dataset.user;
    bubble.innerHTML = html;
    const det = bubble.querySelector('details.think');
    if (det) { if (userToggled) det.dataset.user = '1'; det.querySelector('summary').addEventListener('click', () => { det.dataset.user = '1'; }); }
    bubble._tailHtml = null;
    const msg = bubble.parentElement;
    msg.querySelector('.actions')?.remove(); msg.querySelector('.stopped')?.remove();
    if (!live && (opts.stopped || opts.msg?.status === 'incomplete')) { const st = document.createElement('div'); st.className = 'stopped'; st.setAttribute('role', 'note'); st.textContent = '중지됨'; msg.appendChild(st); }
    if (!live && opts.actions !== false) {
      const a = document.createElement('div'); a.className = 'actions';
      const m = opts.msg, fbOk = !!m && (mode === 'server' ? !!m.id : true);
      a.innerHTML = `<button type="button" class="c" aria-label="복사">${ICON.copy}</button>${opts.regen ? `<button type="button" class="r" aria-label="다시 생성">${ICON.regen}</button>` : ''}${fbOk ? `<button type="button" class="fb up" aria-label="좋아요" aria-pressed="false">${ICON.up}</button><button type="button" class="fb down" aria-label="별로예요" aria-pressed="false">${ICON.down}</button><button type="button" class="fb-why" hidden></button>` : ''}${opts.usage ? `<span class="usage">${escapeHtml(opts.usage)}</span>` : ''}`;
      a.querySelector('.c').onclick = e => copyText(e.currentTarget, answer.trim());
      a.querySelector('.r')?.addEventListener('click', regenerate);
      if (fbOk) { paintFb(a, m.feedback, m); a.querySelectorAll('.fb').forEach(b => b.onclick = () => setFeedback(m, b.classList.contains('up') ? 'up' : 'down', a, b)); a.querySelector('.fb-why').onclick = () => openFbPanel(m, a); }
      msg.appendChild(a);
    }
  }
  async function copyText(btn, text, label) {
    try { await navigator.clipboard.writeText(text); } catch { const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); }
    if (!btn) return showToast('복사됨', '', null, 1400);
    if (btn.dataset.busy) return; btn.dataset.busy = '1';
    const old = btn.innerHTML; btn.innerHTML = ICON.check + (label ? '<span>복사됨</span>' : ''); btn.classList.add('done');
    setTimeout(() => { btn.innerHTML = old; btn.classList.remove('done'); delete btn.dataset.busy; }, 1500);
  }
  box.addEventListener('click', e => {
    const b = e.target.closest('.code-head .copy'); if (!b) return;
    copyText(b, b.closest('.codeblock').querySelector('code').textContent, true);
  });
  /* ---------- feedback 👍/👎 + reasons (THREADS-SPEC §3, feedback-reasons spec v17) ---------- */
  const FB_CHIPS = {
    down: [['wrong_info', '정보가 틀려요'], ['too_long', '너무 길어요'], ['misunderstood', '질문을 잘못 이해했어요'], ['over_refusal', '거절이 과해요'], ['bad_source', '출처가 이상해요'], ['other', '기타']],
    up: [['accurate', '정확해요'], ['concise', '간결해요'], ['helpful', '유용해요'], ['good_source', '출처가 좋아요']] };
  const FB_MAX = 140;
  const fbLive = t => { const el = $('#fbLive'); if (!el) return; el.textContent = ''; setTimeout(() => { el.textContent = t; }, 30); };
  function paintFb(a, rating, m) {
    a.querySelectorAll('.fb').forEach(b => { const on = b.classList.contains(rating === 'up' ? 'up' : 'down') && !!rating; b.setAttribute('aria-pressed', String(on)); b.classList.toggle('on', on); b.classList.toggle('dim', !!rating && !on); });
    const why = a.querySelector('.fb-why'); if (!why) return;
    const n = (m?.fbReasons?.length || 0) + (m?.fbComment ? 1 : 0);
    why.hidden = !rating || !!a.parentElement?.querySelector('.fbp:not(.closing)');
    why.textContent = n ? `사유 ${n}` : '사유';
    why.setAttribute('aria-label', n ? `피드백 사유 ${n}개 수정` : '피드백 사유 고르기');
  }
  const fbPayload = m => ({ id: m.id, rating: m.feedback, reasons: m.feedback ? [...(m.fbReasons || [])] : [], comment: m.feedback ? (m.fbComment || '') : '' });
  // full-replacement save of {rating, reasons, comment}; local-only mode just persists on the device
  function saveFb(m, a, rollbackTo) {
    persist();
    if (mode !== 'server') return Promise.resolve();
    return write('feedback', 'fb:' + m.id, fbPayload(m), e => {
      if (e?.code === 'invalid_feedback_reason' && m.feedback) {   // keep the rating, drop the rejected reasons
        m.fbReasons = []; persist(); if (a.isConnected) paintFb(a, m.feedback, m);
        write('feedback', 'fb:' + m.id, fbPayload(m)); showToast('사유를 저장하지 못했어요. 평가는 저장됐어요', '', null, 2400); return 'handled';
      }
      if (e?.code === 'feedback_comment_too_long' && m.feedback) {   // keep rating+reasons, trim note to the limit and resend
        m.fbComment = (m.fbComment || '').trim().slice(0, FB_MAX - 1); persist();
        write('feedback', 'fb:' + m.id, fbPayload(m)); showToast('메모가 너무 길어 줄여서 저장했어요', '', null, 2400); return 'handled';
      }
      Object.assign(m, rollbackTo); persist(); if (a.isConnected) { paintFb(a, m.feedback, m); a.querySelector('.fb.' + (rollbackTo.feedback || 'up'))?.classList.add('err'); closeFbPanel(a, false); }
    }, '피드백을 저장하지 못했어요');
  }
  function fbReasonRejected(id) {   // outbox replay got 400 invalid_feedback_reason
    for (const c of convs) for (const m of c.messages || []) if (m.id === id) { m.fbReasons = []; persist(); }
    showToast('사유를 저장하지 못했어요. 평가는 저장됐어요', '', null, 2400);
  }
  function setFeedback(m, rating, a, btn) {
    const prev = { feedback: m.feedback, fbReasons: m.fbReasons || [], fbComment: m.fbComment || '' };
    const next = prev.feedback === rating ? null : rating;
    m.feedback = next; if (next !== prev.feedback) { m.fbReasons = []; m.fbComment = ''; }
    paintFb(a, next, m); buzz(8);
    if (next) { btn.classList.remove('pop'); void btn.offsetWidth; btn.classList.add('pop'); }
    a.querySelectorAll('.fb').forEach(b => b.classList.remove('err'));
    btn.classList.add('sending');
    Promise.resolve(saveFb(m, a, prev)).finally(() => btn.classList.remove('sending'));   // rating saves now, never waits for chips
    if (next) { openFbPanel(m, a); fbLive('피드백을 저장했어요. 사유를 고를 수 있어요'); } else closeFbPanel(a, false);
  }
  let fbObserver = null;
  function openFbPanel(m, a) {
    const msg = a.parentElement; msg.querySelector('.fbp')?.remove(); msg.querySelector('.fb-thanks')?.remove();
    const kind = m.feedback; if (!kind) return;
    const picks = new Set(m.fbReasons || []);
    const p = document.createElement('div'); p.className = 'fbp'; p._m = m; p._a = a;
    const hint = kind === 'down' ? '어떤 점이 아쉬웠나요? (선택)' : '어떤 점이 좋았나요? (선택)';
    const nid = 'fbn' + Math.random().toString(36).slice(2, 8);
    p.innerHTML = `<div class="fbp-in"><p class="fbp-hint">${hint}</p>
      <div class="fbp-chips" role="group" aria-label="${kind === 'down' ? '아쉬운 점' : '좋았던 점'}">${FB_CHIPS[kind].map(([k, t]) => `<button type="button" class="fbchip" data-k="${k}" aria-pressed="${picks.has(k)}">${ICON.check}<span>${t}</span></button>`).join('')}</div>
      <div class="fbp-note" hidden><label for="${nid}" class="sr-only">메모</label><input id="${nid}" class="fbp-input" type="text" maxlength="${FB_MAX}" enterkeyhint="send" autocomplete="off" autocorrect="on" autocapitalize="sentences" data-1p-ignore data-lpignore="true" data-form-type="other" placeholder="한 줄로 남겨 주세요"><span class="fbp-count" hidden></span></div>
      <div class="fbp-foot"><button type="button" class="fbp-memo text-btn">메모 추가</button><button type="button" class="fbp-done"></button></div></div>`;
    a.insertAdjacentElement('afterend', p);
    const inp = p.querySelector('.fbp-input'), note = p.querySelector('.fbp-note'), cnt = p.querySelector('.fbp-count'), done = p.querySelector('.fbp-done'), memo = p.querySelector('.fbp-memo');
    inp.value = m.fbComment || '';
    const showNote = focus => { note.hidden = false; memo.hidden = true; if (focus) inp.focus({ preventScroll: true }); };
    if (inp.value) showNote(false);
    const upd = () => {
      const any = picks.size > 0 || !!inp.value.trim();
      done.textContent = any ? '완료' : '건너뛰기'; done.classList.toggle('primary-text', any);
      const left = FB_MAX - inp.value.length; cnt.hidden = inp.value.length <= 120; cnt.textContent = String(left);
    };
    p.querySelectorAll('.fbchip').forEach(c => c.onclick = () => {
      const k = c.dataset.k, on = !picks.has(k); on ? picks.add(k) : picks.delete(k); c.setAttribute('aria-pressed', String(on));
      if (k === 'other' && on) showNote(true); p._dirty = true; upd();
    });
    memo.onclick = () => showNote(true);
    inp.oninput = () => { p._dirty = true; upd(); };
    inp.onkeydown = e => { if (e.key === 'Enter' && !e.isComposing && e.keyCode !== 229) { e.preventDefault(); submit(); } };
    if (!a._fbEsc) { a._fbEsc = true; a.addEventListener('keydown', e => { if (e.key === 'Escape' && !e.isComposing && a.parentElement?.querySelector('.fbp:not(.closing)')) { e.preventDefault(); e.stopPropagation(); closeFbPanel(a, true); } }); }   // N3: Esc from 👍/👎 too
    p.addEventListener('keydown', e => { if (e.key === 'Escape' && !e.isComposing) { e.preventDefault(); e.stopPropagation(); closeFbPanel(a, true); } });
    const submit = () => {
      const comment = inp.value.trim().slice(0, FB_MAX), reasons = FB_CHIPS[kind].map(c => c[0]).filter(k => picks.has(k));
      const prev = { feedback: m.feedback, fbReasons: m.fbReasons || [], fbComment: m.fbComment || '' };
      const changed = comment !== prev.fbComment || reasons.join() !== prev.fbReasons.join();
      m.fbReasons = reasons; m.fbComment = comment;
      p._closing = true; collapse(p);
      if (changed) saveFb(m, a, prev);
      paintFb(a, m.feedback, m);
      if (reasons.length || comment) thanks(a);
    };
    p._submit = submit; p._picks = picks; p._inp = inp;
    done.onclick = submit; upd();
    requestAnimationFrame(() => requestAnimationFrame(() => p.classList.add('open')));
    paintFb(a, m.feedback, m);
    // auto-skip when scrolled offscreen (after it was seen)
    if ('IntersectionObserver' in window) {
      fbObserver ||= new IntersectionObserver(es => es.forEach(en => {
        const el = en.target; if (en.isIntersecting) { el._seen = true; return; }
        if (el._seen && !el._closing && document.activeElement !== el._inp && Math.abs(box.scrollTop - el._st) > 40) closeFbPanel(el._a, true);   // only after the user scrolled it away
      }), { root: box, threshold: 0 });
      setTimeout(() => { if (p.isConnected && !p._closing) { p._st = box.scrollTop; fbObserver.observe(p); } }, 320);
    }
  }
  function collapse(p) { fbObserver?.unobserve(p); p.classList.remove('open'); p.classList.add('closing'); setTimeout(() => p.remove(), 280); }
  function thanks(a) {
    const t = document.createElement('div'); t.className = 'fb-thanks'; t.textContent = '고마워요'; a.insertAdjacentElement('afterend', t);
    fbLive('고마워요'); setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 300); }, 1500);
  }
  // skip=true: auto/explicit skip — still saves chips/note already picked
  function closeFbPanel(a, skip) {
    const p = a?.parentElement?.querySelector('.fbp'); if (!p || p._closing) return;
    if (skip && (p._picks.size || p._inp.value.trim()) && p._dirty) return p._submit();
    p._closing = true; collapse(p); setTimeout(() => { if (a.isConnected) paintFb(a, p._m.feedback, p._m); }, 290);
  }
  function closeAllFbPanels() { box.querySelectorAll('.fbp').forEach(p => closeFbPanel(p._a, true)); }
  function usageText(u, secs) {
    if (!u) return secs ? `${secs}s` : '';
    const ct = u.completion_tokens;
    const rate = secs && ct ? ` · ${(ct / secs).toFixed(0)} tok/s` : '';
    return `입력 ${u.prompt_tokens ?? '?'} · 출력 ${ct ?? '?'} tok${rate}`;
  }

  const CHIPS = [['코드 리뷰', '이 함수의 개선점을 알려줘'], ['요약', '긴 글을 핵심 3줄로 정리해줘'], ['번역', '자연스러운 영어 문장으로 바꿔줘'], ['아이디어', '주말에 할 사이드 프로젝트 추천']];
  function renderEmpty() {
    box.innerHTML = `<div class="empty"><div class="mark"></div><h1>Eve에게 무엇이든 물어보세요</h1><small>${escapeHtml(shortModel() || '로컬 모델')} · 로컬에서 실행 중</small>
      <div class="chips">${CHIPS.map((c, i) => `<button type="button" class="chip" data-i="${i}" data-q="${escapeHtml(c[1])}"><b>${escapeHtml(c[0])}</b><span>${escapeHtml(c[1])}</span></button>`).join('')}</div></div>`;
    box.querySelectorAll('.chip').forEach(b => { b.style.animationDelay = (80 + b.dataset.i * 40) + 'ms'; });
    box.querySelectorAll('.chip').forEach(b => b.onclick = () => { if (!controller) send(b.dataset.q); });
  }
  function renderMessages(keep) {
    box.innerHTML = '';
    const c = cur();
    $('#title').textContent = c ? c.title : '새 대화';
    $('#modelName').textContent = shortModel();
    chatView.classList.toggle('archived', !!c?.archived);
    if (c?.loading && !c.messages.length) { box.innerHTML = '<div class="older loading"><span class="spin"></span></div>'; return; }
    if (!c || !c.messages.length) return renderEmpty();
    box.classList.add('no-anim');
    if (c.hasMore) box.insertAdjacentHTML('afterbegin', '<div class="older"><span class="spin"></span></div>');
    const lastA = c.messages.map(m => m.role).lastIndexOf('assistant');
    c.messages.forEach((m, i) => {
      if (m.role === 'user') addMsgEl('user', m.content, m);
      else fillAssistant(addMsgEl('assistant', '', m), m.content, { usage: m.usageText || (m.usage ? usageText(m.usage) : ''), regen: !c.archived && i === lastA && i === c.messages.length - 1, thinkSecs: m.thinkSecs, msg: m });
    });
    requestAnimationFrame(() => { box.classList.remove('no-anim'); if (!keep) { stick = true; scrollBottom(); } });
  }
  function renderAll() { renderList(); renderMessages(); }

  function setBusy(b) {
    sendBtn.classList.toggle('stop', b);
    sendBtn.disabled = b ? false : !input.value.trim();
    sendBtn.setAttribute('aria-label', b ? '생성 중지' : '전송'); sendBtn.title = b ? '생성 중지 (Esc)' : '';
    if (b) { genId = currentId; if (currentId) localStorage.removeItem(LS.draft + currentId); } else { genId = null; if (app.dataset.route === 'list' || wide.matches) renderList(); maybeA2HS(); }
  }

  /* ---------- errors (gateway contract) ---------- */
  const RETRYABLE = new Set([429, 502, 503, 504]);
  function errMsg(status, body) {
    let e = {}; try { e = JSON.parse(body).error || {}; } catch {}
    const code = e.code || '', m = e.message || String(body || '').slice(0, 300);
    if (code === 'identity_not_allowed') return '이 Tailscale 계정은 허용되지 않았어요 (401 identity_not_allowed).';
    if (code === 'rate_limited') return '요청이 너무 많아요 (429 rate_limited). 잠시 후 재시도하세요.';
    if (status === 401) return '이 기기에서 Tailscale 연결을 확인하세요 (401' + (code ? ' ' + code : '') + ').';
    if (code === 'queue_full') return '서버 대기열이 가득 찼습니다 (429 queue_full). 잠시 후 재시도하세요.';
    if (code === 'queue_timeout') return '대기 시간이 초과되었습니다 (429 queue_timeout). 잠시 후 재시도하세요.';
    if (status === 503) return '모델 서버에 연결할 수 없습니다 (503' + (code ? ' ' + code : '') + ').';
    if (status === 504) return '모델 서버 응답 시간 초과 (504' + (code ? ' ' + code : '') + ').';
    if (status === 404) return '엔드포인트를 찾을 수 없습니다 (404). Base URL을 확인하세요.';
    return `서버 오류 ${status}${code ? ' ' + code : ''}: ${m}`;
  }
  function clearErrors() { box.querySelectorAll('.msg.error').forEach(e => e.remove()); }
  function addError(text, retry) {
    const b = addMsgEl('error');
    b.innerHTML = `${ICON.warn}<span class="err-text"></span>`;
    b.querySelector('.err-text').textContent = text;
    if (retry) { const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'btn retry'; btn.textContent = '재시도'; btn.onclick = () => { b.parentElement.remove(); retry(); }; b.appendChild(btn); }
    scrollBottom(true);
  }

  /* ---------- send / generate ---------- */
  async function send(text) {
    let c = cur();
    if (!c || c.archived) { c = blankConv(); convs.unshift(c); currentId = c.id; }
    if (!c.messages.length) { box.innerHTML = ''; c.title = text.slice(0, 30); $('#title').textContent = c.title; }
    clearErrors(); closeAllFbPanels();
    box.querySelectorAll('.actions .r').forEach(r => r.remove());
    c.messages.push({ role: 'user', content: text, created: Date.now() });
    c.updated = Date.now(); persist(); renderList();
    addMsgEl('user', text);
    input.value = ''; grow(); stick = true; scrollBottom(true);
    return generate(c);
  }
  async function regenerate() {
    const c = cur(); if (controller || !c || c._regenBusy) return;
    const la = c.messages.at(-1);
    if (mode === 'server' && c.srv && la?.role === 'assistant' && !la.id && la.status === 'incomplete') { c._regenBusy = true; try { await resolveStoppedId(c, la, null, 1); } finally { c._regenBusy = false; } if (controller || c !== cur()) return; }
    let replaceId = null;
    if (c.messages.at(-1)?.role === 'assistant') replaceId = c.messages.pop().id || null;
    const els = box.querySelectorAll('.msg.assistant'); els[els.length - 1]?.remove();
    clearErrors(); persist(); generate(c, replaceId);
  }

  // the server stores a stopped reply as status=incomplete, but the client never sees its id (stream cut before "persisted")
  async function resolveStoppedId(c, msg, bubble, tries = 3) {
    for (let k = 0; k < tries && !msg.id; k++) {
      await new Promise(r => setTimeout(r, 400 + k * 600));
      if (!c.messages.includes(msg)) return;
      try {
        const j = await api(`/v1/threads/${encodeURIComponent(c.id)}/messages?limit=4`);
        const a = (j.data || []).filter(m => m.role === 'assistant').pop();
        const u = (j.data || []).filter(m => m.role === 'user').pop();
        if (a && a.status === 'incomplete' && !c.messages.some(x => x !== msg && x.id === a.id)) {
          msg.id = a.id; const um = [...c.messages].reverse().find(m => m.role === 'user'); if (um && u && !um.id) um.id = u.id;
          persist();
          if (bubble?.isConnected && c === cur()) { bubble.parentElement.dataset.mid = a.id; fillAssistant(bubble, msg.content, { regen: c.messages.at(-1) === msg, thinkSecs: msg.thinkSecs, msg }); }
        }
      } catch {}
    }
  }
  function stopGeneration() { if (controller) { buzz(10); sendBtn.classList.add('pressed'); setTimeout(() => sendBtn.classList.remove('pressed'), 160); controller.abort(); } }

  async function generate(c, replaceId) {
    const bubble = addMsgEl('assistant');
    const hist = c.messages.map(({ role, content }) => ({ role, content: role === 'assistant' ? stripStopMark(splitThink(stripStopMark(content)).answer) : content }))
      .filter(m => m.role !== 'assistant' || m.content.trim());
    if (settings.noThink) { const last = hist[hist.length - 1]; if (last && last.role === 'user' && !/\/no_think\s*$/.test(last.content)) last.content += ' /no_think'; }
    const msgs = (settings.system ? [{ role: 'system', content: settings.system }] : []).concat(hist);
    const ctl = controller = new AbortController(); setBusy(true); let stopped = false;
    let sources = null; const ws = webOn(); bubble._ws = ''; bubble._sources = null;
    let acc = '', reasoning = '', usage = null, streamErr = null, slow = false, thinkStart = 0, thinkSecs = 0;
    const t0 = performance.now();
    const full = () => reasoning ? `<think>${reasoning}</think>${acc}` : acc;
    const view = () => reasoning && !acc ? '<think>' + reasoning : full();
    fillAssistant(bubble, '', { live: true }); scrollBottom(true);
    const slowTimer = setTimeout(() => { if (!acc && !reasoning) { slow = true; fillAssistant(bubble, '', { live: true, slow }); } }, 3000);
    let raf = 0;
    const paint = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; fillAssistant(bubble, view(), { live: true }); if (stick) scrollBottom(); }); };
    const retry = () => generate(c, replaceId);
    let persisted = null; const userMsg = [...c.messages].reverse().find(m => m.role === 'user');
    const ids = j => { if (j.thread_id && mode === 'server') adoptThreadId(c, j.thread_id); if (j.user_message_id && userMsg) userMsg.id = j.user_message_id; };
    const finish = () => { clearTimeout(slowTimer); if (controller === ctl) controller = null; setBusy(false); if (raf) cancelAnimationFrame(raf); raf = 0; };
    const markThink = () => { if (!thinkStart) thinkStart = performance.now(); };
    const endThink = () => { if (thinkStart && !thinkSecs) thinkSecs = Math.max(1, Math.round((performance.now() - thinkStart) / 1000)); };
    const setWs = t => { bubble._ws = t; if (!acc.trim()) { bubble._live = false; fillAssistant(bubble, view(), { live: true }); if (stick) scrollBottom(); } };
    let wsReq = ws;
    try {
      const post = keep => fetch(apiBase() + '/v1/chat/completions', {
        method: 'POST', headers: headers('POST'), signal: ctl.signal,
        body: JSON.stringify(Object.assign({ model: settings.model || undefined, messages: msgs, stream: true, stream_options: { include_usage: true } },
          keep ? { thread_id: c.fresh || !c.srv ? 'new' : c.id } : {}, keep && replaceId ? { replace_message_id: replaceId } : {}, wsReq ? { web_search: 'auto' } : {}))
      });
      let res = await post(mode === 'server');
      // storage switched off on the gateway mid-session: answer anyway without persistence, show the subtle notice
      if (res.status === 503 && mode === 'server') { const t = await res.clone().text().catch(() => ''); if (t.includes('persistence_disabled')) { persistOff = true; renderSync(); res = await post(false); } }
      if (res.status === 400 && wsReq) { const t = await res.clone().text().catch(() => ''); if (t.includes('web_search_disabled')) { wsReq = false; setWebOn(false); showToast('서버에서 웹 검색이 꺼져 있어요', '', null, 2500); res = await post(mode === 'server' && !persistOff); } }
      if (!res.ok) {
        const body = await res.text().catch(() => '');
        if (res.status === 401) { let code; try { code = JSON.parse(body).error?.code; } catch {} showAuthNotice(() => generate(c), code); }
        throw Object.assign(new Error(errMsg(res.status, body)), { http: res.status });
      }
      const ctype = res.headers.get('content-type') || '';
      if (!res.body || ctype.includes('application/json')) {
        const j = await res.json();
        if (j.error) throw Object.assign(new Error(errMsg(res.status, JSON.stringify(j))), { http: res.status });
        const m = j.choices?.[0]?.message || {};
        acc = m.content || ''; reasoning = m.reasoning || m.reasoning_content || ''; usage = j.usage || null; if (Array.isArray(m.sources) && m.sources.length) sources = m.sources;
        const h = k => res.headers.get(k);
        ids({ thread_id: j.thread_id || h('X-Thread-Id'), user_message_id: h('X-User-Message-Id') });
        if (j.message_id || h('X-Message-Id')) persisted = { message_id: j.message_id || h('X-Message-Id') };
      } else {
        const reader = res.body.getReader(); const dec = new TextDecoder(); let done = false;
        const parser = createSSEParser(data => {
          if (data.trim() === '[DONE]') { done = true; return; }
          let j; try { j = JSON.parse(data); } catch { return; }
          if (j.error) { streamErr = j.error; return; }
          if (j.object === 'chat.completion.persisted') { ids(j); persisted = j; return; }
          if (j.object === 'chat.completion.tool_call') {
            const a = j.args || {}; let d = ''; try { d = a.url ? new URL(a.url).hostname.replace(/^www\./, '') : ''; } catch {}
            setWs(j.tool === 'web_fetch' ? `읽는 중: ${d || '웹 페이지'}` : (a.query ? `웹 검색 중: ${a.query}` : '웹 검색 중…')); return;
          }
          if (j.object === 'chat.completion.tool_result') {
            if (Array.isArray(j.sources)) { const m = new Map((sources || []).map(x => [x.n, x])); j.sources.forEach(x => m.set(x.n, x)); sources = [...m.values()]; }
            setWs(j.status && j.status !== 'ok' && !(j.sources || []).length ? '검색 결과 없이 답변 작성 중…' : '답변 작성 중…'); return;
          }
          if (j.object === 'chat.completion.sources') { if (Array.isArray(j.sources)) { sources = j.sources; bubble._sources = sources; } return; }
          ids(j);
          if (j.usage) usage = j.usage;
          const d = j.choices?.[0]?.delta || {};
          const r = d.reasoning ?? d.reasoning_content;
          if (r) { markThink(); reasoning += r; }
          if (d.content) {
            acc += d.content;
            if (acc.includes('<think>')) markThink();
            if (reasoning || acc.includes('</think>')) endThink();
          }
          paint();
        });
        const onAbort = () => { try { reader.cancel(); } catch {} };
        ctl.signal.addEventListener('abort', onAbort, { once: true });
        while (!done) { const { value, done: rd } = await reader.read(); if (rd) break; parser.push(dec.decode(value, { stream: true })); }
        ctl.signal.removeEventListener('abort', onAbort);
        if (ctl.signal.aborted && !persisted) stopped = true;
        parser.flush();
        if (!done) try { reader.cancel(); } catch {}
      }
    } catch (e) {
      finish();
      if (e.name === 'AbortError' || ctl.signal.aborted) { stopped = true; }
      else {
        if (acc || reasoning) { fillAssistant(bubble, full(), { actions: false }); c.messages.push({ role: 'assistant', content: full() }); persist(); }
        else bubble.parentElement.remove();
        const m = e.http ? e.message : `네트워크 오류: ${e.message}. Tailscale 연결과 서버 주소(${apiBase() || location.origin})를 확인하세요.`;
        addError(m, (!e.http || RETRYABLE.has(e.http)) && !(acc || reasoning) ? retry : null);
        return;
      }
    }
    finish(); endThink();
    const final = full();
    if (stopped) {
      if (userMsg && !c.messages.includes(userMsg)) { bubble.parentElement?.remove(); return; }   // "edit & resend" truncated the thread
      const msg = { role: 'assistant', content: final, status: 'incomplete', created: Date.now() }; if (thinkSecs) msg.thinkSecs = thinkSecs;
      if (sources?.length) msg.sources = sources;
      fillAssistant(bubble, final, { regen: true, thinkSecs, msg, stopped: true });
      c.messages.push(msg); c.updated = Date.now(); if (final) c.preview = clean(splitThink(final).answer); persist(); renderList();
      if (mode === 'server' && c.srv) resolveStoppedId(c, msg, bubble);
      if (stick) scrollBottom();
      return;
    }
    if (streamErr) {
      if (final) { fillAssistant(bubble, final, { actions: false, thinkSecs }); c.messages.push({ role: 'assistant', content: final }); persist(); } else bubble.parentElement.remove();
      addError(`스트리밍 중 오류: ${streamErr.message || streamErr.code || '알 수 없음'}${streamErr.code ? ' (' + streamErr.code + ')' : ''}`, final ? null : retry);
      return;
    }
    const secs = +((performance.now() - t0) / 1000).toFixed(1);
    const ut = usageText(usage, secs);
    fillAssistant(bubble, final, { usage: ut, regen: true, thinkSecs, sources });
    const msg = { role: 'assistant', content: final, usageText: ut, created: Date.now() }; if (sources?.length) msg.sources = sources; if (usage) msg.usage = usage; if (thinkSecs) msg.thinkSecs = thinkSecs;
    if (persisted?.message_id) msg.id = persisted.message_id; else if (mode === 'server') c.loaded = false;   // refetch next open
    c.messages.push(msg); c.updated = Date.now(); c.preview = clean(splitThink(final).answer); persist(); renderList();
    if (msg.id || mode !== 'server') { if (msg.id) bubble.parentElement.dataset.mid = msg.id; fillAssistant(bubble, final, { usage: ut, regen: true, thinkSecs, msg }); }
    if (stick) scrollBottom();
  }

  /* ---------- composer ---------- */
  function grow() { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 160) + 'px'; if (!controller) sendBtn.disabled = !input.value.trim(); }
  input.addEventListener('input', grow);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey && !isTouch && !e.isComposing) { e.preventDefault(); $('#composer').requestSubmit(); }
  });
  $('#composer').addEventListener('submit', e => {
    e.preventDefault();
    if (controller) { stopGeneration(); return; }
    const t = input.value.trim(); if (!t) return;
    send(t);
  });

  /* ---------- navigation stack (NATIVE §1, §4) ---------- */
  const app = $('#app'), listView = $('#listView'), chatView = $('#chatView'), archView = $('#archiveView');
  let navTimer = 0;
  function syncInert() {
    const r = app.dataset.route, both = wide.matches;
    listView.inert = !both && r !== 'list'; chatView.inert = !both && r !== 'chat'; archView.inert = r !== 'archive';
  }
  function setRoute(r) { app.dataset.route = r; save(LS.route, r); syncInert(); if (r === 'list') renderList(); }
  function slide(route, dir, dur) { // CSS fallback (and always used after a swipe)
    clearTimeout(navTimer);
    app.style.setProperty('--nav-d', (dur || (dir === 'push' ? 420 : 380)) + 'ms');
    app.classList.add('transitioning'); setRoute(route);
    navTimer = setTimeout(() => { app.classList.remove('transitioning'); app.style.removeProperty('--nav-d'); }, (dur || 420) + 40);
  }
  function animateTo(route, dir) {
    if (app.dataset.route === route) return syncInert();
    if (wide.matches || !app.classList.contains('ready')) return setRoute(route);
    if (route === 'archive' || app.dataset.route === 'archive') return slide(route, dir);
    if (document.startViewTransition && !reduce.matches) {
      document.documentElement.dataset.dir = dir; app.classList.add('vt');
      (route === 'chat' ? chatView : listView).inert = false; // target screen interactive immediately
      const t = document.startViewTransition(() => setRoute(route));
      t.finished.finally(() => app.classList.remove('vt'));
    } else slide(route, dir);
  }
  const hashFor = r => r === 'chat' && currentId ? '#/c/' + currentId : '#/';
  function go(route) {
    if (popping) return void setTimeout(() => go(route), 50);
    if (route === 'chat') {
      if (history.state?.route === 'chat') history.replaceState({ route: 'chat', id: currentId }, '', hashFor('chat'));
      else history.pushState({ route: 'chat', id: currentId }, '', hashFor('chat'));
      animateTo('chat', 'push');
    } else back();
  }
  let popping = false;
  function back() {
    if (app.dataset.route === 'list' || popping) return;                   // already on list / pop in flight (REVIEW M1)
    if (input === document.activeElement) input.blur();
    const target = app.dataset.route === 'chat' && chatFrom === 'archive' ? 'archive' : 'list';
    if (target === 'list') chatFrom = 'list';
    if (history.state?.route === 'chat' || history.state?.route === 'archive') { popping = true; ignorePop++; history.back(); }   // route changes now; popstate is ignored
    else history.replaceState({ route: target }, '', target === 'archive' ? '#/archive' : '#/');
    animateTo(target, 'pop');
  }
  let ignorePop = 0;
  window.addEventListener('popstate', e => {
    popping = false;
    if (ignorePop) { ignorePop--; return; }
    const st = e.state || { route: 'list' };
    if (st.route === 'chat' && st.id && st.id !== currentId && (convs.some(c => c.id === st.id) || archivedList.some(c => c.id === st.id))) { saveDraft(); currentId = st.id; persist(); renderAll(); loadDraft(); ensureMessages(cur()); }
    const r = st.route === 'chat' ? 'chat' : st.route === 'archive' ? 'archive' : 'list';
    if (r === 'archive') loadArchive();
    if (e.hasUAVisualTransition) return setRoute(r);   // Safari already animated its own back/forward (REVIEW M2)
    animateTo(r, r === 'chat' ? 'push' : 'pop');
  });
  wide.addEventListener?.('change', syncInert);
  $('#backBtn').onclick = back;
  $('#newChat').onclick = newConv; $('#newChat2').onclick = newConv; $('#newChat3').onclick = newConv;

  /* large title collapse (§2) */
  const scroller = $('#listScroller'), lt = $('#listView .large-title'), lnav = $('#listView .navbar');
  if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => lnav.classList.toggle('collapsed', !e.isIntersecting), { root: scroller, rootMargin: '-52px 0px 0px 0px' }).observe(lt);
  scroller.addEventListener('scroll', () => { if (scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 400) loadMoreThreads(); }, { passive: true });
  scroller.addEventListener('scroll', () => requestAnimationFrame(() => { const y = scroller.scrollTop; lt.style.transform = y < 0 ? `scale(${1 + Math.min(-y, 60) / 600})` : ''; }), { passive: true });

  /* ---------- edge swipe-back, standalone only (§5) ---------- */
  const rubber = (d, lim = 120) => lim * (1 - 1 / (d / lim + 1)); // iOS-like resistance
  let g = null;
  const curX = el => { const m = getComputedStyle(el).transform; return m && m !== 'none' ? new DOMMatrix(m).m41 : 0; };
  chatView.addEventListener('touchstart', e => {
    if (!isStandalone() || wide.matches || app.dataset.route !== 'chat' || e.touches.length > 1 || popping || app.classList.contains('vt') || app.classList.contains('transitioning')) return;
    const t = e.touches[0], edge = 24 + (parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--sal')) || 0);
    if (t.clientX > edge) return;
    g = { x0: t.clientX, y0: t.clientY, t0: performance.now(), tl: performance.now(), xl: t.clientX, v: 0, lock: null, dx: 0, start: Math.max(0, curX(chatView)) };
  }, { passive: true });
  chatView.addEventListener('touchmove', e => {
    if (!g) return; const t = e.touches[0], dx = t.clientX - g.x0, dy = t.clientY - g.y0;
    if (!g.lock) {
      if (Math.hypot(dx, dy) < 8) return;
      g.lock = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
      if (g.lock === 'x') { app.classList.add('dragging'); clearTimeout(navTimer); app.classList.remove('transitioning'); if (document.activeElement === input) input.blur(); }
    }
    if (g.lock !== 'x') return; e.preventDefault();
    const now = performance.now(); g.v = (t.clientX - g.xl) / Math.max(1, now - g.tl); g.xl = t.clientX; g.tl = now;
    const raw = g.start + dx; g.dx = raw < 0 ? -rubber(-raw, 40) : raw;
    const W = innerWidth, p = Math.min(1, Math.max(0, g.dx / W));
    chatView.style.transform = `translateX(${g.dx}px)`;
    listView.style.transform = `translateX(${-30 + 30 * p}%)`;
    listView.style.setProperty('--dim', String(.25 * (1 - p)));
  }, { passive: false });
  const endSwipe = () => {
    if (!g) return; const s = g; g = null; if (s.lock !== 'x') return;
    const W = innerWidth, dxp = Math.max(0, s.dx);
    const commit = dxp > W * .5 || s.v > .5;
    const remain = commit ? 1 - dxp / W : dxp / W;
    const dur = Math.max(180, 380 * remain);
    app.classList.remove('dragging');
    chatView.style.transform = listView.style.transform = ''; listView.style.removeProperty('--dim');
    if (commit) { buzz(8); slide('list', 'pop', dur); if (!popping && history.state?.route === 'chat') { popping = true; ignorePop++; history.back(); } else if (!popping) history.replaceState({ route: 'list' }, '', '#/'); }
    else slide('chat', 'push', dur);
  };
  chatView.addEventListener('touchend', endSwipe); chatView.addEventListener('touchcancel', endSwipe);

  /* ---------- list swipe actions (§3) ---------- */
  let openRow = null, rs = null; const ACT_W = 148;
  function closeSwipe() { if (openRow) { const m = openRow.querySelector('.row-main'); m.style.transition = ''; m.style.transform = ''; openRow.classList.remove('swiped'); openRow = null; } }
  function swipeArchive(row, c) {
    const m = row.querySelector('.row-main'); m.style.transition = 'transform 260ms var(--ease-sheet)'; m.style.transform = 'translateX(-100%)';
    row.style.height = row.offsetHeight + 'px'; row.classList.add('removing', 'collapsing');
    requestAnimationFrame(() => { row.style.height = '0px'; });
    setTimeout(() => { openRow = null; archiveConv(c); }, 300);
  }
  for (const ul of [$('#convList'), $('#archList')]) {
  ul.addEventListener('touchstart', e => {
    const row = e.target.closest('.row'); if (!row || e.target.closest('.row-actions')) return;
    if (openRow && openRow !== row) closeSwipe();
    const t = e.touches[0]; rs = { row, m: row.querySelector('.row-main'), x0: t.clientX, y0: t.clientY, lock: null, base: row === openRow ? -ACT_W : 0, dx: 0, v: 0, xl: t.clientX, tl: performance.now() };
  }, { passive: true });
  ul.addEventListener('touchmove', e => {
    if (!rs) return; const t = e.touches[0], dx = t.clientX - rs.x0, dy = t.clientY - rs.y0;
    if (!rs.lock) { if (Math.hypot(dx, dy) < 8) return; rs.lock = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y'; if (rs.lock === 'x') { rs.m.style.transition = 'none'; rs.row.classList.add('swiped'); cancelLP(); } }
    if (rs.lock !== 'x') return; e.preventDefault();
    const now = performance.now(); rs.v = (t.clientX - rs.xl) / Math.max(1, now - rs.tl); rs.xl = t.clientX; rs.tl = now;
    let x = rs.base + dx; if (x > 0) x = rubber(x, 30); rs.dx = x;
    rs.row.classList.toggle('full', x < -rs.row.offsetWidth * .6);
    rs.m.style.transform = `translateX(${x}px)`;
  }, { passive: false });
  ul.addEventListener('touchend', () => {
    if (!rs) return; const s = rs; rs = null; if (s.lock !== 'x') return;
    suppressClickBriefly();
    s.m.style.transition = ''; s.row.classList.remove('full');
    if (s.dx < -s.row.offsetWidth * .6) { const c = convOf(s.row); buzz(15); if (s.row.classList.contains('archived')) { s.m.style.transform = ''; s.row.classList.remove('swiped'); return restoreConv(c); } return swipeArchive(s.row, c); }
    if (s.dx < -60 || (s.v < -.4 && s.dx < -20)) { s.m.style.transform = `translateX(${-ACT_W}px)`; openRow = s.row; }
    else { s.m.style.transform = ''; s.row.classList.remove('swiped'); if (openRow === s.row) openRow = null; }
  });
  }
  const ul = $('#convList');
  scroller.addEventListener('scroll', () => { if (openRow && !rs) closeSwipe(); }, { passive: true });

  /* ---------- long-press / context menu (§7) ---------- */
  let suppressClick = false, lpT = null, lpEl = null, lpX = 0, lpY = 0;
  function suppressClickBriefly() { suppressClick = true; setTimeout(() => { suppressClick = false; }, 350); }
  document.addEventListener('click', e => { if (suppressClick) { e.stopPropagation(); e.preventDefault(); } }, true);
  function cancelLP() { clearTimeout(lpT); lpT = null; lpEl?.classList.remove('pressing'); lpEl = null; }
  function longPress(container, sel, cb) {
    container.addEventListener('touchstart', e => {
      if (e.touches.length > 1) return cancelLP();
      const el = e.target.closest(sel); if (!el || e.target.closest('button,a,summary,input,textarea,.row-actions') || el.classList.contains('selectable')) return;
      cancelLP(); lpEl = el; ({ clientX: lpX, clientY: lpY } = e.touches[0]);
      el.classList.add('pressing');
      lpT = setTimeout(() => { const t = lpEl; cancelLP(); suppressClickBriefly(); buzz(10); cb(t); }, 500);
    }, { passive: true });
    container.addEventListener('touchmove', e => { if (!lpT) return; const p = e.touches[0]; if (Math.hypot(p.clientX - lpX, p.clientY - lpY) > 10) cancelLP(); }, { passive: true });
    container.addEventListener('touchend', cancelLP); container.addEventListener('touchcancel', cancelLP);
    container.addEventListener('contextmenu', e => { const el = e.target.closest(sel); if (!el || el.classList.contains('selectable')) return; e.preventDefault(); cancelLP(); cb(el); });
  }
  const ctx = $('#ctx'), ctxMenu = ctx.querySelector('.ctx-menu');
  const MI = {
    copy: ICON.copy, regen: ICON.regen, edit: ICON.edit, trash: ICON.trash,
    share: svg('<path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/>'),
    select: svg('<path d="M5 4h4M5 20h4M7 4v16M13 8h7M13 12h7M13 16h5"/>'),
    pin: svg('<path d="M9 4h6l-1 6 3 3H7l3-3Z"/><path d="M12 13v7"/>'),
    send: svg('<path d="M12 19V5M5 12l7-7 7 7"/>'),
    archive: svg('<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11h14V8M10 12h4"/>')
  };
  function showMenu(el, items, opts = {}) {
    ctxMenu.innerHTML = '';
    if (opts.title) { const t = document.createElement('div'); t.className = 'ctx-title'; t.textContent = opts.title; ctxMenu.appendChild(t); }
    items.forEach(it => {
      const b = document.createElement('button'); b.type = 'button'; b.setAttribute('role', 'menuitem'); b.className = it.danger ? 'danger' : '';
      b.innerHTML = `<span></span>${MI[it.icon] || ''}`; b.firstChild.textContent = it.label;
      b.onclick = () => { hideMenu(); setTimeout(it.act, 60); };
      ctxMenu.appendChild(b);
    });
    ctx.querySelector('.ctx-clone')?.remove();
    ctx.className = opts.sheet ? 'as' : '';
    ctx.hidden = false;
    if (el && !opts.sheet) {
      const r = el.getBoundingClientRect(), H = innerHeight, W = innerWidth;
      const clone = el.cloneNode(true); clone.classList.remove('pressing'); clone.classList.add('ctx-clone');
      const maxH = Math.min(r.height, H * .5);
      Object.assign(clone.style, { left: r.left + 'px', top: r.top + 'px', width: r.width + 'px', maxHeight: maxH + 'px' });
      ctx.insertBefore(clone, ctxMenu);
      const mh = items.length * 44 + 2, below = r.top + maxH + 10 + mh < H - 20;
      let top = below ? r.top + maxH + 10 : r.top - mh - 10;
      if (top < 20) { top = Math.max(20, H - mh - 30); clone.style.top = Math.max(20, top - maxH - 10) + 'px'; }
      const left = Math.min(Math.max(16, (el.closest('.msg.user') ? r.right - 250 : r.left)), W - 266);
      Object.assign(ctxMenu.style, { top: top + 'px', left: left + 'px', transformOrigin: (below ? 'top ' : 'bottom ') + (left > W / 2 - 125 ? 'right' : 'left') });
    } else Object.assign(ctxMenu.style, { top: '', left: '', transformOrigin: '' });
    requestAnimationFrame(() => ctx.classList.add('show'));
  }
  function hideMenu() { ctx.classList.remove('show'); setTimeout(() => { if (!ctx.classList.contains('show')) ctx.hidden = true; }, 190); }
  ctx.addEventListener('click', e => { if (!e.target.closest('.ctx-menu button')) hideMenu(); });
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape' || e.isComposing) return;
    if (!ctx.hidden) return hideMenu();
    if (controller && !document.querySelector('dialog[open], .mini-sheet:not([hidden])')) { e.preventDefault(); stopGeneration(); }
  });

  const msgIndex = msg => [...box.querySelectorAll('.msg.user,.msg.assistant')].indexOf(msg);
  const share = text => navigator.share({ text }).catch(() => {});
  longPress(box, '.codeblock, .msg.user .bubble, .msg.assistant .bubble', el => {
    if (el.classList.contains('codeblock')) {
      const code = el.querySelector('code').textContent;
      return showMenu(el, [{ label: '코드 복사', icon: 'copy', act: () => copyText(null, code) }, ...(navigator.share ? [{ label: '공유', icon: 'share', act: () => share(code) }] : [])]);
    }
    const c = cur(); const msg = el.closest('.msg'); const i = msgIndex(msg); const m = c?.messages[i]; if (!m) return;
    if (m.role === 'user') return showMenu(el, [
      { label: '복사', icon: 'copy', act: () => copyText(null, m.content) },
      ...(mode === 'server' ? [] : [
      { label: '수정 후 다시 보내기', icon: 'edit', act: () => { if (controller) controller.abort(); c.messages.splice(i); persist(); renderAll(); input.value = m.content; grow(); input.focus(); } },
      { label: '삭제', icon: 'trash', danger: true, act: () => { const n = c.messages[i + 1]?.role === 'assistant' ? 2 : 1; c.messages.splice(i, n); persist(); renderAll(); } }])
    ]);
    const answer = splitThink(m.content).answer.trim(); const isLast = i === c.messages.length - 1;
    showMenu(el, [
      { label: '복사', icon: 'copy', act: () => copyText(null, answer) },
      ...(isLast && !controller && !c.archived ? [{ label: '다시 생성', icon: 'regen', act: regenerate }] : []),
      ...(navigator.share ? [{ label: '공유', icon: 'share', act: () => share(answer) }] : []),
      { label: '텍스트 선택', icon: 'select', act: () => { el.classList.add('selectable'); const off = ev => { if (!el.contains(ev.target)) { el.classList.remove('selectable'); document.removeEventListener('touchstart', off); document.removeEventListener('mousedown', off); } }; setTimeout(() => { document.addEventListener('touchstart', off, { passive: true }); document.addEventListener('mousedown', off); }, 0); } }
    ]);
  });
  longPress(ul, '.row', row => {
    const c = convOf(row); if (!c) return; closeSwipe();
    showMenu(row, [
      { label: '이름 변경', icon: 'edit', act: () => renameConv(c) },
      { label: c.pinned ? '고정 해제' : '고정', icon: 'pin', act: () => { c.pinned = !c.pinned; const ps = pinSet(); c.pinned ? ps.add(c.id) : ps.delete(c.id); save(LS.pins, [...ps]); persist(); renderList(); } },
      { label: '보관', icon: 'archive', act: () => archiveConv(c) },
      ...(mode === 'local' ? [{ label: '삭제', icon: 'trash', danger: true, act: () => confirmDelete(c) }] : [])
    ]);
  });
  longPress($('#archList'), '.row', row => {
    const c = convOf(row); if (!c) return; closeSwipe();
    showMenu(row, [{ label: '복원', icon: 'archive', act: () => restoreConv(c) }, ...(mode === 'local' ? [{ label: '삭제', icon: 'trash', danger: true, act: () => confirmDelete(c) }] : [])]);
  });

  /* ---------- Tailscale identity (/whoami) ---------- */
  const authEl = $('#authNotice');
  let authRetry = null;
  function renderWho() {
    const el = $('#sWho'); if (!el) return;
    const who = whoami && (whoami.user || whoami.login);
    el.textContent = who ? `${who} 계정으로 연결됨` : '';
    el.hidden = !who;
  }
  function showAuthNotice(retry, code) {
    const denied = code === 'identity_not_allowed';
    $('#authTitle').textContent = denied ? '허용되지 않은 Tailscale 계정이에요' : 'Tailscale 연결을 확인하세요';
    $('#authBody').textContent = denied ? '이 Tailscale 계정은 이 서버를 쓸 수 없어요. 허용된 계정으로 로그인한 뒤 다시 시도하세요.'
      : '이 기기에서 Tailscale이 켜져 있고 로그인되어 있어야 서버에 연결할 수 있어요.';
    if (retry) authRetry = retry;
    if (!authEl.hidden) return;
    authEl.hidden = false; requestAnimationFrame(() => authEl.classList.add('in'));
  }
  function hideAuthNotice() { authEl.classList.remove('in'); authEl.hidden = true; }
  async function checkAuth() {
    try {
      const r = await fetch(apiBase() + '/whoami', { cache: 'no-store' });
      const j = await r.json().catch(() => null);
      if (r.status === 401 || (r.ok && j && j.authenticated === false)) { whoami = null; renderWho(); showAuthNotice(null, j?.error?.code); return false; }
      if (r.ok) { whoami = j; renderWho(); }
      hideAuthNotice(); return true;
    } catch { return true; }   // offline / network error: chat path reports it
  }
  $('#authRetry').onclick = async () => {
    const b = $('#authRetry'); b.disabled = true; b.textContent = '확인 중…';
    const ok = await checkAuth(); b.disabled = false; b.textContent = '다시 시도';
    if (ok && authRetry) { const f = authRetry; authRetry = null; clearErrors(); f(); }
  };

  /* ---------- sheets (§6) ---------- */
  const dlg = $('#settings'), sform = $('#settingsForm');
  const SHEET_EASE = 'cubic-bezier(.32,.72,0,1)';
  function sheetDrag(sheet, scrollEl, onClose) {
    let s = null;
    sheet.addEventListener('touchstart', e => {
      const t = e.touches[0], r = sheet.getBoundingClientRect();
      const onHead = t.clientY - r.top < 56 || e.target.closest('.grabber,.sheet-head');
      if (!onHead && (scrollEl ? scrollEl.scrollTop > 0 : true)) return;
      if (e.target.closest('input,textarea,select') && !onHead) return;
      s = { y0: t.clientY, t0: performance.now(), yl: t.clientY, tl: performance.now(), v: 0, dy: 0, h: sheet.offsetHeight, lock: null, x0: t.clientX, head: !!onHead };
    }, { passive: true });
    sheet.addEventListener('touchmove', e => {
      if (!s) return; const t = e.touches[0], dy = t.clientY - s.y0;
      if (!s.lock) { if (Math.hypot(dy, t.clientX - s.x0) < 6) return; s.lock = Math.abs(dy) > Math.abs(t.clientX - s.x0) && (dy > 0 || s.head) ? 'y' : 'n'; if (s.lock === 'y') sheet.style.transition = 'none'; }
      if (s.lock !== 'y') return; e.preventDefault();
      const now = performance.now(); s.v = (t.clientY - s.yl) / Math.max(1, now - s.tl); s.yl = t.clientY; s.tl = now;
      s.dy = dy; const y = dy < 0 ? dy * .2 : dy;
      sheet.style.transform = `translateY(${y}px)`;
      document.body.style.setProperty('--sheet-p', String(1 - Math.max(0, dy) / s.h));
    }, { passive: false });
    const end = () => {
      if (!s) return; const st = s; s = null; if (st.lock !== 'y') return;
      const v = performance.now() - st.tl > 100 ? 0 : st.v;   // release velocity, not average
      document.body.style.removeProperty('--sheet-p');
      if (st.dy > st.h * .3 || v > .6) onClose(true);
      else { sheet.style.transition = `transform 300ms cubic-bezier(.34,1.36,.64,1)`; sheet.style.transform = ''; }
    };
    sheet.addEventListener('touchend', end); sheet.addEventListener('touchcancel', end);
  }
  function animateOut(sheet, done) {
    sheet.style.transition = `transform 300ms ${SHEET_EASE}`; sheet.style.transform = 'translateY(100%)';
    sheet.classList.add('closing');
    setTimeout(() => { sheet.classList.remove('closing'); sheet.style.transition = sheet.style.transform = ''; done(); }, 300);
  }
  let snap = '';
  const formState = () => JSON.stringify([$('#sBase').value, $('#sModel').value, $('#sSystem').value, $('#sShowThink').checked, $('#sNoThink').checked]);
  function closeSettings(dragged) {
    if (dragged && formState() !== snap) {
      dlg.style.transition = `transform 300ms cubic-bezier(.34,1.36,.64,1)`; dlg.style.transform = '';
      return showMenu(null, [{ label: '변경 사항 폐기', danger: true, act: () => animateOut(dlg, () => dlg.close()) }, { label: '계속 편집', act: () => {} }], { sheet: true });
    }
    animateOut(dlg, () => dlg.close());
  }
  sheetDrag(dlg, sform, closeSettings);
  dlg.addEventListener('cancel', e => { e.preventDefault(); closeSettings(); });
  dlg.addEventListener('close', () => { document.body.classList.remove('sheet-open'); maybeA2HS(); });
  dlg.addEventListener('click', e => { if (e.target === dlg) closeSettings(true); });

  function setModelOptions(list) {
    const sel = $('#sModel'); sel.innerHTML = '';
    const ids = list.length ? list : (settings.model ? [settings.model] : []);
    ids.forEach(id => { const o = document.createElement('option'); o.value = id; o.textContent = id.split('/').pop(); o.title = id; sel.appendChild(o); });
    if (settings.model && ids.includes(settings.model)) sel.value = settings.model;
  }
  async function loadModels() {
    const st = $('#sStatus'); st.className = 'status'; st.textContent = '모델 목록 불러오는 중…';
    const base = normBase($('#sBase').value);
    try {
      const r = await fetch(base + '/v1/models');
      if (!r.ok) {
        const body = await r.text().catch(() => '');
        if (r.status === 401) { let code; try { code = JSON.parse(body).error?.code; } catch {} showAuthNotice(loadModels, code); }
        throw Object.assign(new Error(errMsg(r.status, body)), { http: r.status });
      }
      const j = await r.json(); const ids = (j.data || []).map(m => m.id);
      setModelOptions(ids); st.textContent = `연결 성공 · 모델 ${ids.length}개`;
    } catch (e) { st.className = 'status err'; st.textContent = e.http ? e.message : '연결 실패: ' + e.message; }
  }
  function openSettings() {
    renderSync(); { const mg = localStorage.getItem(LS.migrated); $('#sMigrateRow').hidden = !(mode === 'server' && localConvs().length && (!mg || mg === 'skip')); }
    $('#sBase').value = settings.base; $('#sSystem').value = settings.system;
    $('#sShowThink').checked = settings.showThink; $('#sNoThink').checked = !!settings.noThink;
    setModelOptions([]); $('#sStatus').textContent = '';
    $('#a2hsRow').hidden = isStandalone();
    snap = formState();
    document.body.classList.add('sheet-open'); dlg.showModal(); sform.scrollTop = 0;
    renderWho(); loadModels();
  }
  $('#openSettings').onclick = openSettings;
  $('#sMigrate').onclick = () => animateOut(dlg, () => { dlg.close(); localStorage.removeItem(LS.migrated); save(LS.snooze, { until: 0, n: 0 }); openMigrate(); });
  $('#sSyncNow').onclick = () => { outbox.forEach(o => o.nextAt = 0); obFailed = 0; flushOutbox(); initServer(); };
  $('#loadModels').onclick = loadModels;
  $('#cancelSettings').onclick = () => closeSettings();
  $('#showA2hs').onclick = () => animateOut(dlg, () => { dlg.close(); openA2HS(true); });
  sform.addEventListener('submit', () => {
    settings = { noThink: $('#sNoThink').checked, base: normBase($('#sBase').value), model: $('#sModel').value || DEFAULT_MODEL, system: $('#sSystem').value, showThink: $('#sShowThink').checked };
    save(LS.settings, settings); renderMessages();
  });

  /* ---------- add to home screen (§11) ---------- */
  const a2 = $('#installSheet'); let bip = null, a2Scrim = null;
  window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); bip = e; maybeA2HS(); });
  window.addEventListener('appinstalled', () => { localStorage.setItem('a2hs.installed', '1'); closeA2HS(); });
  if (isStandalone()) localStorage.setItem('a2hs.installed', '1');
  const visits = (+localStorage.getItem('visits') || 0) + 1; localStorage.setItem('visits', visits);
  function a2Eligible() {
    if (isStandalone() || localStorage.getItem('a2hs.installed')) return false;
    if (Date.now() - (+localStorage.getItem('a2hs.dismissed') || 0) < 30 * 864e5) return false;
    if (!(isIOS || bip)) return false;
    return visits >= 2 || convs.some(c => c.messages.some(m => m.role === 'assistant'));
  }
  let a2Timer = 0;
  function maybeA2HS() { clearTimeout(a2Timer); a2Timer = setTimeout(() => { if (a2Eligible() && !dlg.open && a2.hidden && !controller) openA2HS(); }, 1200); }
  function openA2HS(manual) {
    a2.classList.toggle('bip', !!bip && !isIOS); const ipad = isIOS && !/iPhone|iPod/.test(navigator.userAgent); a2.classList.toggle('ipad', ipad);
    if (ipad) $('#installSheet .step-share').innerHTML = '주소창 옆 <b>공유</b> 버튼(또는 ··· → 공유)을 누르고';
    a2Scrim = document.createElement('div'); a2Scrim.className = 'sheet-scrim'; a2Scrim.onclick = () => closeA2HS(true); document.body.appendChild(a2Scrim);
    a2.hidden = false; a2.dataset.manual = manual ? '1' : '';
    requestAnimationFrame(() => requestAnimationFrame(() => { a2.classList.add('show'); a2Scrim.classList.add('show'); }));
  }
  function closeA2HS(dismissed) {
    if (a2.hidden) return;
    if (dismissed && !a2.dataset.manual) localStorage.setItem('a2hs.dismissed', String(Date.now()));
    a2.classList.remove('show'); a2Scrim?.classList.remove('show');
    a2.style.transition = `transform 300ms ${SHEET_EASE}`; a2.style.transform = 'translateY(110%)';
    setTimeout(() => { a2.hidden = true; a2.style.transition = a2.style.transform = ''; a2Scrim?.remove(); a2Scrim = null; }, 300);
  }
  sheetDrag(a2, null, () => closeA2HS(true));
  $('#installLater').onclick = () => closeA2HS(true);
  $('#installBtn').onclick = async () => { if (!bip) return; bip.prompt(); const r = await bip.userChoice.catch(() => null); bip = null; if (r?.outcome === 'accepted') localStorage.setItem('a2hs.installed', '1'); closeA2HS(r?.outcome !== 'accepted'); };

  /* ---------- mini sheets: rename / 👎 reason / migration ---------- */
  const minis = new Map();
  function openMini(sh, opts = {}) {
    if (!sh.hidden) return;
    const scrim = document.createElement('div'); scrim.className = 'sheet-scrim'; scrim.onclick = () => { if (!sh.dataset.lock) (opts.onDismiss || (() => closeMini(sh)))(); };
    document.body.appendChild(scrim); minis.set(sh, scrim);
    sh.hidden = false; requestAnimationFrame(() => requestAnimationFrame(() => { sh.classList.add('show'); scrim.classList.add('show'); }));
  }
  function closeMini(sh) {
    if (sh.hidden) return; const scrim = minis.get(sh); minis.delete(sh);
    if (document.activeElement && sh.contains(document.activeElement)) document.activeElement.blur();
    sh.classList.remove('show'); scrim?.classList.remove('show');
    sh.style.transition = `transform 300ms ${SHEET_EASE}`; sh.style.transform = 'translateY(110%)';
    setTimeout(() => { sh.hidden = true; sh.style.transition = sh.style.transform = ''; scrim?.remove(); }, 300);
  }
  ['#renameSheet'].forEach(id => sheetDrag($(id), null, () => closeMini($(id))));
  // rename from chat title (THREADS-SPEC §2.3)
  function openRenameSheet(c) {
    if (!c) return; const sh = $('#renameSheet'), inp = $('#titleEdit');
    inp.value = c.title; openMini(sh); setTimeout(() => { inp.focus(); inp.select(); }, 60);
    const ok = () => { const v = inp.value.trim(); closeMini(sh); if (v && v !== c.title) updateThread(c, { title: v }); };
    $('#renameSave').onclick = ok; $('#renameCancel').onclick = () => closeMini(sh);
    inp.onkeydown = e => { if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); ok(); } if (e.key === 'Escape') closeMini(sh); };
  }
  $('#titleWrap').addEventListener('click', () => { const c = cur(); if (c && (c.messages.length || c.srv) && !c.archived) openRenameSheet(c); });
  $('#archRestore').onclick = () => { const c = cur(); if (c) restoreConv(c); };

  /* migration: local → server, once (THREADS-SPEC §4) */
  const localConvs = () => load(LS.convs, []).filter(c => c.messages?.length);
  function migrateEligible() {
    if (mode !== 'server' || localStorage.getItem(LS.migrated)) return false;
    const sn = load(LS.snooze, { until: 0, n: 0 }); if (sn.n >= 3 || Date.now() < sn.until) return false;
    return localConvs().length > 0;
  }
  let migrateAsked = false;
  function maybeMigrate() {
    if (migrateAsked || !migrateEligible()) return;
    const show = () => { if (migrateAsked || app.dataset.route !== 'list' && !wide.matches || controller || dlg.open) return; migrateAsked = true; setTimeout(openMigrate, 1000); };
    if (app.dataset.route === 'list' || wide.matches) show(); else { const mo = new MutationObserver(() => { if (app.dataset.route === 'list') { mo.disconnect(); show(); } }); mo.observe(app, { attributes: true, attributeFilter: ['data-route'] }); }
  }
  function toImport(c) {
    const base = (c.created || c.updated || Date.now()) - c.messages.length * 1000;
    return { client_id: 'local:' + c.id, title: c.title || '대화', created_at: new Date(base).toISOString(), archived: !!c.archived,
      messages: c.messages.filter(m => m.role === 'user' || m.role === 'assistant').map((m, i) => {
        const o = { client_id: `local:${c.id}:${i}`, role: m.role, created_at: new Date(m.created || base + i * 1000).toISOString() };
        if (m.role === 'assistant') { const st = splitThink(m.content || ''); o.content = st.answer; if (st.think) o.reasoning = st.think; o.model = settings.model || DEFAULT_MODEL; }
        else o.content = m.content || '';
        return o;
      }) };
  }
  let migFailed = [];
  function migView(v, data = {}) {
    const sh = $('#migrateSheet'); sh.dataset.view = v;
    if (v === 'ask') {
      const l = localConvs(), n = l.reduce((a, c) => a + c.messages.length, 0), kb = new Blob([localStorage.getItem(LS.convs) || '']).size / 1024;
      $('#migSub').textContent = `이 기기에 있는 대화 ${l.length}개를 서버로 옮기면 다른 기기에서도 이어서 볼 수 있어요.`;
      $('#migStats').textContent = `대화 ${l.length}개 · 메시지 ${n}개 · 약 ${kb >= 1024 ? (kb / 1024).toFixed(1) + 'MB' : Math.max(1, Math.round(kb)) + 'KB'}`;
    }
    if (v === 'progress') { const p = data.done / Math.max(1, data.total); $('#migRing').style.strokeDashoffset = String(138 * (1 - p)); $('#migProgText').textContent = `${data.total}개 중 ${data.done}개 저장 중…`; $('#migBar').style.width = (p * 100) + '%'; }
    if (v === 'done') $('#migDoneText').textContent = `대화 ${data.ok}개를 옮겼어요`;
    if (v === 'partial') {
      $('#migPartText').textContent = data.ok ? `${data.ok}개를 옮겼어요. ${data.fail.length}개는 실패했어요` : '지금은 옮길 수 없어요';
      $('#migFailList').innerHTML = data.fail.slice(0, 3).map(f => `<li><b>${escapeHtml(f.title)}</b><small>${escapeHtml(f.reason)}</small></li>`).join('') + (data.fail.length > 3 ? `<li class="more">+${data.fail.length - 3}</li>` : '');
    }
  }
  function openMigrate() { migView('ask'); openMini($('#migrateSheet'), { onDismiss: snoozeMigrate }); }
  function snoozeMigrate() { const sn = load(LS.snooze, { until: 0, n: 0 }); save(LS.snooze, { until: Date.now() + 3 * 864e5, n: sn.n + 1 }); closeMini($('#migrateSheet')); }
  async function runMigration(only) {
    const sh = $('#migrateSheet'); sh.dataset.lock = '1';
    const all = localConvs(), todo = only ? all.filter(c => only.includes(c.id)) : all;
    migrateProg = { done: 0, total: todo.length }; migView('progress', migrateProg); renderSync();
    const ok = new Set(), fail = [];
    for (let i = 0; i < todo.length; i += 5) {      // batches of 5 (also kept under ~4.5MB)
      let batch = todo.slice(i, i + 5);
      const send = async items => {
        const body = JSON.stringify({ threads: items.map(toImport) });
        if (new Blob([body]).size > 4.5e6 && items.length > 1) { const h = Math.ceil(items.length / 2); await send(items.slice(0, h)); return send(items.slice(h)); }
        try {
          const j = await api('/v1/threads/import', { method: 'POST', body });
          const res = j?.results || (j?.mapping || []).map(m => ({ client_id: m.client_id, thread_id: m.id, status: 'created' }));
          items.forEach(c => { const r = res.find(x => x.client_id === 'local:' + c.id); if (r && (r.status === 'created' || r.status === 'exists' || r.thread_id)) ok.add(c.id); else fail.push({ id: c.id, title: c.title, reason: r?.error?.message || r?.status || '응답에 결과가 없어요' }); });
        } catch (e) {
          // the whole batch is rejected on 400/413: bisect so one bad conversation doesn't fail its neighbours
          if ((e.http === 400 || e.http === 413) && items.length > 1) { const h = Math.ceil(items.length / 2); await send(items.slice(0, h)); return send(items.slice(h)); }
          items.forEach(c => fail.push({ id: c.id, title: c.title, reason: isNet(e) ? '네트워크 연결 없음' : e.http === 413 ? '대화가 너무 커요' : e.message }));
        }
      };
      await send(batch);
      migrateProg.done = Math.min(todo.length, i + batch.length); migView('progress', migrateProg); renderSync();
    }
    migrateProg = null; delete sh.dataset.lock; renderSync();
    const prevOk = all.length - todo.length;   // retry: earlier items already succeeded
    migFailed = fail.map(f => f.id);
    if (!fail.length) {
      localStorage.setItem(LS.migrated, String(Date.now()));
      save(LS.bak, { at: Date.now(), data: load(LS.convs, []) }); localStorage.removeItem(LS.convs);
      migView('done', { ok: ok.size + prevOk }); initServer();
    } else migView('partial', { ok: ok.size + prevOk, fail });
    if (sh.hidden && fail.length) showToast(`${fail.length}개 대화를 옮기지 못했어요`, '다시 시도', () => { openMini(sh); runMigration(migFailed); }, 5000);
  }
  $('#migGo').onclick = () => runMigration();
  $('#migLater').onclick = snoozeMigrate;
  $('#migSkip').onclick = () => { localStorage.setItem(LS.migrated, 'skip'); closeMini($('#migrateSheet')); };
  $('#migBg').onclick = () => closeMini($('#migrateSheet'));
  $('#migDone').onclick = () => closeMini($('#migrateSheet'));
  $('#migRetry').onclick = () => runMigration(migFailed);
  $('#migLater2').onclick = () => closeMini($('#migrateSheet'));
  // purge the 7-day backup
  { const b = load(LS.bak, null); if (b && Date.now() - b.at > 7 * 864e5) localStorage.removeItem(LS.bak); }

  /* ---------- offline banner / toast ---------- */
  const setOffline = off => { chatView.classList.toggle('offline', off); app.classList.toggle('offline', off); };
  window.addEventListener('online', () => { setOffline(false); flushOutbox(); initServer(); }); window.addEventListener('offline', () => setOffline(true));
  setOffline(navigator.onLine === false);
  const toast = $('#toast'); let toastT = 0;
  function showToast(text, act, fn, ms) {
    $('#toastText').textContent = text; const b = $('#toastAct'); b.textContent = act || ''; b.hidden = !act; b.onclick = () => { hideToast(); fn && fn(); };
    toast.hidden = false; requestAnimationFrame(() => toast.classList.add('show'));
    clearTimeout(toastT); if (ms) toastT = setTimeout(hideToast, ms);
  }
  function hideToast() { toast.classList.remove('show'); setTimeout(() => { if (!toast.classList.contains('show')) toast.hidden = true; }, 300); }

  /* ---------- state restore (§10) ---------- */
  function saveDraft() { if (!currentId) return; const v = input.value; if (v) localStorage.setItem(LS.draft + currentId, v); else localStorage.removeItem(LS.draft + currentId); }
  function loadDraft() { input.value = (currentId && localStorage.getItem(LS.draft + currentId)) || ''; grow(); }
  let draftT = 0; input.addEventListener('input', () => { clearTimeout(draftT); draftT = setTimeout(saveDraft, 300); });
  function saveState() { saveDraft(); save(LS.route, app.dataset.route); if (currentId) { const sc = load(LS.scroll, {}); sc[currentId] = stick ? -1 : box.scrollTop; save(LS.scroll, sc); } }
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') { saveState(); commitArchive(); } else { swReg?.update().catch(() => {}); flushOutbox(); } });
  window.addEventListener('pagehide', () => { saveState(); commitArchive(); });

  /* ---------- boot ---------- */
  const params = new URLSearchParams(location.search);
  const hm = location.hash.match(/^#\/c\/(.+)$/);
  let route = load(LS.route, 'chat');
  if (hm && convs.some(c => c.id === hm[1])) { currentId = hm[1]; route = 'chat'; } else if (location.hash === '#/' || location.hash === '#/archive') route = 'list';
  if (route === 'archive') route = 'list';
  if (currentId && !cur()) currentId = convs[0]?.id || null;
  if (!cur() && convs.length && route === 'chat') currentId = convs[0].id;
  if (params.has('new')) route = 'chat';
  history.replaceState({ route: 'list' }, '', location.pathname + '#/');
  renderAll(); loadDraft();
  if (params.has('new')) newConv();
  else if (route === 'chat') { history.pushState({ route: 'chat', id: currentId }, '', hashFor('chat')); setRoute('chat'); }
  else setRoute('list');
  const sc = currentId && load(LS.scroll, {})[currentId];
  if (sc > 0) requestAnimationFrame(() => requestAnimationFrame(() => { box.scrollTop = sc; stick = false; }));
  requestAnimationFrame(() => app.classList.add('ready'));
  grow();
  if (cur()) ensureMessages(cur());
  renderSync();
  checkAuth().then(ok => { if (ok) maybeA2HS(); initServer(); });

  const APP_VERSION = '1.0.2'; console.info('[llmchat] app', APP_VERSION);
  /* ---------- service worker (HTTPS / localhost only; app works without it) ---------- */
  let swReg = null, reloading = false, wantReload = !!(navigator.serviceWorker && navigator.serviceWorker.controller);
  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.register('/ui/sw.js', { scope: '/ui/' }).then(reg => {
      swReg = reg;
      const ask = () => { const sw = navigator.serviceWorker.controller; if (!sw) return; const ch = new MessageChannel(); ch.port1.onmessage = e => { const v = e.data && e.data.version; console.info('[llmchat] sw', v); const el = document.getElementById('appVersion'); if (el && v) el.textContent = 'v' + APP_VERSION + ' · SW ' + v.replace('llmchat-', ''); }; sw.postMessage('GET_VERSION', [ch.port2]); };
      ask(); navigator.serviceWorker.addEventListener('controllerchange', ask);
      const offer = w => { wantReload = true; w.postMessage('SKIP_WAITING'); };   // v11: no tap needed, reload once
      reg.update?.().catch(() => {});
      if (reg.waiting && navigator.serviceWorker.controller) offer(reg.waiting);
      reg.addEventListener('updatefound', () => { const w = reg.installing; w && w.addEventListener('statechange', () => { if (w.state === 'installed' && navigator.serviceWorker.controller) offer(w); }); });
    }).catch(() => {});
    navigator.serviceWorker.addEventListener('controllerchange', () => { if (wantReload && !reloading) { reloading = true; location.reload(); } });
  }
  window.__app = { version: APP_VERSION, msgs: () => cur()?.messages, showToast, go, isStandalone, state: () => ({ mode, outbox: outbox.length, convs: convs.length, currentId }) };
})();
