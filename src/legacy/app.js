import { createClient, authCode, isAuthFail, headers, normBase } from '../api/client.js';
import { createThreadModels, toMs, scrubAction } from '../api/thread-models.js';
import { createOperations } from '../api/operations.js';
import { createOutbox } from '../features/conversations/outbox.js';
import { el as mkEl } from '../shared/dom.js';
import { icon } from '../lib/icons.js';
import { renderMarkdown } from '../lib/markdown.js';
import { stableCut } from '../lib/markdown-stream.js';
import { prepareSources, renderSourceHtml } from '../lib/sources.js';
import { freshNote, mapTools, renderToolQueries, toolFailKey, TOOL_FAIL } from '../lib/tool-status.js';
import { escapeHtml } from '../lib/text.js';
import { srcDate, srcDomain } from '../lib/citations.js';
import { createSSEParser } from '../lib/sse.js';
import { splitThink, stripStopMark } from '../lib/think.js';
'use strict';
let _srcSeq = 0;
function renderSources(sources, tools) {
  const model = prepareSources(sources, tools);
  return model ? renderSourceHtml(model, 'src' + (++_srcSeq)) : '';
}
export const browserHelpers = { createSSEParser, splitThink, renderMarkdown, renderSources, srcDate, renderToolQueries, toolFailKey, TOOL_FAIL, escapeHtml, stableCut, stripStopMark };

