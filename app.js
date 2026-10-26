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
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function inlineMd(s) { // s already escaped; code spans are protected from emphasis
  const codes = [];
  s = s.replace(/`([^`\n]+)`/g, (_, c) => `\u0000${codes.push(c) - 1}\u0000`);
  s = s
    .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[i]}</code>`);
}
// Index where the "stable" (completed) markdown ends: last blank line outside any code fence.
function stableCut(s) {
  let i = s.length;
  while ((i = s.lastIndexOf('\n\n', i - 1)) >= 0) {
    const fences = (s.slice(0, i).match(/```/g) || []).length;
    if (fences % 2 === 0) return i + 2;
    if (i === 0) break;
  }
  return 0;
}
function renderMarkdown(src) {
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
    const lines = escapeHtml(part).split('\n');
    let list = null, para = [];
    const flushP = () => { if (para.length) { out.push('<p>' + inlineMd(para.join('<br>')) + '</p>'); para = []; } };
    const flushL = () => { if (list) { out.push(`<${list.t}>` + list.items.map(x => '<li>' + inlineMd(x) + '</li>').join('') + `</${list.t}>`); list = null; } };
    for (const line of lines) {
      let m;
      if ((m = line.match(/^(#{1,6})\s+(.*)/))) { flushP(); flushL(); const n = Math.min(m[1].length + 2, 6); out.push(`<h${n}>${inlineMd(m[2])}</h${n}>`); }
      else if ((m = line.match(/^\s*[-*+]\s+(.*)/))) { flushP(); if (!list || list.t !== 'ul') { flushL(); list = { t: 'ul', items: [] }; } list.items.push(m[1]); }
      else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) { flushP(); if (!list || list.t !== 'ol') { flushL(); list = { t: 'ol', items: [] }; } list.items.push(m[1]); }
      else if (!line.trim()) { flushP(); flushL(); }
      else { flushL(); para.push(line); }
    }
    flushP(); flushL();
  });
  return out.join('');
}
if (typeof module !== 'undefined') module.exports = { createSSEParser, splitThink, renderMarkdown, escapeHtml, stableCut };

/* ---------- app ---------- */
if (typeof document !== 'undefined') (function () {
  const $ = s => document.querySelector(s);
  const svg = d => `<svg viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
  const ICON = {
    copy: COPY_SVG,
    check: svg('<path d="M5 12l5 5 9-10"/>'),
    regen: svg('<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>'),
    warn: svg('<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16.5v.01"/>'),
    chev: '<svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>',
    spark: svg('<path d="M12 3l1.9 5.6 5.6 1.9-5.6 1.9L12 18l-1.9-5.6-5.6-1.9 5.6-1.9Z"/>'),
    edit: svg('<path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>'),
    trash: svg('<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>')
  };
  const LS = { settings: 'llmchat.settings', convs: 'llmchat.convs', current: 'llmchat.current', route: 'llmchat.route', scroll: 'llmchat.scroll', draft: 'llmchat.draft:' };
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
  let convs = load(LS.convs, []);
  let currentId = load(LS.current, null);
  let controller = null;

  const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  const cur = () => convs.find(c => c.id === currentId);
  const persist = () => { save(LS.convs, convs); save(LS.current, currentId); };
  const normBase = b => (b || '').trim().replace(/\/+$/, '').replace(/\/v1$/, ''); // '' => relative /v1/... (same origin)
  const apiBase = () => normBase(settings.base);
  const headers = () => ({ 'Content-Type': 'application/json' });   // no Authorization: gateway trusts Tailscale identity
  let whoami = null;
  const shortModel = () => (settings.model || '').split('/').pop();
  const isTouch = matchMedia('(pointer:coarse)').matches;
  const box = $('#messages'), input = $('#input'), sendBtn = $('#sendBtn');

  /* ---------- viewport / keyboard (NATIVE §9) ---------- */
  const root = document.documentElement.style;
  const vv = window.visualViewport;
  let vvRaf = 0;
  function syncVV() {
    if (vvRaf) return;
    vvRaf = requestAnimationFrame(() => {
      vvRaf = 0; const h = vv ? vv.height : window.innerHeight;
      root.setProperty('--vvh', h + 'px');
      document.body.classList.toggle('kb-open', window.innerHeight - h > 120);
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
  }, { passive: true });
  $('#toBottom').onclick = () => { stick = true; scrollBottom(true); };
  syncVV();

  /* ---------- conversation list (NATIVE §3) ---------- */
  const CHEV_R = '<svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>';
  let genId = null;
  function newConv() {
    const c0 = cur();
    if (c0 && !c0.messages.length && !controller) { openConv(c0.id); if (!isTouch) input.focus(); return; } // reuse empty chat
    if (controller) controller.abort();
    saveDraft();
    const c = { id: uid(), title: '새 대화', messages: [], updated: Date.now() };
    convs.unshift(c); currentId = c.id; persist(); input.value = ''; grow(); renderAll(); go('chat'); if (!isTouch) input.focus();
  }
  function openConv(id) {
    if (id !== currentId) { saveDraft(); currentId = id; persist(); renderAll(); loadDraft(); }
    go('chat');
  }
  function renameConv(c) { const t = prompt('대화 이름', c.title); if (t && t.trim()) { c.title = t.trim(); persist(); renderAll(); } }
  function deleteConv(c) {
    if (genId === c.id && controller) controller.abort();
    convs = convs.filter(x => x.id !== c.id); localStorage.removeItem(LS.draft + c.id);
    if (currentId === c.id) { currentId = convs[0]?.id || null; loadDraft(); }
    persist(); renderAll(); buzz(15);
  }
  function groupLabel(t) {
    const d0 = new Date(); d0.setHours(0, 0, 0, 0); const day = 864e5;
    if (t >= d0) return '오늘'; if (t >= d0 - day) return '어제'; if (t >= d0 - 6 * day) return '지난 7일'; return '이전';
  }
  function fmtTime(t) {
    const d = new Date(t), d0 = new Date(); d0.setHours(0, 0, 0, 0);
    if (t >= d0) return d.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' });
    if (t >= d0 - 864e5) return '어제';
    return `${d.getMonth() + 1}월 ${d.getDate()}일`;
  }
  function preview(c) {
    for (let i = c.messages.length - 1; i >= 0; i--) {
      const m = c.messages[i]; const t = m.role === 'assistant' ? splitThink(m.content).answer : m.content;
      if (t && t.trim()) return t.replace(/```[\s\S]*?(```|$)/g, ' [코드] ').replace(/[#*`>_|]+/g, '').replace(/\s+/g, ' ').trim().slice(0, 140);
    }
    return '메시지 없음';
  }
  function renderList() {
    const ul = $('#convList'); ul.innerHTML = '';
    const q = ($('#search').value || '').trim().toLowerCase();
    convs.sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0) || b.updated - a.updated);
    const list = convs.filter(c => !q || c.title.toLowerCase().includes(q) || c.messages.some(m => (m.content || '').toLowerCase().includes(q)));
    $('#listEmpty').hidden = !!convs.length;
    let lastG = null;
    list.forEach(c => {
      const g = c.pinned ? '고정됨' : groupLabel(c.updated || 0);
      if (g !== lastG) { const h = document.createElement('li'); h.className = 'group-label'; h.textContent = g; ul.appendChild(h); lastG = g; }
      const li = document.createElement('li'); li.className = 'row' + (c.id === currentId ? ' active' : ''); li.dataset.id = c.id;
      li.innerHTML = `<div class="row-actions"><button type="button" class="ra-rename" tabindex="-1">이름 변경</button><button type="button" class="ra-del" tabindex="-1">삭제</button></div>
        <div class="row-main"><div class="row-top"><span class="row-title"></span><time></time>${CHEV_R}</div><div class="row-sub"></div></div>`;
      li.querySelector('.row-title').textContent = (c.pinned ? '📌 ' : '') + c.title;
      li.querySelector('time').textContent = fmtTime(c.updated || Date.now());
      const sub = li.querySelector('.row-sub');
      if (genId === c.id) sub.innerHTML = '<span class="spin" aria-hidden="true"></span>답변 중…'; else sub.textContent = preview(c);
      ul.appendChild(li);
    });
    if (q && !list.length) ul.innerHTML = '<li class="no-results">결과 없음</li>';
  }
  $('#search').addEventListener('input', renderList);
  $('#search').addEventListener('search', renderList);
  const convOf = el => convs.find(c => c.id === el.closest('.row')?.dataset.id);
  $('#convList').addEventListener('click', e => {
    if (suppressClick) return;
    const row = e.target.closest('.row'); if (!row) return; const c = convOf(row); if (!c) return;
    if (e.target.closest('.ra-rename')) { closeSwipe(); return renameConv(c); }
    if (e.target.closest('.ra-del')) return swipeDelete(row, c);
    if (openRow) return closeSwipe();
    openConv(c.id);
  });

  /* ---------- messages ---------- */
  function addMsgEl(role, content) {
    const wrap = document.createElement('div'); wrap.className = 'msg ' + role;
    const b = document.createElement('div'); b.className = 'bubble'; wrap.appendChild(b);
    if (role === 'user') b.textContent = content;
    box.appendChild(wrap); return b;
  }
  // opts: { live, thinkSecs, usage, actions }
  function freshen(tail) { // token fade on the newest text of the tail block
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
      bubble.querySelectorAll('.typing,.warming').forEach(n => n.remove());
      const nm = document.createElement('div'); nm.className = 'md cursor'; nm.innerHTML = '<div class="stable"></div><div class="tail"></div>';
      bubble.appendChild(nm); bubble._cut = 0; return patchLive(bubble, think, answer, thinking);
    }
    const cut = stableCut(answer);
    if (cut !== bubble._cut) { md.querySelector('.stable').innerHTML = renderMarkdown(answer.slice(0, cut)); bubble._cut = cut; }
    const tail = md.querySelector('.tail'); tail.innerHTML = renderMarkdown(answer.slice(cut)); freshen(tail);
    return true;
  }
  function fillAssistant(bubble, text, opts = {}) {
    const { think, answer, thinking } = splitThink(text);
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
    if (waiting) html += `<span class="typing"><i></i><i></i><i></i></span>${opts.slow ? '<div class="warming">모델 준비 중…</div>' : ''}`;
    else if (live && !answer.trim()) { /* still thinking: no answer container yet */ }
    else if (live) { const cut = stableCut(answer); bubble._cut = cut; html += `<div class="md cursor"><div class="stable">${renderMarkdown(answer.slice(0, cut))}</div><div class="tail">${renderMarkdown(answer.slice(cut))}</div></div>`; }
    else html += `<div class="md">${renderMarkdown(answer)}</div>`;
    bubble._live = live;
    const userToggled = prev?.dataset.user;
    bubble.innerHTML = html;
    const det = bubble.querySelector('details.think');
    if (det) { if (userToggled) det.dataset.user = '1'; det.querySelector('summary').addEventListener('click', () => { det.dataset.user = '1'; }); }
    if (live) { const tail = bubble.querySelector('.md .tail'); if (tail) freshen(tail); }
    const msg = bubble.parentElement;
    msg.querySelector('.actions')?.remove();
    if (!live && opts.actions !== false) {
      const a = document.createElement('div'); a.className = 'actions';
      a.innerHTML = `<button type="button" class="c" aria-label="복사">${ICON.copy}</button>${opts.regen ? `<button type="button" class="r" aria-label="다시 생성">${ICON.regen}</button>` : ''}${opts.usage ? `<span class="usage">${escapeHtml(opts.usage)}</span>` : ''}`;
      a.querySelector('.c').onclick = e => copyText(e.currentTarget, answer.trim());
      a.querySelector('.r')?.addEventListener('click', regenerate);
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
  function usageText(u, secs) {
    if (!u) return secs ? `${secs}s` : '';
    const ct = u.completion_tokens;
    const rate = secs && ct ? ` · ${(ct / secs).toFixed(0)} tok/s` : '';
    return `입력 ${u.prompt_tokens ?? '?'} · 출력 ${ct ?? '?'} tok${rate}`;
  }

  const CHIPS = [['코드 리뷰', '이 함수의 개선점을 알려줘'], ['요약', '긴 글을 핵심 3줄로 정리해줘'], ['번역', '자연스러운 영어 문장으로 바꿔줘'], ['아이디어', '주말에 할 사이드 프로젝트 추천']];
  function renderEmpty() {
    box.innerHTML = `<div class="empty"><div class="mark"></div><h1>무엇을 도와드릴까요?</h1><small>${escapeHtml(shortModel() || '로컬 모델')} · 로컬에서 실행 중</small>
      <div class="chips">${CHIPS.map((c, i) => `<button type="button" class="chip" style="animation-delay:${80 + i * 40}ms" data-q="${escapeHtml(c[1])}"><b>${escapeHtml(c[0])}</b><span>${escapeHtml(c[1])}</span></button>`).join('')}</div></div>`;
    box.querySelectorAll('.chip').forEach(b => b.onclick = () => { if (!controller) send(b.dataset.q); });
  }
  function renderMessages() {
    box.innerHTML = '';
    const c = cur();
    $('#title').textContent = c ? c.title : '새 대화';
    $('#modelName').textContent = shortModel();
    if (!c || !c.messages.length) return renderEmpty();
    box.classList.add('no-anim');
    const lastA = c.messages.map(m => m.role).lastIndexOf('assistant');
    c.messages.forEach((m, i) => {
      if (m.role === 'user') addMsgEl('user', m.content);
      else fillAssistant(addMsgEl('assistant'), m.content, { usage: m.usageText || (m.usage ? usageText(m.usage) : ''), regen: i === lastA && i === c.messages.length - 1, thinkSecs: m.thinkSecs });
    });
    requestAnimationFrame(() => { box.classList.remove('no-anim'); stick = true; scrollBottom(); });
  }
  function renderAll() { renderList(); renderMessages(); }

  function setBusy(b) {
    sendBtn.classList.toggle('stop', b);
    sendBtn.disabled = b ? false : !input.value.trim();
    sendBtn.setAttribute('aria-label', b ? '중지' : '전송');
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
    if (!c) { c = { id: uid(), title: '새 대화', messages: [], updated: Date.now() }; convs.unshift(c); currentId = c.id; }
    if (!c.messages.length) { box.innerHTML = ''; c.title = text.slice(0, 30); $('#title').textContent = c.title; }
    clearErrors();
    box.querySelectorAll('.actions .r').forEach(r => r.remove());
    c.messages.push({ role: 'user', content: text });
    c.updated = Date.now(); persist(); renderList();
    addMsgEl('user', text);
    input.value = ''; grow(); stick = true; scrollBottom(true);
    return generate(c);
  }
  function regenerate() {
    const c = cur(); if (controller || !c) return;
    if (c.messages.at(-1)?.role === 'assistant') c.messages.pop();
    const els = box.querySelectorAll('.msg.assistant'); els[els.length - 1]?.remove();
    clearErrors(); persist(); generate(c);
  }

  async function generate(c) {
    const bubble = addMsgEl('assistant');
    const hist = c.messages.map(({ role, content }) => ({ role, content: role === 'assistant' ? splitThink(content).answer : content }));
    if (settings.noThink) { const last = hist[hist.length - 1]; if (last && last.role === 'user' && !/\/no_think\s*$/.test(last.content)) last.content += ' /no_think'; }
    const msgs = (settings.system ? [{ role: 'system', content: settings.system }] : []).concat(hist);
    controller = new AbortController(); setBusy(true);
    let acc = '', reasoning = '', usage = null, streamErr = null, slow = false, thinkStart = 0, thinkSecs = 0;
    const t0 = performance.now();
    const full = () => reasoning ? `<think>${reasoning}</think>${acc}` : acc;
    const view = () => reasoning && !acc ? '<think>' + reasoning : full();
    fillAssistant(bubble, '', { live: true }); scrollBottom(true);
    const slowTimer = setTimeout(() => { if (!acc && !reasoning) { slow = true; fillAssistant(bubble, '', { live: true, slow }); } }, 3000);
    let raf = 0;
    const paint = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; fillAssistant(bubble, view(), { live: true }); if (stick) scrollBottom(); }); };
    const retry = () => generate(c);
    const finish = () => { clearTimeout(slowTimer); controller = null; setBusy(false); if (raf) cancelAnimationFrame(raf); raf = 0; };
    const markThink = () => { if (!thinkStart) thinkStart = performance.now(); };
    const endThink = () => { if (thinkStart && !thinkSecs) thinkSecs = Math.max(1, Math.round((performance.now() - thinkStart) / 1000)); };
    try {
      const res = await fetch(apiBase() + '/v1/chat/completions', {
        method: 'POST', headers: headers(), signal: controller.signal,
        body: JSON.stringify({ model: settings.model || undefined, messages: msgs, stream: true, stream_options: { include_usage: true } })
      });
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
        acc = m.content || ''; reasoning = m.reasoning || m.reasoning_content || ''; usage = j.usage || null;
      } else {
        const reader = res.body.getReader(); const dec = new TextDecoder(); let done = false;
        const parser = createSSEParser(data => {
          if (data.trim() === '[DONE]') { done = true; return; }
          let j; try { j = JSON.parse(data); } catch { return; }
          if (j.error) { streamErr = j.error; return; }
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
        while (!done) { const { value, done: rd } = await reader.read(); if (rd) break; parser.push(dec.decode(value, { stream: true })); }
        parser.flush();
        if (!done) try { reader.cancel(); } catch {}
      }
    } catch (e) {
      finish();
      if (e.name === 'AbortError') { acc += (acc ? '\n\n' : '') + '*(중지됨)*'; }
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
    if (streamErr) {
      if (final) { fillAssistant(bubble, final, { actions: false, thinkSecs }); c.messages.push({ role: 'assistant', content: final }); persist(); } else bubble.parentElement.remove();
      addError(`스트리밍 중 오류: ${streamErr.message || streamErr.code || '알 수 없음'}${streamErr.code ? ' (' + streamErr.code + ')' : ''}`, final ? null : retry);
      return;
    }
    const secs = +((performance.now() - t0) / 1000).toFixed(1);
    const ut = usageText(usage, secs);
    fillAssistant(bubble, final, { usage: ut, regen: true, thinkSecs });
    const msg = { role: 'assistant', content: final, usageText: ut }; if (usage) msg.usage = usage; if (thinkSecs) msg.thinkSecs = thinkSecs;
    c.messages.push(msg); c.updated = Date.now(); persist(); renderList();
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
    if (controller) { controller.abort(); return; }
    const t = input.value.trim(); if (!t) return;
    send(t);
  });

  /* ---------- navigation stack (NATIVE §1, §4) ---------- */
  const app = $('#app'), listView = $('#listView'), chatView = $('#chatView');
  let navTimer = 0;
  function syncInert() {
    const r = app.dataset.route, both = wide.matches;
    listView.inert = !both && r !== 'list'; chatView.inert = !both && r !== 'chat';
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
    if (history.state?.route === 'chat') { popping = true; ignorePop++; history.back(); }   // route changes now; popstate is ignored
    else history.replaceState({ route: 'list' }, '', '#/');
    animateTo('list', 'pop');
  }
  let ignorePop = 0;
  window.addEventListener('popstate', e => {
    popping = false;
    if (ignorePop) { ignorePop--; return; }
    const st = e.state || { route: 'list' };
    if (st.route === 'chat' && st.id && st.id !== currentId && convs.some(c => c.id === st.id)) { saveDraft(); currentId = st.id; persist(); renderAll(); loadDraft(); }
    const r = st.route === 'chat' ? 'chat' : 'list';
    if (e.hasUAVisualTransition) return setRoute(r);   // Safari already animated its own back/forward (REVIEW M2)
    animateTo(r, r === 'chat' ? 'push' : 'pop');
  });
  wide.addEventListener?.('change', syncInert);
  $('#backBtn').onclick = back;
  $('#newChat').onclick = newConv; $('#newChat2').onclick = newConv; $('#newChat3').onclick = newConv;

  /* large title collapse (§2) */
  const scroller = $('#listScroller'), lt = $('#listView .large-title'), lnav = $('#listView .navbar');
  if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => lnav.classList.toggle('collapsed', !e.isIntersecting), { root: scroller, rootMargin: '-52px 0px 0px 0px' }).observe(lt);
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
  function swipeDelete(row, c) {
    const m = row.querySelector('.row-main'); m.style.transition = 'transform 260ms var(--ease-sheet)'; m.style.transform = 'translateX(-100%)';
    row.style.height = row.offsetHeight + 'px'; row.classList.add('removing');
    requestAnimationFrame(() => { row.style.height = '0px'; });
    setTimeout(() => { openRow = null; deleteConv(c); }, 300);
  }
  const ul = $('#convList');
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
    if (s.dx < -s.row.offsetWidth * .6) { const c = convOf(s.row); buzz(15); return swipeDelete(s.row, c); }
    if (s.dx < -60 || (s.v < -.4 && s.dx < -20)) { s.m.style.transform = `translateX(${-ACT_W}px)`; openRow = s.row; }
    else { s.m.style.transform = ''; s.row.classList.remove('swiped'); if (openRow === s.row) openRow = null; }
  });
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
    send: svg('<path d="M12 19V5M5 12l7-7 7 7"/>')
  };
  function showMenu(el, items, opts = {}) {
    ctxMenu.innerHTML = '';
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
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !ctx.hidden) hideMenu(); });

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
      { label: '수정 후 다시 보내기', icon: 'edit', act: () => { if (controller) controller.abort(); c.messages.splice(i); persist(); renderAll(); input.value = m.content; grow(); input.focus(); } },
      { label: '삭제', icon: 'trash', danger: true, act: () => { const n = c.messages[i + 1]?.role === 'assistant' ? 2 : 1; c.messages.splice(i, n); persist(); renderAll(); } }
    ]);
    const answer = splitThink(m.content).answer.trim(); const isLast = i === c.messages.length - 1;
    showMenu(el, [
      { label: '복사', icon: 'copy', act: () => copyText(null, answer) },
      ...(isLast && !controller ? [{ label: '다시 생성', icon: 'regen', act: regenerate }] : []),
      ...(navigator.share ? [{ label: '공유', icon: 'share', act: () => share(answer) }] : []),
      { label: '텍스트 선택', icon: 'select', act: () => { el.classList.add('selectable'); const off = ev => { if (!el.contains(ev.target)) { el.classList.remove('selectable'); document.removeEventListener('touchstart', off); document.removeEventListener('mousedown', off); } }; setTimeout(() => { document.addEventListener('touchstart', off, { passive: true }); document.addEventListener('mousedown', off); }, 0); } }
    ]);
  });
  longPress(ul, '.row', row => {
    const c = convOf(row); if (!c) return; closeSwipe();
    showMenu(row, [
      { label: '이름 변경', icon: 'edit', act: () => renameConv(c) },
      { label: c.pinned ? '고정 해제' : '고정', icon: 'pin', act: () => { c.pinned = !c.pinned; persist(); renderList(); } },
      { label: '삭제', icon: 'trash', danger: true, act: () => deleteConv(c) }
    ]);
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
    $('#sBase').value = settings.base; $('#sSystem').value = settings.system;
    $('#sShowThink').checked = settings.showThink; $('#sNoThink').checked = !!settings.noThink;
    setModelOptions([]); $('#sStatus').textContent = '';
    $('#a2hsRow').hidden = isStandalone();
    snap = formState();
    document.body.classList.add('sheet-open'); dlg.showModal(); sform.scrollTop = 0;
    renderWho(); loadModels();
  }
  $('#openSettings').onclick = openSettings;
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

  /* ---------- offline banner / toast ---------- */
  const setOffline = off => chatView.classList.toggle('offline', off);
  window.addEventListener('online', () => setOffline(false)); window.addEventListener('offline', () => setOffline(true));
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
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') saveState(); else swReg?.update().catch(() => {}); });
  window.addEventListener('pagehide', saveState);

  /* ---------- boot ---------- */
  const params = new URLSearchParams(location.search);
  const hm = location.hash.match(/^#\/c\/(.+)$/);
  let route = load(LS.route, 'chat');
  if (hm && convs.some(c => c.id === hm[1])) { currentId = hm[1]; route = 'chat'; } else if (location.hash === '#/') route = 'list';
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
  checkAuth().then(ok => { if (ok) maybeA2HS(); });

  /* ---------- service worker (HTTPS / localhost only; app works without it) ---------- */
  let swReg = null, reloading = false, wantReload = false;
  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.register('/ui/sw.js', { scope: '/ui/' }).then(reg => {
      swReg = reg;
      const offer = w => showToast('새 버전이 있어요', '새로고침', () => { wantReload = true; w.postMessage('SKIP_WAITING'); });
      if (reg.waiting && navigator.serviceWorker.controller) offer(reg.waiting);
      reg.addEventListener('updatefound', () => { const w = reg.installing; w && w.addEventListener('statechange', () => { if (w.state === 'installed' && navigator.serviceWorker.controller) offer(w); }); });
    }).catch(() => {});
    navigator.serviceWorker.addEventListener('controllerchange', () => { if (wantReload && !reloading) { reloading = true; location.reload(); } });
  }
  window.__app = { showToast, go, isStandalone };
})();