/* ---------- app ---------- */
export function boot({ ProactiveAPI, Proactive, Pim, Memory, Today }) {
  const $ = s => document.querySelector(s);
  let PRO = null;   // proactive.js (선톡 P1); null if the script failed to load
  let MEM = null;   // memory.js (Part B); null unless the 'eve.flag.memory' flag is on
  const svg = d => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;   // only for glyphs not in the sprite
  const ICON = {
    copy: icon('copy'), globe: icon('source'), check: icon('check'), regen: icon('regenerate'), warn: icon('warning'),
    chev: icon('chevron-right', 'chev'), spark: icon('sparkle'), edit: icon('edit'), up: icon('thumb-up'), down: icon('thumb-down'), trash: icon('trash')
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
  const apiBase = () => normBase(settings.base);
  // CSRF: the gateway requires X-Eve-Request: 1 + an allow-listed Origin on every POST/PUT/PATCH/DELETE (403 {error_code:'invalid'}).
  // Every request (fetch in api(), chat completions) builds its headers here. No Authorization: gateway trusts Tailscale identity.
  let whoami = null;
  const shortModel = () => (settings.model || '').split('/').pop();
  const isTouch = matchMedia('(pointer:coarse)').matches;
  const box = $('#messages'), input = $('#input'), sendBtn = $('#sendBtn');
  /* AUTO-TOOLS (eve-serving #134 r4): the request carries NO web_search field. Whether Eve searches is decided server-side, so there is no
     web-search toggle / mode menu in the composer any more. The two old localStorage keys (mode, one-time hint) are removed once. */
  try { localStorage.removeItem('llmchat.webSearch'); localStorage.removeItem('llmchat.autoHintSeen'); } catch {}

  /* ---------- viewport / keyboard (NATIVE §9) ---------- */
  const root = document.documentElement.style;
  const vv = window.visualViewport;
  // 1.2.2 (REFRESH-SPEC M1 / §3.4): while the keyboard moves only --kb changes (composer + toBottom follow via translate, no layout);
  // the layout height --vvh is committed once, 150ms after visualViewport resize stops, then scrollBottom once.
  let vvRaf = 0, vvT = 0, vvH = window.innerHeight;
  function commitVV() {
    vvT = 0; const h = vv ? vv.height : window.innerHeight;
    root.setProperty('--vvh', h + 'px'); root.setProperty('--kb', '0px'); vvH = h;
    const wasKb = document.body.classList.contains('kb-open'), kb = window.innerHeight - h > 120;
    document.body.classList.toggle('kb-open', kb);
    if (kb && !wasKb && document.activeElement?.classList.contains('fbp-input')) document.activeElement.scrollIntoView({ block: 'nearest' });   // N2: keep note above keyboard
    if (window.scrollY) window.scrollTo(0, 0);
    if (stick) scrollBottom();
  }
  function syncVV() {
    if (!vvRaf) vvRaf = requestAnimationFrame(() => {
      vvRaf = 0; const h = vv ? vv.height : window.innerHeight;
      root.setProperty('--kb', Math.max(0, vvH - h) + 'px');
    });
    clearTimeout(vvT); vvT = setTimeout(commitVV, 150);
  }
  window.__vv = { commit: () => { clearTimeout(vvT); commitVV(); } };   // tests
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
  const buzz = n => { if (self.EveShell?.haptic(n <= 10 ? 'light' : n <= 20 ? 'medium' : 'heavy')) return; if (!isIOS && navigator.vibrate) try { navigator.vibrate(n); } catch {} };   // 1.7.0: iOS shell haptics when bridged
  let chatFrom = 'today';
  const wide = matchMedia('(min-width: 761px)');
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');

  /* ---------- scroll ---------- */
  let stick = true;
  function scrollBottom(smooth) { const top = box.scrollHeight; box.scrollTo({ top, behavior: smooth ? 'smooth' : 'auto' }); }
  // 1.2.2 (M2): streaming scroll at most every 100ms; the read (scrollHeight) happens in its own rAF before the write
  let sbLast = 0, sbT = 0;
  function scrollBottomThrottled() {
    if (sbT) return;
    const wait = Math.max(0, 100 - (performance.now() - sbLast));
    sbT = setTimeout(() => requestAnimationFrame(() => { sbT = 0; sbLast = performance.now(); if (stick) scrollBottom(); }), wait);
  }
  box.addEventListener('scroll', () => {
    const d = box.scrollHeight - box.scrollTop - box.clientHeight;
    stick = d < 80;
    $('#toBottom').classList.toggle('show', d > 200);
    $('#topbar').classList.toggle('scrolled', box.scrollTop > 4);
    if (box.scrollTop < 200) loadOlder();
  }, { passive: true });
  $('#toBottom').onclick = () => { stick = true; scrollBottom(true); };
  commitVV();

  /* ---------- server API (threads, THREADS-SPEC §0 / backend contract) ---------- */
  // 1.3.1: gateway #57 sends a disallowed tailnet identity as 403 identity_not_allowed (was 401); treat it as 401. Other 403s unchanged.
  const api = createClient({ apiBase, onAuthFail: code => { clearCards(); showAuthNotice(null, code); }, errorMessage: errMsg });
  const isNet = e => !e.http;                       // fetch failed: offline / unreachable
  const pinSet = () => new Set(load(LS.pins, []));
  // drop stored confirm-card contents (pending_actions) — on sign-out / identity loss (security review Low 2)
  function clearCards() {
    let n = 0; const strip = list => (list || []).forEach(c => (c.messages || []).forEach(m => { if (m.pendingActions) { delete m.pendingActions; n++; } }));
    strip(convs); try { const s = load(LS.srv, []); strip(s); save(LS.srv, s); } catch {}
    if (n) persist(); return n;
  }
  const { fromServerMsg, fromServerThread } = createThreadModels({ fields: ProactiveAPI?.FIELDS, pinSet, usageText });
  let listLoading = true, listError = false, loadT0 = 0, tDirtyT = 0, tSeen = false, msgsPending = 0, coldStart = false;   // 오늘 / 기록 loading state (declared before first use)
  const logSkel = () => coldStart && listLoading && Date.now() - loadT0 >= 250;
  let serverReady = false;   // threads loaded: a push-tap (nid) may open its thread now, not be overwritten by restore
  async function initServer() {
    listLoading = true; loadT0 = Date.now(); coldStart = !convs.length; listError = false; setTimeout(() => { todayDirty(); if (listLoading && listView.classList.contains('screen')) renderList(); }, 260); todayDirty();
    try {
      const j = await api('/v1/threads?limit=20&archived=false');
      const prev = mode === 'server' ? convs : [];
      const wasLocal = mode !== 'server';
      mode = 'server'; save(LS.mode, 'server'); persistOff = false;
      const liveC = mode === 'server' && controller && genId && cur()?.id === genId ? cur() : null;   // 1.10.2: an answer is streaming into this thread: keep its object and its live bubble
      const mapped = (j.data || []).map(t => { const o = prev.find(p => p.id === t.id); return liveC && o === liveC ? Object.assign(o, { title: t.title || o.title, archived: !!t.archived, srv: true, pinned: pinSet().has(t.id) }) : fromServerThread(t, o); });
      convs = prev.filter(c => c.fresh).concat(mapped); nextCursor = j.next_cursor || null;
      if (wasLocal || (currentId && !cur())) currentId = cur() ? currentId : null;
      persist(); if (liveC && cur() === liveC) renderList(); else renderAll(); loadDraft();
      if (cur() && !(liveC && cur() === liveC)) ensureMessages(cur());
      maybeMigrate(); flushOutbox(); fillListIfShort(); serverReady = true; PRO?.refresh(); pendRefresh(true); memRefresh(true); briefRefresh(true); MEM?.intro?.();
    } catch (e) {
      if (e.code === 'persistence_disabled' || e.http === 404 || (e.http === 503 && !e.code)) {
        persistOff = true;
        if (mode === 'server') { clearCards(); mode = 'local'; convs = load(LS.convs, []); if (!cur()) currentId = convs[0]?.id || null; renderAll(); loadDraft(); }
        save(LS.mode, 'local');
      }
      if (!persistOff) listError = true;
      renderSync();
    } finally { const wasCold = coldStart && listLoading; listLoading = false; todayDirty(); if (wasCold) renderList(); }
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
      if (c.messages.some(m => m.status === 'generating')) {   // §3.8: reopened mid-generation → partial content, re-poll with backoff
        c._gen = (c._gen || 0) + 1; if (c._gen < 40) setTimeout(() => { if (!controller) { c.loaded = false; ensureMessages(c); } }, Math.min(8000, 1000 * 2 ** Math.min(c._gen, 3)));
      } else c._gen = 0;
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
    if (currentId === old) { currentId = id; if (app.dataset.route === 'chat') history.replaceState({ route: 'chat', id, from: chatFrom }, '', '#/t/' + id); }
    if (genId === old) genId = id;
    const d = localStorage.getItem(LS.draft + old); if (d) { localStorage.setItem(LS.draft + id, d); localStorage.removeItem(LS.draft + old); }
    persist();
  }

  /* ---------- outbox (offline-first writes, backoff 2..60s, THREADS-SPEC §0) ---------- */
  let migrateProg = null;
  const runOp = createOperations(api);
  const { state: outboxState, saveOutbox, enqueue, scheduleOutbox, flushOutbox, write } = createOutbox({
    mode: () => mode, load, save, storageKey: LS.outbox, runOp, isNet,
    renderSync: () => renderSync(), fbReasonRejected: id => fbReasonRejected(id),
    showToast: (...args) => showToast(...args)
  });
  function renderSync() {
    const el = $('#syncStatus'); if (!el) return;
    let html = '';
    if (migrateProg) html = `<span class="spin"></span>대화 옮기는 중 ${migrateProg.done}/${migrateProg.total}`;
    else if (persistOff) html = mode === 'local' ? '서버 저장이 꺼져 있어 이 기기에만 저장돼요' : '서버 저장이 일시적으로 꺼져 있어요';
    else if (outboxState.failed) html = `<i class="dot bad"></i>${outboxState.failed}개 저장 실패 · <button type="button" class="sync-retry">다시 시도</button>`;
    else if (outboxState.items.length) html = `<i class="dot"></i>변경 사항 ${outboxState.items.length}개 대기 중`;
    el.innerHTML = html; el.hidden = !html;
    el.querySelector('.sync-retry')?.addEventListener('click', () => { outboxState.failed = 0; outboxState.items.forEach(o => o.nextAt = 0); flushOutbox(); });
    const ss = $('#sSync'); if (ss) ss.textContent = mode === 'server' ? (outboxState.items.length ? `대기 ${outboxState.items.length}개` : '서버에 저장 중') : '이 기기에만 저장';
  }

  /* ---------- conversation list (NATIVE §3, THREADS-SPEC §2) ---------- */
  const CHEV_R = icon('chevron-right', 'chev');
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
  function openConv(id) {
    if (id !== currentId) { saveDraft(); currentId = id; persist(); renderAll(); loadDraft(); }
    else renderMessages();
    ensureMessages(cur());
    go('chat');
  }
  function updateThread(c, patch) {
    const before = { title: c.title }; Object.assign(c, patch); persist(); renderList(); if (c === cur()) setConvTitle(c.title);
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
  const MARK = '<svg class="r-eve" viewBox="0 0 100 100" aria-hidden="true"><path d="M14 54V36a16 16 0 0 1 16-16h40a16 16 0 0 1 16 16v28a16 16 0 0 1-16 16H34" fill="none" stroke="currentColor" stroke-width="9"/><rect x="32" y="37" width="10" height="26" rx="5" fill="var(--brand)"/></svg>';
  const hasPro = c => (c.unread || 0) > 0 || (c.messages || []).some(m => m.origin === 'proactive');
  /* 1.10.0 B2 (DIRECTION-B §9.2): a row is  time(36px) · title + preview · [pill] [Eve mark]; rows of one day share a group card */
  function rowEl(c, cls = '', opts = {}) {
    const li = document.createElement('li'); li.className = 'row' + cls + (c.id === currentId ? ' active' : ''); li.dataset.id = c.id;
    const arch = cls.includes('archived');
    li.innerHTML = `<div class="row-actions">${arch ? '<button type="button" class="ra-restore" tabindex="-1">복원</button>' + (mode === 'local' ? '<button type="button" class="ra-del" tabindex="-1">삭제</button>' : '') : '<button type="button" class="ra-rename" tabindex="-1">이름 변경</button><button type="button" class="ra-archive" tabindex="-1">보관</button>'}</div>
      <div class="row-main"><time class="r-tm"></time><div class="r-bd"><div class="row-top"><span class="row-title"></span></div><div class="row-sub"></div></div></div>`;
    li.querySelector('.row-title').textContent = (c.pinned ? '📌 ' : '') + c.title;
    const tm = li.querySelector('time'), ts = c.updated || Date.now(); tm.textContent = opts.day && kstDay(ts) !== kstDay(Date.now()) ? shortDate(ts) : hhmm(ts); tm.dateTime = new Date(ts).toISOString();
    const sub = li.querySelector('.row-sub');
    PRO?.decorateRow(li, c);
    if (hasPro(c)) li.querySelector('.row-top').insertAdjacentHTML('beforeend', MARK);
    if (genId === c.id) sub.innerHTML = '<span class="spin" aria-hidden="true"></span>답변 중…'; else sub.textContent = opts.date ? daySepText(ts).replace(/ · .*/, '') + ' · ' + preview(c) : preview(c);
    return li;
  }
  const shortDate = t => { const [, m, d] = kstDay(t).split('-').map(Number); return `${m}.${d}`; };
  let wkDay = null;   // the day whose week the strip shows (= the date header at the top of the list)
  function renderWk() {
    const el = $('#wk'), T = kstDay(Date.now()), have = new Set(convs.filter(c => !c.archived && c.updated > 0).map(c => kstDay(c.updated)));
    const base = wkDay || T, [y, m, d] = base.split('-').map(Number), start = new Date(Date.UTC(y, m - 1, d)); start.setUTCDate(start.getUTCDate() - start.getUTCDay());
    const key = kstDay(start.getTime() + 12 * 36e5) + '|' + [...have].filter(x => x >= kstDay(start.getTime() + 12 * 36e5)).length;
    const mo = $('#logMonth'); mo.textContent = `${y}년 ${m}월`;
    const week = [...Array(7)].map((_, i) => { const t = new Date(start); t.setUTCDate(start.getUTCDate() + i); return t.toISOString().slice(0, 10); });
    const sig = week.join() + '|' + week.map(x => have.has(x) ? 1 : 0).join('');
    if (el.dataset.sig !== sig) {
      const changedWeek = el.dataset.week && el.dataset.week !== week[0];
      el.dataset.sig = sig; el.dataset.week = week[0]; el.replaceChildren();
      week.forEach((ymd, i) => {
        const fut = ymd > T, has = have.has(ymd), b = document.createElement('button'); b.type = 'button'; b.className = 'wk-c'; b.dataset.day = ymd;
        if (fut || !has) b.setAttribute('aria-disabled', 'true'); if (fut) b.classList.add('fut'); if (has) b.classList.add('has');
        const [, mm, dd] = ymd.split('-').map(Number); b.setAttribute('aria-label', `${mm}월 ${dd}일 ${WEEKDAY[i]}요일${has ? ', 기록 있음' : ''}`);
        b.innerHTML = '<span class="wk-w"></span><span class="wk-n"></span>'; b.querySelector('.wk-w').textContent = WEEKDAY[i]; b.querySelector('.wk-n').textContent = String(dd);
        el.appendChild(b);
      });
      if (changedWeek && !reduce.matches) { el.classList.remove('sw'); void el.offsetWidth; el.classList.add('sw'); }
    }
    el.querySelectorAll('.wk-c').forEach(b => { const on = b.dataset.day === base; b.classList.toggle('sel', on); if (on) b.setAttribute('aria-current', 'date'); else b.removeAttribute('aria-current'); });
  }
  $('#wk').addEventListener('click', e => {
    const b = e.target.closest('.wk-c'); if (!b || b.getAttribute('aria-disabled') === 'true') return;
    const lab = $('#convList').querySelector(`.group-label[data-day="${b.dataset.day}"]`); if (!lab) return;
    wkDay = b.dataset.day; wkLock = Date.now() + 1000; renderWk(); lab.scrollIntoView({ block: 'start', behavior: reduce.matches ? 'auto' : 'smooth' });
  });
  let wkT = 0, wkLock = 0;
  function trackWk() {
    clearTimeout(wkT); wkT = setTimeout(() => {
      if (Date.now() < wkLock) return;
      const top = scroller.getBoundingClientRect().top + (parseFloat(getComputedStyle(listView).getPropertyValue('--nav-h')) || 44) + ($('#wk').offsetHeight || 0) + 2;
      const labs = [...$('#convList').querySelectorAll('.group-label[data-day]')]; if (!labs.length) return;
      let cur = labs[0]; for (const l of labs) if (l.getBoundingClientRect().top <= top + 8) cur = l; else break;
      if (cur.dataset.day !== wkDay) { wkDay = cur.dataset.day; renderWk(); }
    }, 100);
  }
  function renderList() {
    const ul = $('#convList'); if (ul.querySelector('.row.editing')) return; ul.innerHTML = '';
    const searching = listView.classList.contains('searching'), q = listQuery().toLowerCase(), flatMode = searching || !!q;
    const live = convs.filter(c => !c.archived);
    live.sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0) || b.updated - a.updated);
    const list = live.filter(c => !q || c.title.toLowerCase().includes(q) || c.messages.some(m => (m.content || '').toLowerCase().includes(q)) || (c.preview || '').toLowerCase().includes(q));
    $('#listEmpty').hidden = !!live.length || threadsLoading || listLoading || flatMode;
    const label = (txt, n, day) => { const h = document.createElement('li'); h.className = 'group-label'; if (day) h.dataset.day = day; h.innerHTML = '<span class="gl-n"></span><span class="gl-c"></span>'; h.querySelector('.gl-n').textContent = txt; h.querySelector('.gl-c').textContent = n ? `대화 ${n}` : ''; ul.appendChild(h); };
    if (!flatMode) {
      const cnt = new Map(); list.forEach(c => { const k = c.pinned ? 'pin' : kstDay(c.updated || 0); cnt.set(k, (cnt.get(k) || 0) + 1); });
      let lastG = null;
      list.forEach(c => {
        const g = c.pinned ? 'pin' : kstDay(c.updated || 0);
        if (g !== lastG) { label(g === 'pin' ? '고정됨' : daySepText(c.updated || 0), cnt.get(g), g === 'pin' ? '' : g); lastG = g; }
        ul.appendChild(rowEl(c, '', { day: g === 'pin' }));
      });
    } else list.forEach(c => ul.appendChild(rowEl(c, '', { date: true })));
    if (q && searchHits) {   // server results (title + content), deduped against local rows
      const hits = searchHits.filter(h => h.match === 'content' || !list.some(c => c.id === h.thread_id));
      hits.forEach(hit => {
        const li = document.createElement('li'); li.className = 'hit'; li.dataset.tid = hit.thread_id; if (hit.message_id) li.dataset.mid = hit.message_id;
        li.innerHTML = `<div class="row-main"><time class="r-tm"></time><div class="r-bd"><div class="row-top"><span class="row-title"></span></div><div class="row-sub snippet">${safeSnippet(hit.snippet)}</div></div></div>`;
        li.querySelector('.row-title').textContent = hit.thread_title || '대화'; li.querySelector('time').textContent = hhmm(toMs(hit.created_at));
        ul.appendChild(li);
      });
      if (!list.length && !hits.length) ul.innerHTML = '<li class="no-results">결과 없음</li>';
    } else if (q && !list.length && !(mode === 'server' && searchT)) ul.innerHTML = '<li class="no-results">결과 없음</li>';
    if ((threadsLoading || logSkel()) && !q) for (let i = 0; i < 3; i++) { const s = document.createElement('li'); s.className = 'skel'; s.innerHTML = '<i></i><i></i>'; ul.appendChild(s); }
    // one group card per run of rows: round the first and last row
    let run = [];
    const flush = () => { if (run.length) { run[0].classList.add('g1'); run[run.length - 1].classList.add('g9'); } run = []; };
    [...ul.children].forEach(li => { if (li.classList.contains('group-label') || li.classList.contains('no-results')) flush(); else run.push(li); }); flush();
    const ar = $('#archivedRow'); if (ar) { ar.hidden = flatMode; const n = mode === 'local' ? convs.filter(c => c.archived).length : 0; $('#archivedCount').textContent = n ? String(n) : ''; }
    renderWk(); todayDirty();
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
  async function openHit(tid, mid, block = 'center') {
    let c = convs.find(x => x.id === tid) || archivedList.find(x => x.id === tid);
    if (!c) { try { const t = await api('/v1/threads/' + encodeURIComponent(tid)); c = fromServerThread(t); (c.archived ? archivedList : convs).push(c); } catch { return showToast('대화를 열 수 없어요', '', null, 2000); } }
    openConv(c.id);
    if (!mid) return;
    for (let i = 0; i < 40 && !(c.loaded && !c.loading); i++) await new Promise(r => setTimeout(r, 50));
    for (let n = 0; n < 10 && !c.messages.some(m => m.id === mid) && c.hasMore; n++) await loadOlder();
    requestAnimationFrame(() => { const el = box.querySelector(`.msg[data-mid="${CSS.escape(mid)}"]`); if (!el) return; stick = false; el.scrollIntoView({ block }); el.classList.add('flash'); setTimeout(() => el.classList.remove('flash'), 1600); });
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
    ul.firstElementChild?.classList.add('g1'); ul.lastElementChild?.classList.add('g9');
    $('#archEmpty').hidden = !!list.length;
  }
  $('#archList').addEventListener('click', e => {
    if (suppressClick) return;
    const row = e.target.closest('.row'); if (!row) return; const c = convOf(row); if (!c) return;
    if (e.target.closest('.ra-restore')) return restoreConv(c);
    if (e.target.closest('.ra-del')) return confirmDelete(c);
    if (openRow) return closeSwipe();
    openConv(c.id);
  });
  function confirmDelete(c) {
    closeSwipe();
    showMenu(null, [{ label: '대화 영구 삭제', danger: true, act: () => deleteConv(c) }, { label: '취소', act: () => {} }], { sheet: true, title: '대화를 영구 삭제할까요? 이 작업은 되돌릴 수 없어요.' });
  }
  $('#archivedRow').onclick = () => { loadArchive(); go('archive'); };
  $('#archBack').onclick = () => back();

  /* ---------- messages ---------- */
  /* 1.10.0 B1 (DIRECTION-B §3): a message is one timeline event: time (KST, 24h) · dot · who · body. No bubbles. */
  const KST_HM = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
  const KST_YMD = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' });
  const hhmm = t => { try { return KST_HM.format(new Date(t)); } catch { return ''; } };
  const kstDay = t => { try { return KST_YMD.format(new Date(t)); } catch { return ''; } };
  const WEEKDAY = '일월화수목금토';
  function daySepText(t, now = Date.now()) {
    const d = kstDay(t), today = kstDay(now), [y, mo, da] = d.split('-').map(Number), wd = WEEKDAY[new Date(Date.UTC(y, mo - 1, da)).getUTCDay()];
    if (d === today) return `오늘 · ${wd}`; if (d === kstDay(now - 864e5)) return `어제 · ${wd}`;
    return (String(y) !== today.slice(0, 4) ? `${y}년 ` : '') + `${mo}월 ${da}일 · ${wd}`;
  }
  const USER_NAME = '나';   // the signed-in display name has no settings field yet (DIRECTION-B §14): never hard-code a person
  function addMsgEl(role, content, m) {
    const t = m?.created > 0 ? m.created : Date.now(), who = role === 'user' ? USER_NAME : 'Eve';
    const wrap = document.createElement('div'); wrap.className = 'msg ev ' + role + (role === 'user' ? ' me' : role === 'assistant' ? ' e' : ''); wrap.dataset.t = String(t); if (m?.id) wrap.dataset.mid = m.id;
    wrap.setAttribute('role', 'listitem'); wrap.setAttribute('aria-label', `${hhmm(t)} ${who}`);
    const tm = document.createElement('time'); tm.className = 'tm'; tm.dateTime = new Date(t).toISOString(); tm.textContent = hhmm(t);
    const dot = document.createElement('span'); dot.className = 'dot'; dot.setAttribute('aria-hidden', 'true');
    const wh = document.createElement('div'); wh.className = 'who'; const wn = document.createElement('span'); wn.className = 'who-n'; wn.textContent = who; wh.appendChild(wn);
    const b = document.createElement('div'); b.className = 'bubble tx'; wrap.append(tm, dot, wh, b);
    if (role === 'user') b.textContent = content;
    if (role !== 'error') {   // a new date starts a day-sep (rail continues through it)
      const prev = box._lastMsg && box.contains(box._lastMsg) ? box._lastMsg : [...box.querySelectorAll(':scope > .msg:not(.error)')].pop();
      if (prev ? prev.dataset.t && kstDay(+prev.dataset.t) !== kstDay(t) : kstDay(t) !== kstDay(Date.now())) { const sep = document.createElement('div'); sep.className = 'day-sep'; sep.textContent = daySepText(t); box.appendChild(sep); }
      box._lastMsg = wrap;
    }
    if (!box.classList.contains('no-anim')) { box.querySelectorAll(':scope > .msg.enter').forEach(x => x.classList.remove('enter')); wrap.classList.add('enter'); }   // M9: only the newly appended last one
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
    if (!answer.trim()) return !md && (!!bubble.querySelector('.typing,.tline') || (!!det && thinking));
    if (!md) { // first answer token: append answer container without touching the think block
      bubble.querySelectorAll('.typing,.warming').forEach(n => n.remove()); bubble._tsDrop?.();   // the tool line fades out (opacity --d-1) and leaves the flow
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
  /* AUTO-TOOLS-SPEC §5/§7: what the web tools did for a reply — {tools:[{q,by}], note:{key,t}} — kept in memory for this session only (message id → info; never written to storage, so queries do not persist) */
  const TOOLINFO = new Map();
  const renderToolNote = n => n && TOOL_FAIL[n.key] ? `<div class="tnote" role="status" aria-live="polite" data-key="${n.key}" data-t="${n.t || 0}"></div>` : '';   // empty container first; the text is filled next frame so assistive tech announces it
  function fillToolNote(bubble) {
    const n = bubble.querySelector('.tnote[data-key]'); if (!n) return;
    requestAnimationFrame(() => {
      if (!n.isConnected || n.firstChild) return;
      const [, title, sub] = TOOL_FAIL[n.dataset.key] || TOOL_FAIL.unknown;
      n.innerHTML = `${ICON.warn}<div class="tb"><b>${title}</b><span>${sub}</span></div>`;
    });
  }
  /* "참고한 기억" chips (DIRECTION-B §8.1): only when the message carries memory_refs and memory is on; text via escapeHtml only */
  function renderMemRefs(m) {
    const refs = m?.memoryRefs; if (!refs?.length || !MEM?.active?.()) return '';
    const lab = t => { const a = [...String(t)]; return a.length > 14 ? a.slice(0, 14).join('') + '…' : a.join(''); }, shown = refs.slice(0, 2), more = refs.length - shown.length;
    return `<div class="mchips" role="group" aria-label="참고한 기억">${shown.map(r => `<button type="button" class="chp m" data-ref="${escapeHtml(r.id)}" aria-label="${escapeHtml('참고한 기억: ' + r.text)}"><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4h10a1 1 0 0 1 1 1v15l-6-4-6 4V5a1 1 0 0 1 1-1z"/></svg><span>${escapeHtml(lab(r.text))}</span></button>`).join('')}${more ? `<span class="chp-more">+${more}</span>` : ''}</div>`;
  }
  box.addEventListener('click', e => { const b = e.target.closest('.chp.m'); if (b && MEM) openMemoryView(b.dataset.ref); });
   // memory chip → settings sheet #memoryView (openMemoryView, B3)
  function fillAssistant(bubble, text, opts = {}) {
    const { think, answer, thinking } = splitThink(stripStopMark(text));
    const live = !!opts.live;
    if (live) bubble._streamed = true;
    if (live && bubble._live && !opts.slow && !opts.resuming && patchLive(bubble, think, answer, live && thinking)) return;
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
    if (waiting && bubble._tline) { /* the persistent .tline node is re-attached below */ }
    else if (waiting) html += `<span class="typing"><i></i><i></i><i></i></span>${opts.slow ? '<div class="warming">모델 준비 중…</div>' : ''}`;
    else if (live && !answer.trim()) { /* still thinking: no answer container yet */ }
    else if (live) { const cut = stableCut(answer); bubble._cut = cut; html += `<div class="md cursor"><div class="stable">${renderMarkdown(answer.slice(0, cut), srcs)}</div><div class="tail">${renderMarkdown(answer.slice(cut), srcs)}</div></div>`; }
    else { const ti = (opts.msg?.id && TOOLINFO.get(opts.msg.id)) || bubble._ti || null; html += `<div class="md">${renderMarkdown(answer, srcs)}</div>${renderSources(srcs, ti?.tools || opts.msg?.tools)}${renderMemRefs(opts.msg)}${renderToolNote(ti ? ti.note : freshNote(opts.msg))}`; }
    const wasLive = bubble._streamed; bubble._streamed = live; bubble._live = live;
    const userToggled = prev?.dataset.user;
    if (bubble._tline && (!live || answer.trim())) bubble._tsDrop?.();   // answer text (or a finished render) replaces the line; never leave a stale node
    bubble.innerHTML = html;
    if (live && bubble._tline && !answer.trim()) { bubble.appendChild(bubble._tline); requestAnimationFrame(() => bubble._tline?.classList.add('in')); }
    if (wasLive && !live) bubble._freshAt = performance.now();
    { const secs = !live && bubble._freshAt ? bubble.querySelectorAll('.sources, .mchips') : [], el = secs.length ? performance.now() - bubble._freshAt : 1e9; // 120ms fade survives a same-tick re-fill (source + memory chips)
      if (el < 120) secs.forEach(sec => { sec.classList.add('fresh'); if (el > 1) sec.style.animationDelay = `-${Math.round(el)}ms`; }); }
    fillToolNote(bubble);
    const det = bubble.querySelector('details.think');
    if (det) { if (userToggled) det.dataset.user = '1'; det.querySelector('summary').addEventListener('click', () => { det.dataset.user = '1'; }); }
    bubble._tailHtml = null;
    const msg = bubble.parentElement;
    msg.querySelector('.actions')?.remove(); msg.querySelector('.stopped')?.remove();
    msg.querySelector('.msg-note')?.remove();
    // 1.1.3: old incomplete rows with a non-stop reason, and empty finished replies, count as failed (no silent empty bubbles)
    const om = opts.msg, oldFail = om?.status === 'incomplete' && om.errorCode && !STOP_CODES.has(om.errorCode);
    const emptyDone = !live && !opts.stopped && om && om.role !== 'user' && !answer.trim() && think === null && (!om.status || om.status === 'complete');
    const isFail = !live && (om?.status === 'failed' && !STOP_CODES.has(om.errorCode) || oldFail || emptyDone);
    if (!live && !isFail && (opts.stopped || om?.status === 'incomplete' || (om?.status === 'failed' && STOP_CODES.has(om.errorCode)))) { const st = document.createElement('div'); st.className = 'stopped'; st.setAttribute('role', 'note'); st.textContent = STOPPED_TEXT;
      if (opts.regen) { const rb = document.createElement('button'); rb.type = 'button'; rb.className = 'btn retry'; rb.textContent = '다시 시도'; rb.onclick = regenerate; st.append(' ', rb); }   // normal style, retry kept
      msg.appendChild(st); }
    else if (isFail) { const st = document.createElement('div'); st.className = 'stopped msg-note failed'; st.setAttribute('role', 'note'); st.textContent = emptyDone && !om.errorCode ? '답변을 받지 못했어요' : failText(om.errorCode);
      if (opts.regen) { const rb = document.createElement('button'); rb.type = 'button'; rb.className = 'btn retry'; rb.textContent = '다시 시도'; rb.onclick = regenerate; st.append(' ', rb); }   // regenerates the same message_id
      msg.appendChild(st); }
    else if (opts.msg?.status === 'generating' || opts.resuming) { const st = document.createElement('div'); st.className = 'stopped msg-note resuming'; st.setAttribute('role', 'status'); st.textContent = RESUMING; msg.appendChild(st); }
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

  /* 1.10.0 B1: an empty conversation is just the timeline's "지금" event (DIRECTION-B §4): no logo, headline, subtitle or suggestion cards. */
  function renderEmpty() {
    const t = Date.now(), ev = document.createElement('div'); ev.className = 'rail-now'; ev.setAttribute('role', 'listitem'); ev.setAttribute('aria-label', `${hhmm(t)} 지금`);
    ev.innerHTML = '<time class="tm"></time><span class="dot" aria-hidden="true"></span><div class="who"><span class="who-n">지금</span></div><div class="tx d">아래에 한 줄로 남기면 오늘 기록에 쌓여요.</div>';
    ev.querySelector('.tm').textContent = hhmm(t); box.innerHTML = ''; box.appendChild(ev);
  }
  setInterval(() => { const n = box.querySelector('.rail-now'); if (n && !document.hidden) { const t = Date.now(); n.querySelector('.tm').textContent = hhmm(t); n.setAttribute('aria-label', `${hhmm(t)} 지금`); } }, 60000);
  function setConvTitle(t) { $('#title').textContent = t; box.setAttribute('aria-label', t || '대화'); }   /* the message list is named after the thread (screen readers: "<title>, list") */
  function renderMessages(keep) {
    box.innerHTML = '';
    const c = cur();
    setConvTitle(c ? c.title : '새 대화');
    const mi = $('#sModelInfo'); if (mi) mi.textContent = shortModel() || '—';
    chatView.classList.toggle('archived', !!c?.archived);
    if (c?.loading && !c.messages.length) { box.innerHTML = '<div class="older loading"><span class="spin"></span></div>'; return; }
    if (!c || !c.messages.length) return renderEmpty();
    box.classList.add('no-anim');
    if (c.hasMore) box.insertAdjacentHTML('afterbegin', '<div class="older"><span class="spin"></span></div>');
    const lastA = c.messages.map(m => m.role).lastIndexOf('assistant');
    c.messages.forEach((m, i) => {
      if (m.role === 'user') addMsgEl('user', m.content, m);
      else fillAssistant(addMsgEl('assistant', '', m), m.content, { usage: m.usageText || (m.usage ? usageText(m.usage) : ''), regen: !c.archived && m.origin !== 'proactive' && i === lastA && i === c.messages.length - 1, thinkSecs: m.thinkSecs, msg: m });
      PRO?.decorateMsg([...box.querySelectorAll(':scope > .msg')].pop() || null, m, i, c.messages);
    });
    PRO?.afterRender(c);
    if (MEM?.ensure && !MEM.active() && c.messages.some(m => m.memoryRefs?.length)) MEM.ensure().then(on => { if (on && cur() === c && !controller) renderMessages(true); });
    // 1.1.3: thread ends with a user turn and no reply (and nothing running) → visible retry
    if (!c.archived && c.messages.at(-1)?.role === 'user' && !c.loading && !(controller && genId === c.id)) addError('답변을 받지 못했어요', () => generate(c));
    requestAnimationFrame(() => { box.classList.remove('no-anim'); if (!keep) { stick = true; scrollBottom(); } });
  }
  function renderAll() { renderList(); renderMessages(); }

  function setBusy(b) {
    sendBtn.classList.toggle('stop', b);
    sendBtn.disabled = b ? false : !input.value.trim();
    sendBtn.setAttribute('aria-label', b ? '생성 중지' : '전송'); sendBtn.title = b ? '생성 중지 (Esc)' : '';
    tSend.classList.toggle('stop', b); tSend.disabled = b ? false : !tInput.value.trim(); tSend.setAttribute('aria-label', b ? '생성 중지' : '전송');
    if (b) { genId = currentId; if (currentId) localStorage.removeItem(LS.draft + currentId); } else { genId = null; if (app.dataset.route === 'list' || app.dataset.route === 'today' || wide.matches) renderList(); maybeA2HS(); }
  }

  /* ---------- errors (gateway contract) ---------- */
  const RETRYABLE = new Set([429, 502, 503, 504]);
  function errMsg(status, body) {
    let e = {}; try { e = JSON.parse(body).error || {}; } catch {}
    let code = e.code || ''; if (!code) try { code = JSON.parse(body).error_code || ''; } catch {}
    // 1.1.4 copy: no infrastructure names, codes or HTTP numbers on screen
    if (code === 'identity_not_allowed') return '허용되지 않은 계정이에요';
    if (status === 403 && code === 'scope_denied') return '이 세션에서는 할 수 없는 작업이에요';   // 1.6.0: session kept, no pairing
    if (isAuthFail(status, code)) return '서버에 연결할 수 없어요. 연결을 확인해 주세요';
    if (FAIL_TEXT[code]) return FAIL_TEXT[code];
    if (status === 429) return BUSY_TEXT;
    if (status === 504) return FAIL_TEXT.upstream_timeout;
    if (status === 404) return '연결할 주소를 찾을 수 없어요. 설정의 Base URL을 확인해 주세요.';
    return DEFAULT_FAIL;
  }
  // 1.1.3 (contract §3.8): failed message error_code → friendly text; unknown → generic
  const DEFAULT_FAIL = '답변을 끝내지 못했어요', BUSY_TEXT = '지금 요청이 많아요. 잠시 후 다시 시도해 주세요', STOPPED_TEXT = '답변을 멈췄어요';
  const FAIL_TEXT = { upstream_error: '문제가 생겨 답변을 끝내지 못했어요', internal_error: '문제가 생겨 답변을 끝내지 못했어요',
    upstream_timeout: '응답이 늦어 답변을 끝내지 못했어요', timeout: '답변이 너무 오래 걸려 멈췄어요',
    gateway_restart: '잠시 연결이 끊겨 답변이 멈췄어요', no_subscriber: '앱을 오래 닫아 두어 답변이 멈췄어요', too_large: '답변이 너무 길어져 멈췄어요',
    queue_full: BUSY_TEXT, queue_timeout: BUSY_TEXT, server_busy: BUSY_TEXT, rate_limited: BUSY_TEXT,
    too_many_generations: '이미 답변 2개를 만들고 있어요. 하나가 끝나면 다시 시도해 주세요',
    too_many_subscribers: '이 답변이 열린 창이 너무 많아요. 다른 창을 닫고 다시 시도해 주세요',
    generation_in_progress: '이 답변은 이미 다시 만드는 중이에요' };
  // 1.1.3: user stops — new 'cancelled' and the legacy incomplete reason for a client abort → 중지됨
  const STOP_CODES = new Set(['cancelled', 'client_disconnected']);
  const HTTP_CODES = new Set(['queue_full', 'queue_timeout', 'rate_limited', 'too_many_generations', 'server_busy', 'too_many_subscribers', 'generation_in_progress']);
  const raText = ra => ra > 0 ? ` (${Math.ceil(ra)}초 뒤에 다시 시도할 수 있어요)` : '';
  const retryAfterOf = res => { const v = res.headers.get('Retry-After'); if (!v) return 0; const n = +v; if (Number.isFinite(n)) return Math.max(0, n); const d = Date.parse(v); return isNaN(d) ? 0 : Math.max(0, (d - Date.now()) / 1000); };
  const failText = code => FAIL_TEXT[code] || DEFAULT_FAIL;
  const RESUMING = '답변 불러오는 중…';
  function clearErrors() { box.querySelectorAll('.msg.error').forEach(e => e.remove()); }
  function addError(text, retry, retryAfter) {
    const b = addMsgEl('error');
    b.innerHTML = `${ICON.warn}<span class="err-text"></span>`;
    b.querySelector('.err-text').textContent = text;
    if (retry) { const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'btn retry'; btn.textContent = '다시 시도'; btn.onclick = () => { b.parentElement.remove(); retry(); }; b.appendChild(btn);
      if (retryAfter > 0) { btn.disabled = true; setTimeout(() => { btn.disabled = false; }, retryAfter * 1000); } }   // respect Retry-After
    scrollBottom(true);
  }

  /* ---------- send / generate ---------- */
  async function send(text) {
    let c = cur();
    if (!c || c.archived) { c = blankConv(); convs.unshift(c); currentId = c.id; }
    if (!c.messages.length) { box.innerHTML = ''; c.title = text.slice(0, 30); setConvTitle(c.title); }
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
  let cancelRun = null;
  /* 1.10.2: the connection came back (online event) while an answer is streaming. A socket that died silently while offline never errors, so reader.read()
     would wait forever and the bubble would stay on '답변 불러오는 중…'. Cancelling the reader ends the read → 'stream ended early' → recover() re-requests
     GET …/stream with Last-Event-ID (or polls). Safe when the stream was in fact alive: the replay continues after the last event we applied. */
  let kickStream = null;
  function stopGeneration() { if (controller) { try { cancelRun?.(); } catch {} buzz(10); sendBtn.classList.add('pressed'); setTimeout(() => sendBtn.classList.remove('pressed'), 160); controller.abort(); } }

  // 409 generation_in_progress bodies: {error:{code,message_id}} | {error_code, message_id} | {error:{code, details:{message_id}}}
  function inProgressId(body) {
    let j = null; try { j = typeof body === 'string' ? JSON.parse(body) : body; } catch { return ''; }
    const id = j && (j.error?.message_id ?? j.message_id ?? j.error?.details?.message_id ?? j.details?.message_id);
    return typeof id === 'string' && /^[\w.-]{1,128}$/.test(id) ? id : '';
  }
  // attaching to a turn that is already on the server: no second user bubble, no stale copy of that assistant row
  function dropDupTurn(c, id) {
    const msgs = c.messages, last = msgs.at(-1), prev = msgs.at(-2);
    const users = () => box.querySelectorAll('.msg.user');
    if (last?.role === 'user' && prev?.role === 'user' && prev.content === last.content) { msgs.pop(); if (c === cur()) { const u = users(); u[u.length - 1]?.remove(); } }
    for (let i = msgs.length - 1; i >= 0; i--) if (msgs[i].role === 'assistant' && msgs[i].id === id) { msgs.splice(i, 1); if (c === cur()) box.querySelector(`.msg.assistant[data-mid="${CSS.escape(id)}"]`)?.remove(); }
    persist();
  }
  async function generate(c, replaceId) {
    const bubble = addMsgEl('assistant');
    const hist = c.messages.map(({ role, content }) => ({ role, content: role === 'assistant' ? stripStopMark(splitThink(stripStopMark(content)).answer) : content }))
      .filter(m => m.role !== 'assistant' || m.content.trim());
    if (settings.noThink) { const last = hist[hist.length - 1]; if (last && last.role === 'user' && !/\/no_think\s*$/.test(last.content)) last.content += ' /no_think'; }
    const msgs = (settings.system ? [{ role: 'system', content: settings.system }] : []).concat(hist);
    const ctl = controller = new AbortController(); setBusy(true); let stopped = false;
    let sources = null; bubble._tline = null; bubble._ti = null; bubble._sources = null;
    let confs = null, acc = '', reasoning = '', usage = null, streamErr = null, slow = false, thinkStart = 0, thinkSecs = 0;
    const t0 = performance.now();
    const full = () => reasoning ? `<think>${reasoning}</think>${acc}` : acc;
    const view = () => reasoning && !acc ? '<think>' + reasoning : full();
    fillAssistant(bubble, '', { live: true }); scrollBottom(true);
    const slowTimer = setTimeout(() => { if (!acc && !reasoning) { slow = true; fillAssistant(bubble, '', { live: true, slow }); } }, 3000);
    let raf = 0;
    const paint = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; fillAssistant(bubble, view(), { live: true }); if (stick) scrollBottomThrottled(); }); };
    // 1.1.4: if the thread now ends with a failed assistant row, retry must replace it (replace_message_id),
    // otherwise gateway 3.1.0 stores the user turn twice
    const retry = () => { const la = c.messages.at(-1); if (la?.role === 'assistant' && la.id && la.status !== 'complete') { clearErrors(); c.messages.pop(); const els = box.querySelectorAll('.msg.assistant'); if (c === cur()) els[els.length - 1]?.remove(); persist(); return generate(c, la.id); } return generate(c, replaceId); };
    let persisted = null; const userMsg = [...c.messages].reverse().find(m => m.role === 'user');
    const ids = j => { if (j.thread_id && mode === 'server') adoptThreadId(c, j.thread_id); if (j.user_message_id && userMsg) userMsg.id = j.user_message_id; };
    const finish = () => { tsStop(); clearTimeout(slowTimer); if (kickStream === kick) kickStream = null; if (controller === ctl) controller = null; setBusy(false); if (raf) cancelAnimationFrame(raf); raf = 0; };
    const markThink = () => { if (!thinkStart) thinkStart = performance.now(); };
    const endThink = () => { if (thinkStart && !thinkSecs) thinkSecs = Math.max(1, Math.round((performance.now() - thinkStart) / 1000)); };
    /* ---- the tool status line (AUTO-TOOLS-SPEC §3/§4/§9): ONE reused .tline > .tstat[role=status] per reply; text swaps cross-fade (opacity only),
       web updates are throttled to ≥1 s apart (the latest wins), a PIM tool's own copy shows at once; the line leaves the flow on the first answer token / on stop ---- */
    const ts = { applied: 0, timer: 0, want: null, slowT: 0, s4T: 0, slowShown: false, dead: false, tools: [], calls: new Map(), fail: null };
    const reduceM = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
    function tsSwap(wrap, text) {
      const cur = wrap.querySelector('span.on:last-child') || wrap.lastElementChild;
      if (!text) { wrap.replaceChildren(); return; }
      if (cur && cur.textContent === text) return;
      const n = document.createElement('span'); n.textContent = text;
      if (cur && !reduceM()) { cur.classList.remove('on'); setTimeout(() => cur.remove(), 160); } else if (cur) cur.remove();
      wrap.appendChild(n); requestAnimationFrame(() => n.classList.add('on'));
    }
    function tsFill(w, r1, r2) {
      tsSwap(w.querySelector('.t1'), r1); const row2 = w.querySelector('.row2'); row2.hidden = !r2; tsSwap(w.querySelector('.t2'), r2 || '');
    }
    function tsApply() {
      ts.timer = 0; const want = ts.want; ts.want = null; if (!want || ts.dead || acc.trim()) return;
      let w = bubble._tline;
      if (!w || !w.isConnected) {
        if (!w) { w = bubble._tline = document.createElement('div'); w.className = 'tline';
          w.innerHTML = `<div class="tstat" role="status" aria-live="polite" aria-atomic="true"><div class="row1">${icon('globe-spark')}<span class="tw t1"></span></div><div class="row2" hidden><span class="tw t2"></span></div></div>`; }
        bubble._live = false; fillAssistant(bubble, view(), { live: true }); if (stick) scrollBottom();
        ts.applied = performance.now(); requestAnimationFrame(() => { if (bubble._tline === w) tsFill(w, want.r1, want.r2); });   // container first, text on the next frame
        return;
      }
      ts.applied = performance.now(); tsFill(w, want.r1, want.r2);
    }
    const tsShow = (r1, r2 = '', now = false) => {
      if (ts.dead || acc.trim()) return;
      ts.want = { r1, r2 }; clearTimeout(ts.timer); ts.timer = 0;
      const wait = now || !ts.applied ? 0 : Math.max(0, ts.applied + 1000 - performance.now());
      if (wait) ts.timer = setTimeout(tsApply, wait); else tsApply();
    };
    const tsSlowOff = () => { clearTimeout(ts.slowT); ts.slowT = 0; };
    const tsRemove = () => {
      clearTimeout(ts.timer); ts.timer = 0; ts.want = null; clearTimeout(ts.s4T); tsSlowOff();
      const w = bubble._tline; bubble._tline = null; if (!w) return;
      if (w.isConnected) { w.classList.remove('in'); w.classList.add('out'); setTimeout(() => w.remove(), 160); }
    };
    bubble._tsDrop = tsRemove;
    const tsStop = () => { ts.dead = true; tsRemove(); };
    const setWs = t => { tsShow(t, '', true); };   // PIM tools (calendar/reminders): own copy, no throttle, never the web wording
    const hostOf = u => { try { return u ? new URL(u).hostname.replace(/^www\./i, '') : ''; } catch { return ''; } };
    const isWebTool = t => t === 'web_search' || t === 'web_fetch';
    function onWebCall(j) {
      const a = j.args && typeof j.args === 'object' ? j.args : {}, id = j.id != null ? String(j.id) : '';
      const by = j.selected_by === 'model' || j.selected_by === 'user' ? j.selected_by : '';
      clearTimeout(ts.s4T);
      let r1, r2 = '';
      if (j.tool === 'web_fetch') { r1 = '페이지를 읽고 있어요'; r2 = hostOf(a.url) || '웹 페이지'; }
      else { r1 = '웹에서 찾고 있어요'; const q = typeof a.query === 'string' ? a.query.trim() : ''; r2 = q ? `“${q}”` : '';
        if (q || by) { const t = { q, by }; ts.tools.push(t); if (id) ts.calls.set(id, t); bubble._ti = { tools: ts.tools, note: null }; } }
      tsShow(r1, r2);
      tsSlowOff(); if (!ts.slowShown) ts.slowT = setTimeout(() => { const w = bubble._tline; if (!w || ts.slowShown || acc.trim()) return; ts.slowShown = true;
        const sp = document.createElement('span'); sp.className = 'slow'; sp.setAttribute('aria-hidden', 'true'); sp.textContent = ' · 조금 걸려요'; w.querySelector('.row1').appendChild(sp); }, 6000);
    }
    function onWebResult(j) {
      tsSlowOff(); clearTimeout(ts.s4T);
      const call = j.id != null ? ts.calls.get(String(j.id)) : null, key = toolFailKey(j);
      const srcs = Array.isArray(j.sources) ? j.sources : [];
      if (srcs.length) { const m = new Map((sources || []).map(x => [x.n, x])); srcs.forEach(x => m.set(x.n, x)); sources = [...m.values()]; bubble._sources = sources; }
      if (key === 'query_rejected' && call) call.q = '';   // a rejected query is never shown (§4)
      if (j.error_code === 'duplicate_query') return;       // silent: no line change
      if (key) {
        if (!ts.fail) ts.fail = { key, t: Date.now() };
        if (!(key === 'blocked' && srcs.length)) { tsShow(TOOL_FAIL[key][0]); ts.s4T = setTimeout(() => tsShow('답변을 쓰고 있어요'), 1500); return; }
      }
      if (j.error_code === 'tainted') return;
      if (srcs.length) { const n = Number.isFinite(+j.count) && +j.count > 0 ? +j.count : srcs.length; const d = srcDomain(srcs[0]);
        tsShow(`출처 ${n}개를 읽고 있어요`, n > 1 && d ? `${d} 외 ${n - 1}곳` : ''); }
      ts.s4T = setTimeout(() => tsShow('답변을 쓰고 있어요'), 1000);
    }
    ctl.signal.addEventListener('abort', tsStop, { once: true });   // stop: the line leaves at once (opacity --d-1), no chips/note are made for it
    let liveReader = null;
    let mid = null, seq = 0, wentHidden = document.hidden, done = false;   // §3.8 detached generation: eve.meta message_id + last event id
    const onVis = () => { if (document.hidden) wentHidden = true; };
    document.addEventListener('visibilitychange', onVis);
    const kick = () => { if (mid && !done && liveReader && mode === 'server') { try { liveReader.cancel(); } catch {} } };
    kickStream = kick;
    cancelRun = () => { if (mid && mode === 'server') api(`/v1/threads/${encodeURIComponent(c.id)}/messages/${encodeURIComponent(mid)}/cancel`, { method: 'POST' }).catch(() => {}); };   // §3.8 cancel → 204
    const applyMsg = m => {   // eve.snapshot / polled Message → replaces what we have
      acc = m.content || ''; reasoning = m.reasoning || ''; if (m.usage) usage = m.usage; if (acc.trim()) tsStop();
      const s = m.sources || m.metadata?.sources; if (Array.isArray(s) && s.length) { sources = s; bubble._sources = s; }
      if (m.status === 'failed') streamErr = { code: m.error_code || 'internal_error', failed: true };
    };
    const onEvent = (data, ev, id) => {
      if (id != null && /^\d+$/.test(id)) seq = Math.max(seq, +id);
      if (data.trim() === '[DONE]') { done = true; return; }
      let j; try { j = JSON.parse(data); } catch { return; }
      if (ev === 'eve.meta') { if (j.message_id) mid = j.message_id; ids(j); return; }
      if (ev === 'eve.snapshot') { applyMsg(j); if (+j.last_event_id > 0) seq = +j.last_event_id; if ((j.status || 'complete') !== 'generating') done = true; paint(); return; }   // replaces content, never appended
      if (j.error) { streamErr = j.error; return; }   // after admission: error event (+ retry_after)
      if (j.object === 'chat.completion.persisted') { ids(j); persisted = j; if (j.status === 'failed' && !streamErr) streamErr = { code: j.error_code || 'internal_error', failed: true }; return; }
      if (j.object === 'chat.completion.tool_call') {
        if (Pim?.isTool(j.tool)) { setWs(Pim.callText(j.tool)); return; }   // calendar/reminders: own copy, never the web-search wording (eve-serving #66 §11.1)
        if (isWebTool(j.tool)) onWebCall(j);   // unknown tool names are ignored (no line, no chip)
        return;
      }
      if (j.object === 'chat.completion.tool_result') {
        if (Pim?.isTool(j.tool)) {   // read card / error card are stream-only (never persisted); a write's confirm card follows as its own event
          setWs(Pim.resultText(j)); let n = null; try { n = Pim.resultCard(j); } catch {}
          if (n) Pim.mount(n, bubble.parentElement);
          return;
        }
        if (isWebTool(j.tool)) onWebResult(j);
        return;
      }
      if (j.object === 'chat.completion.confirmation') { if (PRO) (confs = confs || []).push(PRO.streamCard(j, bubble.parentElement)); return; }
      if (j.object === 'chat.completion.action_result') { PRO?.actionResult(j); return; }
      if (j.object === 'chat.completion.sources') { if (Array.isArray(j.sources)) { sources = j.sources; bubble._sources = sources; } return; }
      ids(j);
      if (j.usage) usage = j.usage;
      const d = j.choices?.[0]?.delta || {};
      const r = d.reasoning ?? d.reasoning_content;
      if (r) { markThink(); reasoning += r; }
      if (d.content) {
        acc += d.content; if (acc.trim()) tsStop();
        if (acc.includes('<think>')) markThink();
        if (reasoning || acc.includes('</think>')) endThink();
      }
      paint();
    };
    async function consume(res) {   // read one SSE response into the shared state; throws on network loss
      const reader = liveReader = res.body.getReader(); const dec = new TextDecoder(); const parser = createSSEParser(onEvent);
      const onAbort = () => { try { reader.cancel(); } catch {} };
      ctl.signal.addEventListener('abort', onAbort, { once: true });
      try { while (!done) { const { value, done: rd } = await reader.read(); if (rd) break; parser.push(dec.decode(value, { stream: true })); } parser.flush(); }
      finally { ctl.signal.removeEventListener('abort', onAbort); if (liveReader === reader) liveReader = null; }
      if (!done) try { reader.cancel(); } catch {}
    }
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const untilVisible = () => document.hidden ? new Promise(r => { const f = () => { if (document.hidden) return; document.removeEventListener('visibilitychange', f); removeEventListener('pageshow', f); r(); }; document.addEventListener('visibilitychange', f); addEventListener('pageshow', f); }) : null;
    async function recover() {   // stream lost (e.g. iOS killed fetch in background): resume → poll → give up
      const showResuming = () => { fillAssistant(bubble, view(), { live: true, resuming: true }); };
      showResuming(); await untilVisible(); showResuming();
      const tid = c.id, deadline = Date.now() + 5 * 60e3;
      for (let fails = 0; fails < 3 && Date.now() < deadline && !ctl.signal.aborted;) {   // 1) GET .../stream with Last-Event-ID (replay + live, or eve.snapshot); reconnect on write-timeout cuts
        if (fails) await sleep(800 * fails);
        if (document.hidden) await untilVisible();
        const before = seq;
        try {
          const r = await fetch(apiBase() + `/v1/threads/${encodeURIComponent(tid)}/messages/${encodeURIComponent(mid)}/stream`, { cache: 'no-store', signal: ctl.signal, headers: { ...headers(), 'Last-Event-ID': String(seq) } });
          if (r.status === 429) { fails++; await sleep(Math.min(30, retryAfterOf(r) || 2) * 1000); continue; }   // too_many_subscribers: wait Retry-After, retry
          if (!r.ok || !r.body) break;
          await consume(r); if (done) return true;
        } catch (e) { if (ctl.signal.aborted) throw e; }
        fails = seq > before ? 0 : fails + 1;   // progress → keep following (server cuts slow readers after 30s)
      }
      for (let k = 0; Date.now() < deadline && !ctl.signal.aborted; k++) {   // 2) poll the messages list (partial content while generating)
        if (k) await sleep(Math.min(8000, 1000 * 2 ** Math.min(k, 3)));
        if (document.hidden) await untilVisible();
        try {
          const j = await api(`/v1/threads/${encodeURIComponent(tid)}/messages?limit=10`);
          const m = (j.data || []).find(x => x.id === mid); if (!m) continue;
          applyMsg(m);
          if ((m.status || 'complete') !== 'generating') { done = true; return true; }
          showResuming();
        } catch (e) { if (e.http === 404) return false; }
      }
      return false;
    }
    try {
      const post = keep => fetch(apiBase() + '/v1/chat/completions', {
        method: 'POST', headers: headers('POST'), signal: ctl.signal,
        body: JSON.stringify(Object.assign({ model: settings.model || undefined, messages: msgs, stream: true, stream_options: { include_usage: true } },
          keep ? { thread_id: c.fresh || !c.srv ? 'new' : c.id } : {}, keep && replaceId ? { replace_message_id: replaceId } : {}))
      });
      let res = await post(mode === 'server');
      // storage switched off on the gateway mid-session: answer anyway without persistence, show the subtle notice
      if (res.status === 503 && mode === 'server') { const t = await res.clone().text().catch(() => ''); if (t.includes('persistence_disabled')) { persistOff = true; renderSync(); res = await post(false); } }
      if (!res.ok) {
        const body = await res.text().catch(() => '');
        const code = authCode(body);
        if (isAuthFail(res.status, code)) showAuthNotice(() => generate(c), code);
        const ra = retryAfterOf(res);
        // 1.8.0 (eve-serving #62): duplicate send/retry while the same turn is generating → 409 generation_in_progress.
        // If the body names the in-progress message (either shape), attach to it via the resume stream instead of an error.
        if (res.status === 409 && code === 'generation_in_progress' && mode === 'server' && c.srv) {
          const ip = inProgressId(body);
          if (ip) { dropDupTurn(c, ip); mid = ip; throw new Error('attach in-progress generation'); }   // non-http error → recover() below
        }
        if (HTTP_CODES.has(code) && (res.status === 429 || res.status === 409)) throw Object.assign(new Error(failText(code) + raText(ra)), { http: res.status, retryAfter: ra });   // before admission: no assistant row
        throw Object.assign(new Error(errMsg(res.status, body)), { http: res.status, retryAfter: ra });
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
        if (res.headers.get('X-Message-Id')) mid = res.headers.get('X-Message-Id');   // fallback when eve.meta is missing/late
        await consume(res);
        if (!done && !ctl.signal.aborted && mode === 'server' && (mid || wentHidden || document.hidden)) throw new Error('stream ended early');   // cut without [DONE] → resume / reload
        if (ctl.signal.aborted && !persisted) stopped = true;
      }
    } catch (e0) {
      let e = e0;
      if (!(e.name === 'AbortError' || ctl.signal.aborted) && !e.http && mode === 'server') {
        const bg = wentHidden || document.hidden || /load failed/i.test(e.message || '');
        if (mid) { let rec = false; try { rec = await recover(); } catch {} if (rec) e = null; }
        else if (bg && c.srv) {   // old server (no eve.meta): wait for foreground, reload the thread
          await untilVisible(); finish(); document.removeEventListener('visibilitychange', onVis);
          bubble.parentElement.remove(); c.loaded = false; await ensureMessages(c);
          if (c.messages.at(-1)?.role === 'assistant') return;
          addError('연결이 끊겼어요. 연결 상태를 확인해 주세요.', retry); return;
        }
      }
      if (e) finish();
      if (!e) { /* recovered: fall through to the normal ending */ }
      else if (e.name === 'AbortError' || ctl.signal.aborted) { stopped = true; }
      else {
        document.removeEventListener('visibilitychange', onVis);
        if (acc || reasoning) { fillAssistant(bubble, full(), { actions: false }); c.messages.push({ role: 'assistant', content: full() }); persist(); }
        else bubble.parentElement.remove();
        const m = e.http ? e.message : `네트워크 오류: ${e.message}. 연결 상태를 확인하세요.`;
        addError(m, (!e.http || RETRYABLE.has(e.http) || e.http === 409) && !(acc || reasoning) ? retry : null, e.retryAfter || 0);
        return;
      }
    }
    finish(); endThink(); document.removeEventListener('visibilitychange', onVis); cancelRun = null;
    if (mid && !persisted) persisted = { message_id: mid };
    const final = full();
    if (stopped) {
      if (userMsg && !c.messages.includes(userMsg)) { bubble.parentElement?.remove(); return; }   // "edit & resend" truncated the thread
      const msg = { role: 'assistant', content: final, status: 'incomplete', created: Date.now() }; if (thinkSecs) msg.thinkSecs = thinkSecs; if (mid) { msg.id = mid; bubble.parentElement.dataset.mid = mid; }
      if (sources?.length) msg.sources = sources;
      fillAssistant(bubble, final, { regen: true, thinkSecs, msg, stopped: true });
      c.messages.push(msg); c.updated = Date.now(); if (final) c.preview = clean(splitThink(final).answer); persist(); renderList();
      if (mode === 'server' && c.srv && !msg.id) resolveStoppedId(c, msg, bubble);
      if (stick) scrollBottom();
      return;
    }
    if (streamErr && STOP_CODES.has(streamErr.code)) {   // cancelled (e.g. from another device) → 중지됨
      const msg = { role: 'assistant', content: final, status: 'failed', errorCode: streamErr.code, created: Date.now() }; if (persisted?.message_id) { msg.id = persisted.message_id; bubble.parentElement.dataset.mid = msg.id; }
      fillAssistant(bubble, final, { regen: true, thinkSecs, msg }); c.messages.push(msg); persist(); renderList(); return;
    }
    if (streamErr) {   // §3.8: error event inside a 200 stream / failed status → failed message
      const fm = { role: 'assistant', content: final, status: 'failed', errorCode: streamErr.code || null, created: Date.now() }; if (persisted?.message_id) fm.id = persisted.message_id;
      if (final) { fillAssistant(bubble, final, { actions: false, thinkSecs, msg: fm }); c.messages.push(fm); persist(); } else bubble.parentElement.remove();
      const ra = +streamErr.retry_after || 0; addError(failText(streamErr.code) + raText(ra), final ? null : retry, ra);
      return;
    }
    const secs = +((performance.now() - t0) / 1000).toFixed(1);
    const ut = usageText(usage, secs);
    // AUTO-TOOLS-SPEC §5/§7: queries + a failure note, session-only. No note when cited sources exist (except blocked), none for a stopped/failed reply
    const pf = persisted?.fresh ?? persisted?.metadata?.fresh, ptools = mapTools(persisted?.tools ?? persisted?.metadata?.tools);   // persisted.fresh is the authority; without it the tool_result decides
    let note = ts.fail && (!sources?.length || ts.fail.key === 'blocked') ? ts.fail : null;
    if (pf === 'ok') note = null; else if (pf === 'unverified') note = ts.fail || freshNote({ fresh: 'unverified', tools: ptools });
    const tinfo = ts.tools.length || note ? { tools: ts.tools, note } : null; bubble._ti = tinfo;
    fillAssistant(bubble, final, { usage: ut, regen: true, thinkSecs, sources });
    const msg = { role: 'assistant', content: final, usageText: ut, created: Date.now() }; if (confs) msg.pendingActions = confs.map(scrubAction); if (sources?.length) msg.sources = sources; if (usage) msg.usage = usage; if (thinkSecs) msg.thinkSecs = thinkSecs; if (pf === 'ok' || pf === 'unverified') msg.fresh = pf; if (ptools) msg.tools = ptools;
    if (persisted?.message_id) msg.id = persisted.message_id; else if (mode === 'server') c.loaded = false;   // refetch next open
    if (tinfo && msg.id) TOOLINFO.set(msg.id, tinfo);
    c.messages.push(msg); c.updated = Date.now(); c.preview = clean(splitThink(final).answer); persist(); renderList();
    if (msg.id || mode !== 'server') { if (msg.id) bubble.parentElement.dataset.mid = msg.id; fillAssistant(bubble, final, { usage: ut, regen: true, thinkSecs, msg }); }
    if (stick) scrollBottom();
  }

  /* ---------- composer ---------- */
  let growH = -1;
  function grow() { if (!input.value) { if (growH !== 0) { input.style.height = ''; growH = 0; } } else { input.style.height = 'auto'; const h = Math.min(input.scrollHeight, 120); input.style.height = h + 'px'; growH = h; } if (!controller) sendBtn.disabled = !input.value.trim(); }
  input.addEventListener('input', grow);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey && !isTouch && !e.isComposing) { e.preventDefault(); submitComposer(); }
  });
  // 1.3.2: #composer is no longer a <form> (iOS AutoFill classifies form-associated fields and ignores autocomplete=off),
  // so the send button is type=button and submit is handled here.
  function submitComposer() {
    if (controller) { stopGeneration(); return; }
    const t = input.value.trim(); if (!t) return;
    send(t);
  }
  sendBtn.addEventListener('click', e => { e.preventDefault(); submitComposer(); });

  /* ---------- 오늘 (DIRECTION-B §4, B2): the root. A timeline of what Eve sent first and what you asked today, a "지금" line, one composer. ---------- */
  const tInput = $('#tInput'), tSend = $('#tSend');
  const todaySeenKey = 'eve.b2.todaySeen';
  // skeleton only on a cold start (no cached list) and only when 250ms have passed; `ready` = list loaded and today's threads' messages in (the stagger waits for it)
  const needMsgs = M => M.candidates.filter(c => !c.loaded && !c.loading && !c._tTried && c.srv && !c.fresh).slice(0, 10);
  const todayState = () => { const busy = listLoading || msgsPending > 0 || (mode === 'server' && needMsgs(Today.model(convs)).length > 0); return { error: listError, ready: !busy, skeleton: coldStart && busy && Date.now() - loadT0 >= 250 }; };
  const TODAY = Today?.init({
    convs: () => convs, state: todayState, userName: () => USER_NAME, preview: c => preview(c),
    retry: () => { listError = false; initServer(); }, openLog: () => go('list'),
    pend: () => pendFirst(), review: p => openPend(p), later: p => pendSnooze(p), strip: () => stripModel(), stripTap: (k, el) => stripTap(k, el),
    open: (c, mid) => (mid ? openHit(c.id, mid) : openConv(c.id)),
    stagger: () => { if (reduce.matches) return false; try { if (sessionStorage.getItem(todaySeenKey)) return false; sessionStorage.setItem(todaySeenKey, '1'); } catch { if (tSeen) return false; tSeen = true; } return true; },
  });
  /* 확인 대기 card (§4-4, §6): the oldest pending confirmation not put off with "나중에". Read-only: [검토하기] opens its thread, approval stays on the card in the thread.
     No endpoint / error / offline / cross-origin → the card is simply not drawn. */
  let pendItems = [], pendAt = 0, pendBusy = false, pendState = 'init', pendT0 = 0;   // pendState: init | ok | err | absent (no endpoint / cross-origin → the strip cell is not drawn)
  const SNZ = 'eve.b2.snooze';
  const snoozed = () => { try { const o = JSON.parse(sessionStorage.getItem(SNZ) || 'null'); return o && o.day === Today.kstDay(Date.now()) && Array.isArray(o.ids) ? o.ids : []; } catch { return []; } };
  const pendOpen = () => { const z = snoozed(); return pendItems.filter(i => !z.includes(i.id)); };   // follow-up i: items put off with "나중에" are out of the strip count, the sheet and the direct jump too
  function pendFirst() { if (pendState !== 'ok') return null; const z = snoozed(); return pendItems.find(i => !z.includes(i.id)) || null; }
  function pendSnooze(p) { try { sessionStorage.setItem(SNZ, JSON.stringify({ day: Today.kstDay(Date.now()), ids: [...snoozed(), p.id] })); } catch {} todayDirty(); }
  async function pendRefresh(force) {
    if (!PRO?.pendingList || mode !== 'server' || pendBusy || navigator.onLine === false || (!force && Date.now() - pendAt < 5000)) return;
    pendBusy = true; pendAt = Date.now(); if (pendState === 'init' && !pendT0) { pendT0 = Date.now(); setTimeout(todayDirty, 270); }
    try { const l = await PRO.pendingList(); if (l) { pendItems = l; pendState = 'ok'; } else { pendItems = []; pendState = 'absent'; } }
    catch (e) { pendItems = []; pendState = e && (e.code === 'cross_origin' || e.http === 404 || e.http === 405 || e.http === 501) ? 'absent' : 'err'; } finally { pendBusy = false; }
    todayDirty();
  }
  function openPend(p) { openHit(p.threadId, p.messageId || undefined, 'start'); }

  /* 현황 띠 (DIRECTION-B §5–§7, B3): 기억 · 확인 대기 · 오늘 일정. A cell with no data source is simply not drawn (§14); errors show "–" and are not tappable. */
  let memS = { st: 'init', n: 0, at: 0, busy: false, t0: 0 };   // st: init | ok | err | hidden
  async function memRefresh(force) {
    if (!MEM?.count || mode !== 'server' || memS.busy || navigator.onLine === false || (!force && Date.now() - memS.at < 30000)) return;
    memS.busy = true; memS.at = Date.now(); if (memS.st === 'init' && !memS.t0) { memS.t0 = Date.now(); setTimeout(todayDirty, 270); }
    try { const r = await MEM.count(); if (r === null) { memS.st = 'hidden'; memS.n = 0; } else if (r.err) memS.st = 'err'; else { memS.st = 'ok'; memS.n = r.n; } }
    catch { memS.st = memS.st === 'ok' ? 'err' : 'hidden'; } finally { memS.busy = false; }
    todayDirty(); memChipsSync();
  }
  /* 오늘 일정 follows `briefing.enabled` from GET /v1/settings when the server sends it (only an explicit false hides the cell); absent → no opinion (TODO(architect): confirm the gateway sends briefing.enabled=false rather than dropping the key when briefing is off) */
  let briefS = { off: false, at: 0, busy: false };
  async function briefRefresh(force) {
    if (!PRO?.briefingEnabled || mode !== 'server' || briefS.busy || navigator.onLine === false || (!force && Date.now() - briefS.at < 30000)) return;
    briefS.busy = true; briefS.at = Date.now();
    try { const r = await PRO.briefingEnabled(); if (r !== null) briefS.off = r === false; } catch {} finally { briefS.busy = false; }
    todayDirty();
  }
  // the "참고한 기억" chips follow the memory cell (§8.1): when the cell appears or goes away the open thread's chips are redrawn
  let memShownPrev = null;
  function memChipsSync() { const on = !!(MEM?.active?.()); if (memShownPrev !== null && memShownPrev !== on && app.dataset.route === 'chat' && !controller) renderMessages(true); memShownPrev = on; }
  const HM = new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
  const kstHM = t => { const p = HM.formatToParts(new Date(t)), g = k => (p.find(x => x.type === k) || {}).value || '00'; return `${g('hour')}:${g('minute')}`; };
  /* 오늘 일정 (§7): today's briefing message (template_kind 'briefing', briefing.date == today KST), events section. null = no data source → cell hidden. */
  function schedData(now = Date.now()) {
    if (briefS.off) return null;   // briefing.enabled === false on the server (k)
    const T = Today.kstDay(now); let best = null;
    for (const c of convs) { if (c.archived) continue; for (const m of c.messages || []) if (m.origin === 'proactive' && m.templateKind === 'briefing' && m.briefing && m.briefing.date === T && (!best || m.created > best.m.created)) best = { c, m }; }
    if (!best) return null;
    const sec = (best.m.briefing.sections || []).find(x => x.kind === 'events');
    if (!sec || !sec.ok || !(sec.count > 0)) return null;
    const end = x => Date.parse(x.end || x.start || '') || 0, past = x => !x.allDay && end(x) > 0 && end(x) < now;
    const rest = Math.max(0, sec.count - sec.items.length), trunc = sec.truncated || rest > 0;
    const left = sec.items.filter(x => !past(x)).length + rest;
    return { items: sec.items, past, left, trunc, at: best.m.created };
  }
  function stripModel() {
    if (mode !== 'server') return { cells: [], sub: '' };
    const now = Date.now(), cells = [], subs = [], skOK = t0 => t0 && now - t0 >= 250;
    if (MEM?.count && memS.st !== 'hidden') {
      if (memS.st === 'ok') { cells.push({ k: 'mem', n: String(memS.n), z: !memS.n, label: '기억', icon: 'memory', aria: `기억 ${memS.n}개` }); subs.push(`기억 ${memS.n}`); }
      else if (memS.st === 'err') cells.push({ k: 'mem', n: '–', er: true, off: true, label: '기억', icon: 'memory', aria: '기억, 불러오지 못했어요' });
      else if (skOK(memS.t0)) cells.push({ k: 'mem', sk: true, off: true, label: '기억', icon: 'memory', aria: '기억, 불러오는 중' });
    }
    if (PRO?.pendingList && pendState !== 'absent') {
      const n = pendOpen().length;
      if (pendState === 'ok') { cells.push({ k: 'pend', n: String(n), z: !n, off: !n, label: '확인 대기', icon: 'bell', aria: `확인 대기 ${n}건` }); subs.push(`대기 ${n}`); }
      else if (pendState === 'err') cells.push({ k: 'pend', n: '–', er: true, off: true, label: '확인 대기', icon: 'bell', aria: '확인 대기, 불러오지 못했어요' });
      else if (skOK(pendT0)) cells.push({ k: 'pend', sk: true, off: true, label: '확인 대기', icon: 'bell', aria: '확인 대기, 불러오는 중' });
    }
    const sd = todayState().ready ? schedData(now) : null;
    if (sd) { const n = (sd.trunc ? sd.left + '+' : String(sd.left)); cells.push({ k: 'sch', n, z: !sd.left, off: !sd.left, label: '오늘 일정', aria: `오늘 일정 ${n.replace('+', '개 이상')}${sd.trunc ? '' : '개'}, 오늘 아침 기준` }); }
    return { cells, sub: subs.join(' · ') };
  }
  /* medium sheet (shared by 확인 대기 / 오늘 일정): all text via textContent, read-only */
  const SS = $('#stripSheet'); let ssFrom = null;
  function ssClose() { if (SS.hidden) return; closeMini(SS); document.removeEventListener('keydown', ssKey, true); const f = ssFrom; ssFrom = null; setTimeout(() => { try { f && f.isConnected && f.focus({ preventScroll: true }); } catch {} }, 0); }
  function ssKey(e) { if (e.key === 'Escape') { e.stopPropagation(); ssClose(); } }
  function ssOpen(title, sub, rows, foot, from) {
    $('#ssTitle').textContent = title; const sb = $('#ssSub'); sb.textContent = sub || ''; sb.hidden = !sub;
    $('#ssList').replaceChildren(...rows); $('#ssFoot').hidden = !foot; SS.scrollTop = 0; ssFrom = from || null;
    openMini(SS, { onDismiss: ssClose }); document.addEventListener('keydown', ssKey, true); setTimeout(() => $('#ssTitle').focus({ preventScroll: true }), 60);
  }
  sheetDrag(SS, null, ssClose);
  function pendSheet(from) {
    const list = pendOpen(), rows = list.map(p => {
      const li = document.createElement('li'), b = mkEl('button', 'ss-row'); b.type = 'button'; const soon = Today.soonOf(p, Date.now());
      const t = mkEl('span', 'ss-b'); t.append(mkEl('span', 'ss-t', p.title || '확인이 필요한 일'));
      const m = mkEl('span', 'ss-m', p.verbLabel || '실행'); if (soon) { m.append(' · '); m.append(mkEl('span', 'ss-x', '곧 만료')); } t.append(m);
      const ch = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); ch.setAttribute('class', 'i'); ch.setAttribute('viewBox', '0 0 24 24'); ch.setAttribute('aria-hidden', 'true');
      const u = document.createElementNS('http://www.w3.org/2000/svg', 'use'); u.setAttribute('href', '#i-chevron-right'); ch.appendChild(u);
      b.setAttribute('aria-label', `${p.title || '확인이 필요한 일'}, ${p.verbLabel || '실행'}${soon ? ', 곧 만료' : ''}`);
      b.append(t, ch); b.addEventListener('click', () => { ssFrom = null; ssClose(); openPend(p); }); li.appendChild(b); return li;
    });
    ssOpen(`확인 대기 ${list.length}건`, '', rows, false, from);
  }
  function schedSheet(from) {
    const sd = schedData(); if (!sd || !sd.left) return;
    const rows = sd.items.map(x => {
      const li = mkEl('li', 'ss-ev' + (sd.past(x) ? ' past' : '')), fmt = x.allDay ? '종일' : (x.start ? kstHM(x.start) + (x.end ? '–' + kstHM(x.end) : '') : '');
      const b = mkEl('div', 'ss-b'); b.append(mkEl('span', 'ss-t', x.title || '(제목 없음)')); if (x.cal) b.append(mkEl('span', 'ss-m', x.cal));
      li.append(mkEl('time', 'ss-tm', fmt), b); return li;
    });
    ssOpen('오늘 일정', `오늘 아침 기준 · ${kstHM(sd.at)}`, rows, sd.trunc, from);
  }
  $('#settings')?.addEventListener('close', () => { memRefresh(true); pendRefresh(true); briefRefresh(true); });   // memory switched / items deleted in settings → the strip follows
  function stripTap(k, el) {
    if (k === 'mem') openMemoryView(null);
    else if (k === 'pend') { const l = pendOpen(); if (l.length === 1) openPend(l[0]); else if (l.length > 1) pendSheet(el); }
    else if (k === 'sch') schedSheet(el);
  }
  /* settings sheet → #memoryView (strip 기억 칸 and the "참고한 기억" chips): optional row id → scroll + 0.6s highlight; gone/none → top of the list */
  function openMemoryView(id) {
    if (!MEM) return; let n = 0, opened = false; openSettings();
    const t = setInterval(() => {
      n++; const o = $('#memOpen'), v = $('#memoryView');
      if (v.hidden && o && o.offsetParent && !opened) { opened = true; o.click(); return; }
      if (v.hidden) { if (n > 30) clearInterval(t); return; }
      const row = id ? [...v.querySelectorAll('.mem-row')].find(r => r.dataset.id === id) : null;
      if (row) { clearInterval(t); row.scrollIntoView({ block: 'center' }); row.classList.add('hl'); setTimeout(() => row.classList.remove('hl'), 600); }
      else if (n > 18 || v.querySelector('.mem-row') || (!id && v.querySelector('#memState:not([hidden])') == null && n > 4)) { clearInterval(t); v.scrollTop = 0; v.parentElement && (v.parentElement.scrollTop = 0); }
    }, 90);
  }
  function todayRender() {
    if (!TODAY) return;
    $('#todayDate').textContent = Today.dateLine();
    const M = TODAY.render();
    // pro messages live inside threads: load the messages of today's threads (and the 이어서 candidates) once, then draw again
    const need = needMsgs(M);
    if (need.length && mode === 'server') { need.forEach(c => { c._tTried = true; }); msgsPending += need.length; Promise.allSettled(need.map(c => ensureMessages(c).finally(() => { msgsPending--; }))).then(() => todayDirty()); }
  }
  function todayDirty() {
    if (!TODAY || tDirtyT) return;
    tDirtyT = requestAnimationFrame(() => { tDirtyT = 0; if (app.dataset.route === 'today' || wide.matches) todayRender(); });
  }
  function todayShow() { todayRender(); tGrow(); pendRefresh(); memRefresh(); briefRefresh(); }
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') { todayDirty(); pendRefresh(true); memRefresh(true); briefRefresh(true); } });
  setInterval(() => { if (document.visibilityState === 'visible') { TODAY?.tick(); if (app.dataset.route === 'today' || wide.matches) pendRefresh(true); else todayDirty(); if (TODAY && $('#todayList').dataset.day !== Today.kstDay(Date.now())) todayDirty(); } }, 60000);
  function tGrow() {
    if (!tInput.value) tInput.style.height = ''; else { tInput.style.height = 'auto'; tInput.style.height = Math.min(tInput.scrollHeight, 120) + 'px'; }
    tSend.disabled = controller ? false : !tInput.value.trim();
  }
  tInput.addEventListener('input', tGrow);
  let tDraftT = 0; tInput.addEventListener('input', () => { clearTimeout(tDraftT); tDraftT = setTimeout(() => { const v = tInput.value; if (v) localStorage.setItem(LS.draft + 'today', v); else localStorage.removeItem(LS.draft + 'today'); }, 300); });
  tInput.value = localStorage.getItem(LS.draft + 'today') || '';
  function todaySubmit() {
    if (controller) return stopGeneration();
    const t = tInput.value.trim(); if (!t) return;
    saveDraft();
    const c0 = cur();
    if (!(c0 && !c0.messages.length && !c0.archived)) { const c = blankConv(); convs.unshift(c); currentId = c.id; persist(); }
    tInput.value = ''; localStorage.removeItem(LS.draft + 'today'); tGrow();
    input.value = t; grow(); renderAll(); go('chat'); submitComposer();
  }
  tInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !isTouch && !e.isComposing) { e.preventDefault(); todaySubmit(); } });
  tSend.addEventListener('click', e => { e.preventDefault(); todaySubmit(); });

  /* ---------- navigation stack (NATIVE §1, §4) ---------- */
  const app = $('#app'), todayView = $('#todayView'), listView = $('#listView'), chatView = $('#chatView'), archView = $('#archiveView');
  const VIEW = { today: todayView, list: listView, archive: archView, chat: chatView };
  const RANK = { today: 0, list: 1, archive: 2, chat: 3 };
  let navTimer = 0;
  /* 1.10.0 B2 (DIRECTION-B §1): a stack  오늘 ▸ 기록 (#/log) ▸ 보관함 (#/archive)  and chat (#/t/<id>) pushed over whichever it was opened from.
     ≥761px the sidebar is always 기록; the right pane is 오늘 or the chat. */
  function syncInert() {
    const r = app.dataset.route, both = wide.matches;
    todayView.inert = both ? r === 'chat' : r !== 'today'; listView.inert = both ? r === 'archive' : r !== 'list';
    chatView.inert = r !== 'chat'; archView.inert = r !== 'archive';
  }
  function setRoute(r) {
    app.dataset.route = r; app.dataset.from = chatFrom; syncInert();
    if (r === 'list') renderList();
    if (r === 'today') { todayShow(); if (serverReady) MEM?.intro?.(); }
    if (r === 'chat') updateBackLbl();
  }
  function slide(route, dir, dur) { // CSS fallback (and always used after a swipe)
    clearTimeout(navTimer);
    app.style.setProperty('--nav-d', (dur || (dir === 'push' ? 420 : 380)) + 'ms');
    app.classList.add('transitioning'); setRoute(route);
    navTimer = setTimeout(() => { app.classList.remove('transitioning'); app.style.removeProperty('--nav-d'); }, (dur || 420) + 40);
  }
  function animateTo(route, dir) {
    const from = app.dataset.route;
    if (from === route) return syncInert();
    if (wide.matches || !app.classList.contains('ready')) return setRoute(route);
    const vtPair = (route === 'chat' && chatFrom === 'list') || (from === 'chat' && route === 'list');   // View Transitions: 기록 ↔ chat only
    if (vtPair && document.startViewTransition && !reduce.matches) {
      document.documentElement.dataset.dir = dir; app.classList.add('vt');
      (route === 'chat' ? chatView : listView).inert = false; // target screen interactive immediately
      const t = document.startViewTransition(() => setRoute(route));
      t.finished.finally(() => app.classList.remove('vt'));
    } else slide(route, dir);
  }
  const HASH = { today: '#/', list: '#/log', archive: '#/archive' };
  const hashFor = r => r === 'chat' && currentId ? '#/t/' + currentId : (HASH[r] || '#/');
  const stateFor = r => r === 'chat' ? { route: 'chat', id: currentId, from: chatFrom } : { route: r };
  function go(route) {
    if (popping) return void setTimeout(() => go(route), 50);
    const here = app.dataset.route;
    if (route === 'chat') {
      if (here !== 'chat') chatFrom = here === 'archive' ? 'archive' : here === 'list' && !wide.matches ? 'list' : 'today';
      app.dataset.from = chatFrom;
      if (history.state?.route === 'chat') history.replaceState(stateFor('chat'), '', hashFor('chat'));
      else history.pushState(stateFor('chat'), '', hashFor('chat'));
      animateTo('chat', 'push');
    } else if (route === 'list' || route === 'archive') {
      if (here === route) return;
      history.pushState(stateFor(route), '', hashFor(route)); animateTo(route, 'push');
    } else back();
  }
  let popping = false;
  const parentOf = r => r === 'chat' ? chatFrom : r === 'archive' ? 'list' : r === 'list' ? 'today' : null;
  function back() {
    const r = app.dataset.route; if (r === 'today' || popping) return;       // already at the root / pop in flight (REVIEW M1)
    if (input === document.activeElement) input.blur();
    const target = parentOf(r);
    if (history.state?.route === r) { popping = true; ignorePop++; history.back(); }   // route changes now; popstate is ignored
    else history.replaceState(stateFor(target), '', hashFor(target));
    animateTo(target, 'pop');
  }
  let ignorePop = 0;
  window.addEventListener('popstate', e => {
    popping = false;
    if (ignorePop) { ignorePop--; return; }
    const st = e.state || { route: location.hash === '#/log' ? 'list' : location.hash === '#/archive' ? 'archive' : 'today' };   // a hand-typed hash change has no state: read the route from the hash
    if (st.route === 'chat' && st.from) chatFrom = st.from;
    if (st.route === 'chat' && st.id && st.id !== currentId && (convs.some(c => c.id === st.id) || archivedList.some(c => c.id === st.id))) { saveDraft(); currentId = st.id; persist(); renderAll(); loadDraft(); ensureMessages(cur()); }
    const r = RANK[st.route] != null ? st.route : 'today';
    if (r === 'archive') loadArchive();
    if (e.hasUAVisualTransition) return setRoute(r);   // Safari already animated its own back/forward (REVIEW M2)
    animateTo(r, RANK[r] > RANK[app.dataset.route] ? 'push' : 'pop');
  });
  wide.addEventListener?.('change', syncInert);
  $('#backBtn').onclick = back;
  function updateBackLbl() { const n = { today: '오늘', list: '기록', archive: '보관함' }[chatFrom] || '오늘'; $('#backLbl').textContent = n; $('#backBtn').setAttribute('aria-label', n + '(으)로 돌아가기'); }
  $('#openLog').onclick = () => go('list');
  $('#logBack').onclick = () => { if (app.dataset.route === 'list') back(); else showToday(); };
  function showToday() { if (app.dataset.route === 'chat') back(); else if (app.dataset.route !== 'today') { history.replaceState({ route: 'today' }, '', '#/'); animateTo('today', 'pop'); } }
  /* ⋯ in the chat top bar: 새 대화 (the old pencil) */
  $('#newChat2').onclick = () => showMenu($('#newChat2'), [{ label: '새 대화', icon: 'edit', act: () => newConv() }], { align: 'right' });

  /* 기록: search mode (§9.2). The magnifier swaps the title + week strip for the field; 취소 restores them. */
  function setSearching(on) {
    listView.classList.toggle('searching', on);
    for (const e of [$('#wk'), listView.querySelector('.l-head')]) if (e) e.inert = on;   // faded out → also out of the tab order
    const f = $('#search');
    if (on) f.focus({ preventScroll: true });
    else { f.value = ''; f.blur(); onSearch(); }
    renderList();
  }
  $('#logSearch').onclick = () => setSearching(true);
  $('#searchCancel').onclick = () => setSearching(false);
  $('#search').addEventListener('keydown', e => { if (e.key === 'Escape') { e.preventDefault(); setSearching(false); } });

  /* large title collapse (§2) */
  const scroller = $('#listScroller'), lt = $('#listView .large-title'), lnav = $('#listView .navbar');
  if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => lnav.classList.toggle('collapsed', !e.isIntersecting), { root: scroller, rootMargin: '-52px 0px 0px 0px' }).observe(lt);
  scroller.addEventListener('scroll', () => { if (scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 400) loadMoreThreads(); trackWk(); }, { passive: true });
  scroller.addEventListener('scroll', () => requestAnimationFrame(() => { const y = scroller.scrollTop; lt.style.transform = y < 0 ? `scale(${1 + Math.min(-y, 60) / 600})` : ''; }), { passive: true });
  const tScroller = $('#todayScroller'), tnav = $('#todayView .navbar');
  if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => tnav.classList.toggle('collapsed', !e.isIntersecting), { root: tScroller, rootMargin: '-52px 0px 0px 0px' }).observe($('#todayTitle'));

  /* ---------- edge swipe-back, standalone only (§5): chat → where it came from, 기록 → 오늘, 보관함 → 기록 ---------- */
  const rubber = (d, lim = 120) => lim * (1 - 1 / (d / lim + 1)); // iOS-like resistance
  let g = null;
  const curX = el => { const m = getComputedStyle(el).transform; return m && m !== 'none' ? new DOMMatrix(m).m41 : 0; };
  const clearUnder = u => { u.style.transform = ''; u.style.removeProperty('--dim'); };
  function attachSwipe(view, routeName) {
    view.addEventListener('touchstart', e => {
      if (!isStandalone() || wide.matches || app.dataset.route !== routeName || e.touches.length > 1 || popping || app.classList.contains('vt') || app.classList.contains('transitioning')) return;
      const t = e.touches[0], edge = 24 + (parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--sal')) || 0);
      if (t.clientX > edge) return;
      g = { view, routeName, under: VIEW[parentOf(routeName)], x0: t.clientX, y0: t.clientY, t0: performance.now(), tl: performance.now(), xl: t.clientX, v: 0, lock: null, dx: 0, start: Math.max(0, curX(view)) };
    }, { passive: true });
    view.addEventListener('touchmove', e => {
      if (!g || g.view !== view) return; const t = e.touches[0], dx = t.clientX - g.x0, dy = t.clientY - g.y0;
      if (!g.lock) {
        if (Math.hypot(dx, dy) < 8) return;
        g.lock = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
        if (g.lock === 'x') { app.classList.add('dragging'); clearTimeout(navTimer); app.classList.remove('transitioning'); if (document.activeElement === input) input.blur(); g.under.style.visibility = 'visible'; }
      }
      if (g.lock !== 'x') return; e.preventDefault();
      const now = performance.now(); g.v = (t.clientX - g.xl) / Math.max(1, now - g.tl); g.xl = t.clientX; g.tl = now;
      const raw = g.start + dx; g.dx = raw < 0 ? -rubber(-raw, 40) : raw;
      const W = innerWidth, p = Math.min(1, Math.max(0, g.dx / W));
      view.style.transform = `translateX(${g.dx}px)`;
      g.under.style.transform = `translateX(${-30 + 30 * p}%)`;
      g.under.style.setProperty('--dim', String(.25 * (1 - p)));
    }, { passive: false });
    const endSwipe = () => {
      if (!g || g.view !== view) return; const s = g; g = null; if (s.lock !== 'x') return;
      const W = innerWidth, dxp = Math.max(0, s.dx);
      const commit = dxp > W * .5 || s.v > .5;
      const remain = commit ? 1 - dxp / W : dxp / W;
      const dur = Math.max(180, 380 * remain);
      app.classList.remove('dragging');
      view.style.transform = ''; clearUnder(s.under); s.under.style.visibility = '';
      const target = parentOf(routeName);
      if (commit) { buzz(8); slide(target, 'pop', dur); if (!popping && history.state?.route === routeName) { popping = true; ignorePop++; history.back(); } else if (!popping) history.replaceState(stateFor(target), '', hashFor(target)); }
      else slide(routeName, 'push', dur);
    };
    view.addEventListener('touchend', endSwipe); view.addEventListener('touchcancel', endSwipe);
  }
  attachSwipe(chatView, 'chat'); attachSwipe(listView, 'list'); attachSwipe(archView, 'archive');

  /* ---------- list swipe actions (§3) ---------- */
  let openRow = null, rs = null; const ACT_W = 148;
  function closeSwipe() { if (openRow) { const m = openRow.querySelector('.row-main'); m.style.transition = ''; m.style.transform = ''; openRow.classList.remove('swiped'); openRow = null; } }
  function flipRows(ul, before) {
    if (!ul || reduce.matches) return;
    const moved = [];
    ul.querySelectorAll('li.row[data-id]').forEach(r => { const t0 = before.get(r.dataset.id); if (t0 == null) return; const d = t0 - r.getBoundingClientRect().top; if (d) moved.push([r, d]); });   // reads
    moved.forEach(([r, d]) => { r.style.transform = `translateY(${d}px)`; r.style.willChange = 'transform'; });                                                                          // writes
    requestAnimationFrame(() => requestAnimationFrame(() => moved.forEach(([r]) => {
      r.classList.add('flip'); r.style.transform = '';
      r.addEventListener('transitionend', () => { r.classList.remove('flip'); r.style.willChange = ''; }, { once: true });
    })));
  }
  function swipeArchive(row, c) {
    const m = row.querySelector('.row-main'); m.style.transition = 'transform 260ms var(--ease-sheet)'; m.style.transform = 'translateX(-100%)';
    row.classList.add('removing', 'collapsing');   // M3: opacity + scale(.98); rows below FLIP up (no height animation)
    setTimeout(() => {
      const ul = row.parentElement, before = new Map();
      ul && ul.querySelectorAll('li.row[data-id]').forEach(r => before.set(r.dataset.id, r.getBoundingClientRect().top));   // read
      openRow = null; archiveConv(c);
      flipRows(ul, before);
    }, 200);
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
    copy: ICON.copy, regen: ICON.regen, edit: ICON.edit, trash: ICON.trash, share: icon('share'), send: icon('send'), archive: icon('archive'),
    select: svg('<path d="M5 4h4M5 20h4M7 4v16M13 8h7M13 12h7M13 16h5"/>'),
    pin: svg('<path d="M9 4h6l-1 6 3 3H7l3-3Z"/><path d="M12 13v7"/>')
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
  // 1.6.0 (eve-serving #65, identity-transport §4/§6): 401 = no/expired session → pairing code entry (POST /v1/pair → 204 + eve_session cookie).
  // 401 invalid_session (or 401 after we were paired) → re-pair notice. 403 identity_not_allowed keeps its own notice;
  // 403 scope_denied is NOT an auth failure (session kept, errMsg shows a not-allowed message).
  // Codes: 8-char Crockford, 10 min, single use; 5 failures lock pairing 10 min and void codes. Server only says pair_failed,
  // so the lock is tracked client-side (count + until) — no codes/tokens are ever stored.
  const PAIRED = 'eve.paired', PLOCK = 'eve.pairLock', MAXF = 5, LOCK_MS = 10 * 60e3;
  const pairEl = $('#pairForm'), pairIn = $('#pairCode'), pairErr = $('#pairErr'), pairBtn = $('#pairSubmit'), pairHint = $('#pairHint');
  const normCode = v => String(v || '').toUpperCase().replace(/[^0-9A-Z]/g, '').replace(/O/g, '0').replace(/[IL]/g, '1').replace(/U/g, 'V').slice(0, 8);   // Crockford base32
  const fmtCode = c => c.length > 4 ? c.slice(0, 4) + '-' + c.slice(4) : c;
  const lockState = () => { const l = load(PLOCK, null) || {}; return { fails: l.fails | 0, until: +l.until || 0 }; };
  let lockTimer = 0;
  function renderLock() {
    const { fails, until } = lockState(), left = until - Date.now();
    clearTimeout(lockTimer);
    if (left > 0) {
      const m = Math.ceil(left / 60e3);
      pairIn.disabled = true; pairBtn.disabled = true; authEl.querySelector('.auth-card').dataset.pair = 'locked';
      pairErr.textContent = `시도가 너무 많아 잠겼어요. ${m}분 뒤에 새 코드를 받아 입력해 주세요.`; pairErr.hidden = false;
      lockTimer = setTimeout(renderLock, Math.min(left, 30e3)); return true;
    }
    if (until) { save(PLOCK, { fails: 0, until: 0 }); pairErr.hidden = true; }
    pairIn.disabled = false; pairBtn.disabled = normCode(pairIn.value).length !== 8; authEl.querySelector('.auth-card').dataset.pair = fails ? 'failed' : 'entry';
    return false;
  }
  function showAuthNotice(retry, code) {
    const denied = code === 'identity_not_allowed', pair = !denied;
    const repair = pair && (code === 'invalid_session' || localStorage.getItem(PAIRED) === '1');
    $('#authTitle').textContent = denied ? '이 계정은 쓸 수 없어요' : repair ? '다시 연결해 주세요' : '이 기기를 연결해 주세요';
    $('#authBody').textContent = denied ? '허용된 Tailscale 계정으로 로그인한 뒤 다시 시도해 주세요.'
      : repair ? '연결이 만료됐거나 해제됐어요. Eve 서버에서 새 연결 코드를 받아 입력해 주세요.' : 'Eve 서버에서 받은 8자리 연결 코드를 입력해 주세요.';
    const card = authEl.querySelector('.auth-card'); card.classList.toggle('pairing', pair); card.dataset.pair = pair ? 'entry' : '';
    pairEl.hidden = !pair; $('#authRetry').textContent = pair ? '이미 연결했어요' : '다시 시도';
    if (retry) authRetry = retry;
    if (!authEl.hidden) { if (pair) renderLock(); return; }
    pairIn.value = ''; pairErr.hidden = true; pairIn.removeAttribute('aria-invalid');
    if (pair) renderLock();
    authEl.hidden = false; requestAnimationFrame(() => { authEl.classList.add('in'); if (pair && !pairIn.disabled && !matchMedia('(pointer:coarse)').matches) pairIn.focus(); });
  }
  pairIn.addEventListener('input', () => { const c = normCode(pairIn.value); pairIn.value = fmtCode(c); pairBtn.disabled = c.length !== 8; if (!lockState().fails) pairErr.hidden = true; pairIn.removeAttribute('aria-invalid'); });
  pairEl.addEventListener('submit', async ev => {
    ev.preventDefault(); const c = normCode(pairIn.value); if (c.length !== 8 || renderLock()) return;
    pairBtn.disabled = true; pairBtn.textContent = '연결 중…';
    let r = null;
    try { r = await fetch(apiBase() + '/v1/pair', { method: 'POST', cache: 'no-store', credentials: 'same-origin', headers: headers('POST'), body: JSON.stringify({ code: fmtCode(c) }) }); }
    catch { pairErr.textContent = '서버에 연결할 수 없어요. 연결 상태를 확인해 주세요.'; pairErr.hidden = false; pairBtn.textContent = '연결'; pairBtn.disabled = false; return; }
    pairBtn.textContent = '연결';
    if (!r.ok) {
      if (r.status !== 401) { pairErr.textContent = '지금은 연결할 수 없어요. 잠시 뒤 다시 시도해 주세요.'; pairErr.hidden = false; pairBtn.disabled = false; return; }   // not a code failure: don't count
      const fails = lockState().fails + 1;
      save(PLOCK, fails >= MAXF ? { fails: 0, until: Date.now() + LOCK_MS } : { fails, until: 0 });
      pairIn.setAttribute('aria-invalid', 'true'); buzz(20);
      if (renderLock()) return;
      pairErr.textContent = `코드가 맞지 않거나, 이미 썼거나, 10분이 지났어요. 남은 시도 ${MAXF - fails}번`; pairErr.hidden = false; pairBtn.disabled = false; return;
    }
    save(PLOCK, { fails: 0, until: 0 }); localStorage.setItem(PAIRED, '1');
    if (await checkAuth()) { const f = authRetry; authRetry = null; clearErrors(); if (f) f(); }
  });
  function hideAuthNotice() { authEl.classList.remove('in'); authEl.hidden = true; }
  async function checkAuth() {
    try {
      const r = await fetch(apiBase() + '/whoami', { cache: 'no-store' });
      const j = await r.json().catch(() => null);
      if (isAuthFail(r.status, authCode(j)) || (r.ok && j && j.authenticated === false)) { whoami = null; renderWho(); clearCards(); showAuthNotice(null, authCode(j)); return false; }   // signed out: drop stored card contents
      if (r.ok) { whoami = j; renderWho(); localStorage.setItem(PAIRED, '1'); }
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
        if (isAuthFail(r.status, authCode(body))) showAuthNotice(loadModels, authCode(body));
        throw Object.assign(new Error(errMsg(r.status, body)), { http: r.status });
      }
      const j = await r.json(); const ids = (j.data || []).map(m => m.id);
      setModelOptions(ids); st.textContent = `연결 성공 · 모델 ${ids.length}개`;
    } catch (e) { st.className = 'status err'; st.textContent = e.http ? e.message : '연결 실패: ' + e.message; }
  }
  const crossOrigin = b => { if (!b) return false; try { return new URL(b, location.href).origin !== location.origin; } catch { return true; } };
  const baseWarn = () => { $('#sBaseWarn').hidden = !crossOrigin(normBase($('#sBase').value)); };   // other origin: all calls go there, approve blocked
  $('#sBase').addEventListener('input', baseWarn);
  function openSettings() {
    renderSync(); { const mg = localStorage.getItem(LS.migrated); $('#sMigrateRow').hidden = !(mode === 'server' && localConvs().length && (!mg || mg === 'skip')); }
    $('#sBase').value = settings.base; $('#sSystem').value = settings.system; baseWarn();
    $('#sShowThink').checked = settings.showThink; $('#sNoThink').checked = !!settings.noThink;
    setModelOptions([]); $('#sStatus').textContent = '';
    $('#a2hsRow').hidden = isStandalone();
    snap = formState();
    document.body.classList.add('sheet-open'); dlg.showModal(); sform.scrollTop = 0;
    renderWho(); loadModels(); $('#sModelInfo').textContent = shortModel() || '—'; PRO?.openSettings(); MEM?.openSettings();
  }
  $('#openSettings').onclick = openSettings; $('#openSettings3').onclick = openSettings;
  $('#sMigrate').onclick = () => animateOut(dlg, () => { dlg.close(); localStorage.removeItem(LS.migrated); save(LS.snooze, { until: 0, n: 0 }); openMigrate(); });
  $('#sSyncNow').onclick = () => { outboxState.items.forEach(o => o.nextAt = 0); outboxState.failed = 0; flushOutbox(); initServer(); };
  $('#loadModels').onclick = loadModels;
  $('#cancelSettings').onclick = () => closeSettings();
  $('#showA2hs').onclick = () => animateOut(dlg, () => { dlg.close(); openA2HS(true); });
  sform.addEventListener('submit', () => {
    settings = { noThink: $('#sNoThink').checked, base: normBase($('#sBase').value), model: $('#sModel').value || DEFAULT_MODEL, system: $('#sSystem').value, showThink: $('#sShowThink').checked };
    save(LS.settings, settings); renderMessages(); PRO?.saveSettings();
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
  window.addEventListener('online', () => { setOffline(false); flushOutbox(); kickStream?.(); initServer(); }); window.addEventListener('offline', () => setOffline(true));
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
  const hm = location.hash.match(/^#\/(?:t|c)\/(.+)$/);
  let route = 'today', bootTid = null;   // 1.10.0 B2: the app opens on 오늘; only an explicit hash deep-links elsewhere
  if (hm) { let id = hm[1]; try { id = decodeURIComponent(id); } catch {} if (convs.some(c => c.id === id)) { currentId = id; route = 'chat'; } else bootTid = id; }
  else if (location.hash === '#/log') route = 'list'; else if (location.hash === '#/archive') route = 'archive';
  if (currentId && !cur()) currentId = convs[0]?.id || null;
  if (!cur() && convs.length && route === 'chat') currentId = convs[0].id;
  history.replaceState({ route: 'today' }, '', location.pathname + (params.has('nid') ? location.search : '') + '#/');   // keep ?nid for EveProactive.init (it strips it)
  if (Proactive) try {
    PRO = Proactive.init({ api, ready: () => serverReady, sameOrigin: () => !crossOrigin(apiBase()), enqueue, convs: () => convs, unstick: () => { stick = false; }, reload: c => { c.loaded = false; ensureMessages(c); }, online: () => navigator.onLine !== false, cur, renderList, openConv: id => openConv(id), openHit, showToast, isServer: () => mode === 'server', isStandalone, route: () => app.dataset.route });
  } catch (e) { console.warn('[llmchat] proactive init failed', e); }
  // Part B memory UI: behind localStorage flag 'eve.flag.memory' (off by default → MEM stays null)
  // source chips: chip toggle, citation tap → expand + scroll + highlight, 모두 보기 sheet, favicon → monogram fallback
  const reduceMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  function setSrcOpen(sec, open) {
    const chips = sec.querySelectorAll('.sc'), list = sec.querySelector('.src-list'); if (!chips.length || !list) return;
    chips.forEach(c => c.setAttribute('aria-expanded', String(open))); sec.classList.toggle('open', open);
    if (open) { list.hidden = false; list.classList.remove('in'); void list.offsetWidth; list.classList.add('in'); }
    else if (reduceMotion()) list.hidden = true;
    else { list.classList.remove('in'); const fin = e => { if (e.target !== list || e.propertyName !== 'opacity') return; list.removeEventListener('transitionend', fin); if (!sec.classList.contains('open')) list.hidden = true; }; list.addEventListener('transitionend', fin); }
    if (open && sec.closest('.msg') === [...document.querySelectorAll('#messages .msg')].pop()) { // last message: bring the opened list into view once it has settled
      const go = () => list.scrollIntoView({ block: 'nearest', behavior: reduceMotion() ? 'auto' : 'smooth' });
      if (reduceMotion()) go(); else { const fin = e => { if (e.target !== list || e.propertyName !== 'transform') return; list.removeEventListener('transitionend', fin); go(); }; list.addEventListener('transitionend', fin); } }
  }
  function closeSrcSheet(d) { if (d.open && !d.classList.contains('closing')) animateOut(d, () => d.close()); }
  function openSrcSheet(sec) {
    let d = document.getElementById('srcSheet');
    if (!d) { d = document.createElement('dialog'); d.id = 'srcSheet'; d.className = 'src-sheet'; d.setAttribute('aria-labelledby', 'srcSheetTitle'); document.body.appendChild(d);
      d.addEventListener('click', e => { if (e.target === d || e.target.closest('.src-close')) closeSrcSheet(d); }); d.addEventListener('cancel', e => { e.preventDefault(); closeSrcSheet(d); }); d.addEventListener('close', () => document.body.classList.remove('sheet-open')); }
    const n = sec.querySelectorAll('.src-all-tpl')[0]?.content.querySelectorAll('.src-item').length || 0;
    d.innerHTML = `<div class="grabber" aria-hidden="true"></div><div class="src-sheet-head"><h3 id="srcSheetTitle">출처 ${n}개</h3><button type="button" class="text-btn src-close">닫기</button></div><div class="src-sheet-body"></div>`;
    d.querySelector('.src-sheet-body').appendChild(sec.querySelector('.src-all-tpl').content.cloneNode(true));
    document.body.classList.add('sheet-open'); d.showModal();
  }
  document.addEventListener('click', e => {
    const chip = e.target.closest?.('.sources .sc');
    if (chip) { const sec = chip.closest('.sources'); setSrcOpen(sec, chip.getAttribute('aria-expanded') !== 'true'); return; }
    const all = e.target.closest?.('.sources .src-all'); if (all) { openSrcSheet(all.closest('.sources')); return; }
    const cite = e.target.closest?.('sup.cite a[data-n]'); if (!cite) return;
    const sec = cite.closest('.bubble')?.querySelector('.sources'); if (!sec) return; // streaming: no row yet → default link
    e.preventDefault();
    const n = cite.dataset.n.split(',')[0]; setSrcOpen(sec, true);
    let it = sec.querySelector(`.src-list .src-item[data-n="${n}"]`);
    if (!it) { openSrcSheet(sec); it = document.querySelector(`#srcSheet .src-item[data-n="${n}"]`); }
    if (!it) return;
    it.scrollIntoView({ block: 'nearest', behavior: reduceMotion() ? 'auto' : 'smooth' });
    it.classList.remove('hl'); void it.offsetWidth; it.classList.add('hl'); setTimeout(() => it.classList.remove('hl'), 600);
  });
  document.addEventListener('error', e => { const img = e.target; if (img?.tagName === 'IMG' && img.dataset.mono && img.parentElement?.classList.contains('fav')) { const f = img.parentElement; f.classList.add('mono'); f.textContent = img.dataset.mono; } }, true);
  try { MEM = Memory?.init({ api, isServer: () => mode === 'server', showToast, route: () => app.dataset.route, openSettings: () => openSettings(),
    busy: () => !!(document.querySelector('dialog[open], .mini-sheet:not([hidden]), #authNotice:not([hidden])') || [...document.querySelectorAll('.confirm-card')].some(c => c.offsetParent && c.dataset.state === 'pending')) }) || null; } catch (e) { console.warn('[llmchat] memory init failed', e); }
  renderAll(); loadDraft();
  if (params.has('new')) newConv();
  else if (route === 'chat') { history.pushState(stateFor('chat'), '', hashFor('chat')); setRoute('chat'); }
  else if (route === 'list') { history.pushState(stateFor('list'), '', hashFor('list')); setRoute('list'); }
  else if (route === 'archive') { history.pushState(stateFor('list'), '', hashFor('list')); history.pushState(stateFor('archive'), '', hashFor('archive')); loadArchive(); setRoute('archive'); }
  else setRoute('today');
  const sc = currentId && load(LS.scroll, {})[currentId];
  if (sc > 0) requestAnimationFrame(() => requestAnimationFrame(() => { box.scrollTop = sc; stick = false; }));
  requestAnimationFrame(() => app.classList.add('ready'));
  grow();
  if (cur()) ensureMessages(cur());
  renderSync();
  checkAuth().then(ok => { if (ok) maybeA2HS(); return initServer(); }).then(() => { if (bootTid && mode === 'server') openHit(bootTid); });

  const APP_VERSION = '__EVE_VERSION__'; console.info('[llmchat] app', APP_VERSION);
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
  window.__app = { version: APP_VERSION, newChat: newConv, route: () => app.dataset.route, today: () => TODAY?.model(), shell: () => self.EveShell?.state(), enqueue, clearCards, msgs: () => cur()?.messages, showToast, go, isStandalone, state: () => ({ mode, outbox: outboxState.items.length, convs: convs.length, currentId }) };
}
