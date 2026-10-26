/* Eve 선톡 P1 UI (eve-chat-ui-design PROACTIVE-MEMORY-SPEC v2 @6221745 + eve-serving PR #12 contract, Part A + §C):
 * in-thread proactive messages, unread dot/pill + title/app badge, read-on-view via outbox,
 * the shared .confirm-card, and Settings › 선톡. Server calls go through proactive-api.js only.
 * Security: a confirm token is fetched only when approve is pressed (POST reissue → approve, contract §3.5.4), held in a local variable, never stored/logged; SSE tokens are ignored;
 * push payloads are never rendered (sw.js shows fixed text). */
(function () {
  const ULID = /^[0-9A-HJKMNP-TV-Z]{26}$/;
  const PUSH_HOSTS = ['web.push.apple.com'];          // exact host, mirrors the server allowlist (PM §2.2.1)
  const POLL_MS = 60000, LS_PUSH = 'eve.push', LS_KID = 'eve.push.kid';
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const svg = d => `<svg viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
  const IC = {
    sparkle: svg('<path d="M12 3l1.9 5.6 5.6 1.9-5.6 1.9L12 18l-1.9-5.6-5.6-1.9 5.6-1.9Z"/>'),
    eye: svg('<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'),
    uturn: svg('<path d="M9 14 4 9l5-5M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>'),
    sun: svg('<path d="M3 18h18M6 18a6 6 0 0 1 12 0M12 6v2M5.6 9.6l1.4 1.4M18.4 9.6 17 11"/>'),
    bell: svg('<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20a2 2 0 0 0 4 0"/>'),
    wrench: svg('<path d="M14.7 6.3a4 4 0 0 0 5 5L13 18l-3 3-4-4 3-3 6.7-6.7a4 4 0 0 0-1-1z"/>'),
    brain: svg('<path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 6 1V5a2 2 0 0 0-3-1zM15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-6 1"/>'),
    trash: svg('<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>'),
    warn: svg('<path d="M12 3 2 20h20zM12 10v4M12 17v.01"/>'),
    check: svg('<path d="M5 12l5 5 9-10"/>'),
    err: svg('<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16v.01"/>')
  };
  const T = new Intl.DateTimeFormat('ko-KR', { hour: 'numeric', minute: '2-digit' });
  const DAYS = ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일'];
  function when(ms) {                                  // spec A2: 오늘 / 어제 / 이번 주 요일 / M월 D일
    const d = new Date(ms), now = new Date(), t = T.format(d);
    const day0 = x => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const diff = Math.round((day0(now) - day0(d)) / 864e5);
    if (diff === 0) return t; if (diff === 1) return '어제 ' + t;
    if (diff > 1 && diff < 7) return DAYS[d.getDay()] + ' ' + t;
    return `${d.getMonth() + 1}월 ${d.getDate()}일 ${t}`;
  }
  const hm = s => { const m = /^(\d{2}):(\d{2})$/.exec(s || ''); if (!m) return s || ''; const d = new Date(2000, 0, 1, +m[1], +m[2]); return T.format(d); };
  let live = null;                                     // hidden role=status region (spec C5/A7)
  function say(text) { if (!live) { live = el('div', 'sr-only'); live.setAttribute('role', 'status'); live.id = 'proLive'; document.body.appendChild(live); } live.textContent = ''; setTimeout(() => { live.textContent = text; }, 30); }

  /* ================= §C shared .confirm-card (spec v2 C1–C4) ================= */
  const F = () => self.EveProactiveAPI.FIELDS;         // all server field names live in proactive-api.js
  const cards = new Map();                             // action_id -> card element
  let SYS = { proactive: true, tools: true, memoryRO: false };   // GET /v1/settings system.* (read-only)
  const sanitize = a => { const o = Object.assign({}, a); delete o.confirm_token; delete o.token_expires_at; return o; };
  function variantOf(x) {                              // spec C4
    if (x.tool === 'memory.propose') return x.op === 'delete' ? 'forget' : 'remember';
    if (x.tool === 'proactive.propose_followup') return 'proactive';
    return 'tool';
  }
  // danger (spec §F-1): only send verbs and delete ops are red; write stays accent
  const dangerOf = (x, variant) => variant === 'forget' || x.op === 'delete' || x.verbs.includes('send') || x.verbs.includes('delete');
  const DENIED = { secret_detected: '비밀번호나 키처럼 보여서 진행하지 않았어요', cap_exceeded: '허용된 한도를 넘어서 진행하지 않았어요', tainted: '외부 내용이 섞인 요청이라 진행하지 않았어요',
    scope_denied: '이 작업은 할 수 있는 권한이 없어요', item_gone: '이미 바뀌거나 지워진 항목이 있어서 진행하지 않았어요',
    conflict: '이미 처리된 요청이라 진행하지 않았어요', payload_mismatch: '내용이 바뀌어서 진행하지 않았어요', expired: '시간이 지나 진행하지 않았어요', not_found: '대상을 찾을 수 없어요', kill_switch: '지금은 이 기능을 쓸 수 없어요', invalid: '요청 내용이 올바르지 않아 진행하지 않았어요' };
  const CROSS = '서버 주소가 이 앱과 다른 곳으로 설정되어 있어 여기서는 승인할 수 없어요. 설정에서 서버 주소를 비우면 승인할 수 있어요';
  const RTF = new Intl.DateTimeFormat('ko-KR', { month: 'long', day: 'numeric' }), YTF = new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' });
  function shortDate(iso) {                            // spec B2: 오늘 / N일 전 / 10월 21일 / 2025년 3월 2일
    const d = new Date(iso); if (isNaN(d)) return '';
    const now = new Date(), day0 = x => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime(), diff = Math.round((day0(now) - day0(d)) / 864e5);
    if (diff <= 0) return '오늘'; if (diff < 7) return diff + '일 전';
    return (d.getFullYear() === now.getFullYear() ? RTF : YTF).format(d);
  }
  const VAR = {
    remember: { ic: 'brain', title: () => '메모리에 저장할까요?', primary: () => '저장', secondary: '취소', done: () => '저장했어요' },
    forget: { ic: 'trash', title: x => x.ambiguous ? '어떤 걸 지울까요?' : '메모리에서 지울까요?', primary: (x, n) => `${n}개 지우기`, secondary: '취소', done: (x, n) => `${n}개 지웠어요` },
    proactive: { ic: 'bell', title: () => '다시 알려 드릴까요?', primary: () => '예약', secondary: '괜찮아요', done: x => x.display ? `${x.display}에 알려 드릴게요` : '알림을 예약했어요' },
    tool: { ic: 'wrench', title: x => x.summary || x.tool || '작업을 실행할까요?', primary: x => x.verbs.includes('delete') ? '삭제' : x.verbs.includes('send') ? '보내기' : /create|add/.test(x.tool) ? '추가' : '실행', secondary: '취소', done: () => '실행했어요' }
  };
  const EXPIRED = '시간이 지나 취소됐어요';
  const deniedText = c => DENIED[c] || (c ? DENIED.invalid : '진행하지 않았어요');   // SSE denied without code → generic; unknown API code → invalid
  let seq = 0;
  function renderConfirmCard(action, opts) {
    const P = opts.P, a = sanitize(action), x = F().action(action), id = x.id;
    const variant = variantOf(x), V = VAR[variant], danger = dangerOf(x, variant), n = ++seq;
    const retries = opts.retries || 0;               // "다시 요청" count, carried across in-place replacement
    const card = el('div', 'confirm-card'); card.dataset.variant = variant; card.dataset.aid = id || '';
    card.setAttribute('role', 'group'); card.setAttribute('aria-labelledby', 'cct' + n);
    if (id) cards.set(id, card);
    const head = el('div', 'cc-head'); head.insertAdjacentHTML('beforeend', IC[V.ic]);
    const title = el('span', 'cc-title', V.title(x)); title.id = 'cct' + n; head.appendChild(title); card.appendChild(head);
    const result = el('p', 'cc-result'); result.tabIndex = -1; result.hidden = true;
    if (x.status === 'denied') {                       // spec C3 denied: one line, no body, no buttons
      card.dataset.state = 'denied'; head.remove(); result.hidden = false;
      result.insertAdjacentHTML('beforeend', IC.err); result.appendChild(el('span', null, deniedText(x.errorCode)));
      card.appendChild(result); card.removeAttribute('aria-labelledby'); card.setAttribute('aria-label', result.textContent); say(result.textContent);
      return card;
    }
    const desc = [];
    if (x.tainted) { const t = el('p', 'cc-taint'); t.id = 'ccw' + n; t.insertAdjacentHTML('beforeend', IC.warn); t.appendChild(el('span', null, '외부 콘텐츠를 읽은 뒤 제안된 작업이에요')); card.appendChild(t); desc.push(t.id); }
    if (x.actor === 'scheduler') card.appendChild(el('p', 'cc-prov', (x.jobName ? x.jobName + '에서' : 'Eve 예약 작업에서') + ' · 예약 작업'));
    const body = el('div', 'cc-body'); body.id = 'ccb' + n; desc.push(body.id);
    const boxes = [];
    if (variant === 'remember') { const it = x.items[0] || {}; body.appendChild(el('p', 'cc-quote', '“' + (it.text || x.summary) + '”')); if (it.kind) body.appendChild(el('p', 'cc-kind', it.kind)); }
    else if (variant === 'forget') {                   // meta = kind · updated_at (spec f01cd23 §F-3)
      const ul = el('ul', 'cc-items');
      x.items.forEach(it => {
        const li = el('li'), lab = el('label', 'cc-item'), cb = el('input'); cb.type = 'checkbox'; cb.checked = !x.ambiguous; cb.dataset.iid = it.id || '';
        const tx = el('span', 'cc-item-text'); tx.appendChild(el('span', null, it.text));
        const meta = el('span', 'cc-kind'); if (it.kind) meta.append(it.kind);
        if (it.updatedAt && shortDate(it.updatedAt)) { if (it.kind) meta.append(' · '); const tm = el('time', null, shortDate(it.updatedAt)); tm.dateTime = it.updatedAt; meta.appendChild(tm); }
        if (meta.textContent) tx.appendChild(meta);
        lab.append(cb, tx); li.appendChild(lab); ul.appendChild(li); boxes.push(cb);
        cb.addEventListener('change', () => paintPrimary());
      });
      body.appendChild(ul);
    }
    else if (variant === 'proactive') {
      body.appendChild(el('p', 'cc-summary', x.summary));
      if (x.display) { const w = el('time', 'cc-when', x.display); if (x.whenAt) w.dateTime = x.whenAt; body.appendChild(w); }   // display as given (Asia/Seoul, CT Q12)
      body.appendChild(el('p', 'cc-where', '이 대화에서'));
    }
    else {
      const v = x.view, dl = el('dl', 'cc-view'), ks = Object.keys(v);
      ks.forEach((k, i) => { const val = v[k]; const dt = el('dt', null, k), dd = el('dd', null, typeof val === 'string' ? val : JSON.stringify(val)); if (i >= 6) dt.hidden = dd.hidden = true; dl.append(dt, dd); });
      if (ks.length) body.appendChild(dl);
      if (ks.length > 6) { const more = el('button', 'cc-more', '모두 보기'); more.type = 'button'; more.onclick = () => { dl.querySelectorAll('[hidden]').forEach(e => { e.hidden = false; }); more.remove(); }; body.appendChild(more); }
    }
    card.appendChild(body); card.setAttribute('aria-describedby', desc.join(' '));
    const acts = el('div', 'cc-actions');
    const no = el('button', 'cc-secondary', V.secondary), yes = el('button', 'cc-primary' + (danger ? ' cc-danger' : ''), '');
    no.type = yes.type = 'button'; if (x.tainted) yes.setAttribute('aria-describedby', 'ccw' + n);
    acts.append(no, yes); card.appendChild(acts);
    const again = el('button', 'cc-again', '다시 요청'); again.type = 'button'; again.hidden = true;
    const resRow = el('div', 'cc-result-row'); resRow.append(result, again); card.appendChild(resRow);
    const meta = el('p', 'cc-meta'); card.appendChild(meta);
    const checked = () => boxes.filter(b => b.checked);
    const cross = () => !P.sameOrigin();          // custom base on another origin: no token / approve calls (no CORS)
    const blocked = () => cross() || (variant === 'tool' && !SYS.tools) || ((variant === 'remember' || variant === 'forget') && SYS.memoryRO);
    function paintPrimary() { yes.textContent = V.primary(x, checked().length); if (state === 'pending') yes.disabled = !P.online() || blocked() || (variant === 'forget' && !checked().length); }
    let timer = 0, state = '', retryFn = null, gone = !!opts.gone;   // gone: revise returned 410 (past 24h)
    const expired = () => x.expiresAt && x.expiresAt <= Date.now();
    function setState(s, msg, opt = {}) {
      state = s; card.dataset.state = s;
      const settled = ['confirmed', 'declined', 'expired', 'error', 'denied'].includes(s), busy = s === 'preparing' || s === 'revising' || s === 'checking';
      const hadFocus = card.contains(document.activeElement) && document.activeElement.tagName === 'BUTTON';
      yes.disabled = no.disabled = s !== 'pending' || !P.online();
      boxes.forEach(b => { b.disabled = s !== 'pending'; });
      card.setAttribute('aria-busy', String(s === 'submitting' || busy));
      yes.classList.toggle('loading', busy || (s === 'submitting' && opt.which !== 'no')); no.classList.toggle('loading', s === 'submitting' && opt.which === 'no');
      if (busy) yes.textContent = s === 'checking' ? '확인 중…' : '준비 중…'; else paintPrimary();
      if (s === 'pending') no.disabled = !P.online() || cross();
      acts.hidden = settled && !(s === 'error' && opt.retry);
      if (s === 'error' && opt.retry) { no.hidden = true; yes.textContent = '다시 시도'; yes.disabled = false; yes.classList.remove('cc-danger'); } else { no.hidden = false; yes.classList.toggle('cc-danger', danger); }
      result.hidden = !settled; result.textContent = '';
      again.hidden = !(s === 'expired' && !gone && P.online());
      if (settled) {
        result.insertAdjacentHTML('beforeend', s === 'error' || s === 'denied' ? IC.err : s === 'confirmed' ? IC.check : '');
        if (s === 'denied') { [head, body, card.querySelector('.cc-taint'), card.querySelector('.cc-prov')].forEach(e => e && (e.hidden = true)); }
        result.appendChild(el('span', null, msg || ''));
        if (s !== 'expired') clearInterval(timer); meta.textContent = '';
        if (msg) say(msg);
        if (hadFocus) result.focus();
      }
      if (s === 'pending' && cross()) meta.textContent = CROSS;
      else if (!settled && !P.online()) meta.textContent = '연결되면 확인할 수 있어요';
      else if (s === 'pending' && blocked()) meta.textContent = variant === 'tool' ? '지금은 실행할 수 없어요' : '지금은 메모리를 바꿀 수 없어요';
      if (opts.onSettled && settled) opts.onSettled(id, s);
    }
    function tick() {                                  // proposal expiry only (expires_at); no token countdown/auto-reissue (contract §3.5.4)
      if (state !== 'pending') return;
      if (expired()) { setState('expired', EXPIRED); return; }
      if (!P.online()) { meta.textContent = '연결되면 확인할 수 있어요'; return; }
      if (cross()) meta.textContent = CROSS;
    }
    function settleErr(e, retry) {
      if (!e.http) return setState('error', '연결이 끊겼어요', { retry });   // network only: retryable
      if (e.code === 'expired') return setState('expired', EXPIRED);          // branch on body.error_code, never on HTTP status
      return setState('denied', deniedText(e.code || 'invalid'));
    }
    async function revise(itemIds, nextRetries) {     // partial forget / 다시 요청 → new proposal replaces this card in place
      setState('revising');
      try {
        const next = await P.api.revise(id, itemIds);
        if (!next || !next.action_id) throw Object.assign(new Error('bad'), { http: 400 });
        cards.delete(id); clearInterval(timer);   // any token in the revise response is ignored: approve fetches its own
        return card._replace(next, nextRetries);
      } catch (e) {
        if (!e.http) { retryFn = () => revise(itemIds, nextRetries); return setState('error', '연결이 끊겼어요', { retry: retryFn }); }
        if (e.code === 'expired') { gone = true; return setState('expired', EXPIRED); }   // 24h from the root proposal: hide 다시 요청
        setState('denied', deniedText(e.code || 'invalid'));
      }
    }
    again.onclick = () => {
      const ids = x.items.map(i => i.id).filter(Boolean);   // same item_ids; proposals without item ids → empty body
      revise(ids.length ? ids : undefined, retries + 1); return;
    };
    yes.onclick = async () => {
      if (state === 'error') { const f = retryFn; retryFn = null; return f ? f() : null; }
      if (state !== 'pending' || !P.online() || blocked()) return;
      if (expired()) return setState('expired', EXPIRED);
      if (variant === 'forget' && checked().length < boxes.length) {   // some unchecked → revise to the subset first
        if (!checked().length) return;
        return revise(checked().map(b => b.dataset.iid).filter(Boolean), retries);
      }
      if (cross()) return;
      // §3.5.4: token only on press — POST reissue, then approve at once. Token lives in this local only; never stored or logged.
      setState('submitting', '', { which: 'yes' });
      let tok;
      try { const r = await P.api.reissue(id); tok = r && r.confirm_token; }
      catch (e) { retryFn = () => { setState('pending'); yes.onclick(); }; return settleErr(e, retryFn); }   // approve not sent yet: retry is safe
      if (!tok) return setState('error', '실행하지 못했어요');
      try {
        const r = await P.api.approve(id, tok, x.hash); tok = null;
        if (r && r.status === 'failed') setState('error', '실행하지 못했어요'); else setState('confirmed', V.done(x, checked().length || x.items.length));
      } catch (e) {
        tok = null;
        if (!e.http) return recheck();                 // may have executed server-side: never blind-retry approve (security review Low 4)
        retryFn = () => { setState('pending'); }; settleErr(e, retryFn);
      }
    };
    async function recheck() {                         // GET /v1/actions/{id} (fallback: pending list) to learn the real outcome
      setState('checking'); meta.textContent = '결과를 확인하는 중이에요'; say('결과를 확인하는 중이에요');
      for (let i = 0; i < 6; i++) {
        if (i) await new Promise(r => setTimeout(r, Math.min(8000, 1000 * 2 ** i)));
        if (!P.online()) continue;
        let st = null;
        try { const r = await P.api.getAction(id); st = r && r.status; }
        catch (e) {
          if (!e.http) continue;
          try { const l = await P.api.pendingActions(); st = (l && l.data || []).some(z => z.action_id === id) ? 'pending' : 'unknown'; } catch (e2) { if (!e2.http) continue; st = 'unknown'; }
        }
        meta.textContent = '';
        if (st === 'executed' || st === 'executing') return setState('confirmed', V.done(x, checked().length || x.items.length));
        if (st === 'pending') return setState('pending');   // not executed: user may press again (fresh reissue → approve)
        if (st === 'rejected') return setState('declined', '취소했어요');
        if (st === 'expired') return setState('expired', EXPIRED);
        if (st === 'failed') return setState('error', '실행하지 못했어요');
        return setState('error', '결과를 확인하지 못했어요. 대화를 새로고침해 확인해 주세요');
      }
      meta.textContent = ''; setState('error', '결과를 확인하지 못했어요. 연결되면 다시 확인할게요', { retry: recheck });
    }
    no.onclick = async () => {
      if (state !== 'pending') return;
      setState('submitting', '', { which: 'no' });
      try { await P.api.reject(id); setState('declined', '취소했어요'); }
      catch (e) { if (!e.http) { retryFn = () => { setState('pending'); }; setState('error', '연결이 끊겼어요', { retry: retryFn }); } else settleErr(e); }
    };
    const st = x.status;
    if (st === 'executed') setState('confirmed', V.done(x, x.items.length));
    else if (st === 'rejected') setState('declined', '취소했어요');
    else if (st === 'expired' || expired()) setState('expired', EXPIRED);
    else if (st === 'failed') setState('error', '실행하지 못했어요');
    else if (st && st !== 'pending') setState('declined', '이미 처리된 요청이에요');
    else setState('pending');                          // no token fetched on render/viewport (§3.5.4)
    timer = setInterval(tick, 1000); tick();
    card._setState = setState;
    card._replace = (next, r) => { const c2 = renderConfirmCard(next, Object.assign({}, opts, { retries: r == null ? retries : r })); card.replaceWith(c2); return c2; };
    if (!st || st === 'pending') say('확인이 필요해요: ' + V.title(x));
    return card;
  }
  function setCardState(id, s, msg) { const c = cards.get(id); if (c && c._setState) c._setState(s, msg); }
  function actionResult(j) {
    const map = { executed: ['confirmed', '실행했어요'], rejected: ['declined', '취소했어요'], expired: ['expired', EXPIRED], failed: ['error', '실행하지 못했어요'] };
    const c = cards.get(j.action_id); if (!c || !c._setState || ['confirmed', 'declined', 'expired', 'error', 'denied'].includes(c.dataset.state)) return;
    const m = map[j.status] || map.failed; c._setState(m[0], m[1]);
  }

  /* ================= Part A: proactive messages ================= */
  function init(h) {
    const api = self.EveProactiveAPI.make(h.api, h.sameOrigin || (() => true));
    const P = { api, online: h.online, sameOrigin: h.sameOrigin || (() => true) };
    let sysLoaded = false, notif = new Map(), supported = true, pollT = null, pendingNid = null, total = 0, lastTotal = 0;
    const qs = new URLSearchParams(location.search);
    if (ULID.test(qs.get('nid') || '')) { pendingNid = qs.get('nid'); qs.delete('nid'); history.replaceState(history.state, '', location.pathname + (qs.toString() ? '?' + qs : '') + location.hash); }
    const unreadOf = c => c.unread || 0;
    function badge() {
      const convs = h.convs ? h.convs() : []; let n = 0; const seen = new Set();
      convs.forEach(c => { n += unreadOf(c); seen.add(c.id); }); notif.forEach((k, tid) => { if (!seen.has(tid)) n += k; });
      total = n; document.title = n ? `(${n}) Eve` : 'Eve';
      try { if (navigator.setAppBadge) { (n ? navigator.setAppBadge(n) : navigator.clearAppBadge()).catch(() => {}); } } catch {}
      const cur = h.cur(), b = document.getElementById('backBadge');
      if (b) { const k = n - (cur ? unreadOf(cur) : 0); b.hidden = k <= 0; b.textContent = k > 99 ? '99+' : String(k); }
    }
    async function refresh() {
      if (!supported || !h.isServer() || !h.online()) return badge();
      if (!sysLoaded) { sysLoaded = true; api.getSettings().then(j => { SYS = F().system(j); }).catch(() => { sysLoaded = false; }); }
      try {
        const j = await api.unreadThreads(); const m = new Map();   // GET /v1/threads?unread=true → server unread_count per thread
        (j && j.data || []).forEach(t => { const n = F().unread(t); if (t && t.id && n > 0) m.set(t.id, n); });
        (h.convs ? h.convs() : []).forEach(c => { c.unread = m.get(c.id) || 0; });   // other-device reads vanish
        notif = m; h.renderList(); badge();
        if (pendingNid && (!h.ready || h.ready())) { const mid = pendingNid; pendingNid = null; await openByMessage(mid, m); }
        const c = h.cur(); if (c && total > lastTotal && h.route() === 'chat' && m.has(c.id) && h.reload) { h.reload(c); say('Eve가 새 메시지를 보냈어요'); }
        lastTotal = total;
      } catch (e) {
        if (api.unsupported(e)) { supported = false; clearInterval(pollT); badge(); return; }
        if (pendingNid && !e.http) connectScreen();
      }
    }
    async function openByMessage(mid, unreadMap) {   // push nid = message_id → its thread, scrolled to it
      const cur = h.cur(); if (cur && (cur.messages || []).some(x => x.id === mid)) return h.openHit(cur.id, mid);
      const tids = [...unreadMap.keys(), ...(h.convs ? h.convs() : []).map(c => c.id).filter(id => !unreadMap.has(id)).slice(0, 5)];
      for (const tid of tids) {
        const c = (h.convs ? h.convs() : []).find(x => x.id === tid);
        if (c && (c.messages || []).some(x => x.id === mid)) return h.openHit(tid, mid);
        try { const r = await api.threadMessages(tid); if ((r && r.data || []).some(x => x.id === mid)) return h.openHit(tid, mid); } catch {}
      }
    }
    function connectScreen() {                         // spec A6 / PM §2.3: no hostnames, nid kept locally
      if (document.getElementById('proConnect')) return;
      const d = el('div', 'pro-connect'); d.id = 'proConnect'; d.setAttribute('role', 'alertdialog'); d.setAttribute('aria-label', '서버에 연결할 수 없어요');
      d.append(el('h2', null, '서버에 연결할 수 없어요'), el('p', null, '네트워크 연결을 확인한 뒤 다시 시도해 주세요'));
      const btn = el('button', 'primary', '다시 시도'); btn.type = 'button'; btn.onclick = () => { d.remove(); refresh(); }; d.appendChild(btn);
      document.body.appendChild(d);
    }
    function decorateRow(li, c) {
      const n = unreadOf(c); if (!n) return;
      li.classList.add('unread');
      li.querySelector('.row-main')?.insertAdjacentHTML('afterbegin', '<span class="unread-dot" aria-hidden="true"></span>');
      if (n >= 2) { const b = el('span', 'unread-pill', n > 99 ? '99+' : String(n)); b.setAttribute('aria-hidden', 'true'); const top = li.querySelector('.row-top'); top && top.appendChild(b); }
      li.setAttribute('aria-label', `${c.title}, 읽지 않은 메시지 ${n}개`);
    }
    let prevJob = null, sepDone = new Set();
    function decorateMsg(wrap, m, i, msgs) {
      if (!wrap || !m) return;
      if (m.origin === 'proactive') {
        const prev = msgs && msgs[i - 1], cont = prev && prev.origin === 'proactive' && prev.jobId === m.jobId && prev.kind === m.kind;
        const label = m.kind === 'digest' ? '조용한 시간 동안 · 요약' : m.jobName ? 'Eve가 먼저 보냄 · ' + m.jobName : 'Eve가 먼저 보냄', t = when(m.created || Date.now());
        wrap.classList.add('proactive'); wrap.dataset.origin = 'proactive'; if (m.jobId) wrap.dataset.job = m.jobId;
        wrap.setAttribute('role', 'article');
        wrap.setAttribute('aria-label', (m.readAt ? '' : '읽지 않음, ') + 'Eve가 먼저 보낸 메시지, ' + (m.kind === 'digest' ? '조용한 시간 동안 요약, ' : m.jobName ? m.jobName + ', ' : '') + t);
        if (!m.readAt) wrap.dataset.unread = '';
        if (prev && (m.created || 0) - (prev.created || 0) >= 30 * 60000 || prev && new Date(m.created).toDateString() !== new Date(prev.created).toDateString()) {
          const sep = el('div', 'day-sep', (new Date(m.created).toDateString() === new Date().toDateString() ? '오늘 ' : '') + when(m.created)); wrap.before(sep);
        }
        const line = el('div', 'origin-line');
        if (!cont) { line.insertAdjacentHTML('beforeend', IC[{ briefing: 'sun', watch: 'eye', followup: 'uturn' }[m.templateKind] || 'sparkle'].replace('<svg', '<svg class="origin-ic"')); line.appendChild(el('span', 'origin-label', label)); }
        const tm = el('time', null, t); tm.dateTime = new Date(m.created || Date.now()).toISOString(); line.appendChild(tm);
        wrap.insertBefore(line, wrap.firstChild);
      }
      (m.pendingActions || []).forEach(a => mountCard(a, wrap));
    }
    function mountCard(a, after) {
      if (cards.has(a.action_id) && document.body.contains(cards.get(a.action_id))) return;
      const host = after.nextElementSibling && after.nextElementSibling.classList.contains('cc-stack') ? after.nextElementSibling : (() => { const s = el('div', 'cc-stack'); after.after(s); return s; })();
      host.appendChild(renderConfirmCard(a, { P, onSettled: (id, s) => { a.status = { confirmed: 'executed', declined: 'rejected', expired: 'expired', error: 'failed' }[s]; } }));
    }
    /* read rule (A3.3): ≥50% visible for 1s while the page is visible → local now, POST via outbox */
    const timers = new Map();
    const io = 'IntersectionObserver' in self ? new IntersectionObserver(es => es.forEach(e => {
      const w = e.target, id = w.dataset.mid;
      if (e.isIntersecting && (e.intersectionRatio >= 0.5 || e.intersectionRect.height >= 0.5 * (e.rootBounds ? e.rootBounds.height : innerHeight))) { if (!timers.has(id)) timers.set(id, setTimeout(() => { timers.delete(id); if (document.visibilityState === 'visible' && h.route() === 'chat') markRead(w); }, 1000)); }
      else { clearTimeout(timers.get(id)); timers.delete(id); }
    }), { threshold: [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1] }) : null;
    function markRead(w) {
      const id = w.dataset.mid, c = h.cur(); if (!id || !c) return;
      io && io.unobserve(w);
      const m = (c.messages || []).find(x => x.id === id); if (!m || m.readAt) return;
      m.readAt = Date.now(); delete w.dataset.unread; w.setAttribute('aria-label', w.getAttribute('aria-label').replace(/^읽지 않음, /, ''));
      if (c.unread) c.unread--; if (notif.has(c.id)) { const k = notif.get(c.id) - 1; if (k > 0) notif.set(c.id, k); else notif.delete(c.id); }
      batch.push(id); clearTimeout(batchT); batchT = setTimeout(() => flushReads(c), 50); badge();
    }
    let batch = [], batchT = 0;
    function flushReads(c) {                           // several at once and nothing left unread → one POST /v1/threads/{id}/read (CT Q6)
      const ids = batch; batch = [];
      const left = (c.messages || []).some(m => m.origin === 'proactive' && !m.readAt);
      if (ids.length > 1 && !left && c.srv !== false) h.enqueue('readThread', 'readThread:' + c.id, { id: c.id });
      else ids.forEach(id => h.enqueue('read', 'read:' + id, { id }));
    }
    let restored = new Set();
    async function afterRender(c) {
      if (!c) return;
      const unread = [...document.querySelectorAll('.msg.proactive[data-unread]')];
      if (unread.length && !sepDone.has(c.id)) {      // first open: '새 메시지' divider + scroll to it
        sepDone.add(c.id);
        const sep = el('div', 'unread-sep', '새 메시지'); sep.setAttribute('role', 'separator'); unread[0].before(sep.previousElementSibling?.classList?.contains('day-sep') ? sep : sep);
        requestAnimationFrame(() => requestAnimationFrame(() => { h.unstick && h.unstick(); sep.scrollIntoView({ block: 'start' }); setTimeout(() => sep.classList.add('fade'), 1500); }));   // after app's own scroll-to-bottom frame
      }
      if (io) unread.forEach(w => io.observe(w));
      if (h.isServer() && c.srv && !restored.has(c.id) && h.online()) {   // restore pending cards after reload (no tokens)
        restored.add(c.id);
        try {
          const j = await api.pendingActions();
          (j && j.data || []).filter(a => a.thread_id === c.id).forEach(a => {
            if (cards.has(a.action_id) && document.body.contains(cards.get(a.action_id))) return;
            const anchor = (a.message_id && document.querySelector(`.msg[data-mid="${CSS.escape(a.message_id)}"]`)) || [...document.querySelectorAll('#messages > .msg, .msg')].pop();
            if (anchor) mountCard(sanitize(a), anchor);
          });
        } catch (e) { restored.delete(c.id); }
      }
      badge();
    }
    // SSE never carries a token (eve-serving PR #16): any confirm_token there is dropped; the token comes only from the session POST reissue
    function streamCard(j, after) { const a = sanitize(j); mountCard(a, after); return a; }

    /* ================= Settings › 선톡 (spec A5 + architect keys) ================= */
    const $ = s => document.getElementById(s);
    const sw = $('sProactive'), more = $('proMore'), qS = $('qStart'), qE = $('qEnd'), qSV = $('qStartVal'), qEV = $('qEndVal'), qErr = $('qErr'),
      memRow = $('proMemRow'), msw = $('sProMem'), note = $('sProNote'), pushRow = $('pushRow'), psw = $('sPush'), pnote = $('sPushNote');
    let srv = null;                                    // last server copy of settings
    const showQ = () => { qSV.textContent = hm(qS.value); qEV.textContent = hm(qE.value); const bad = qS.value && qS.value === qE.value; qErr.hidden = !bad; };
    function paint() {
      const p = srv?.proactive || {};
      sw.checked = !!p.enabled; more.hidden = !p.enabled;
      const q = p.quiet_hours || {}; qS.value = q.start || '22:00'; qE.value = q.end || '08:00'; showQ();
      memRow.hidden = !(srv?.memory?.enabled); msw.checked = !!p.memory_read;
      pushRow.hidden = !(p.enabled && h.isStandalone()); psw.checked = localStorage.getItem(LS_PUSH) === '1';
    }
    async function openSettings() {
      $('qStartWrap').hidden = $('qEndWrap').hidden = true;
      if (!h.isServer()) { sw.disabled = true; more.hidden = true; note.textContent = '서버에 연결되면 설정할 수 있어요.'; return; }
      sw.disabled = true; note.textContent = 'Eve가 브리핑이나 알림을 먼저 보낼 수 있어요. 하루 최대 3번.';
      try {
        srv = await api.getSettings() || {}; SYS = F().system(srv); delete srv.system;   // system.* is read-only: never PATCHed
        sw.disabled = !SYS.proactive; paint();
        if (!SYS.proactive) { more.hidden = true; note.textContent = '지금은 이 기능을 쓸 수 없어요'; }
        msw.disabled = SYS.memoryRO;
      }
      catch (e) { srv = null; sw.checked = false; more.hidden = true; note.textContent = api.unsupported(e) ? '지금은 이 기능을 쓸 수 없어요' : '설정을 불러오지 못했어요.'; }
    }
    async function patch(changed, rollback) {
      try { await api.patchSettings(changed); return true; }
      catch (e) { rollback(); h.showToast('설정을 저장하지 못했어요', '다시 시도', () => patch(changed, rollback), 4000); return false; }
    }
    sw.addEventListener('change', () => {               // immediate, optimistic, rollback on failure
      const on = sw.checked; srv.proactive = Object.assign({}, srv.proactive, { enabled: on }); paint();
      patch({ proactive: { enabled: on } }, () => { srv.proactive.enabled = !on; paint(); });
      if (!on && localStorage.getItem(LS_PUSH) === '1') setPush(false).catch(() => {});
    });
    msw.addEventListener('change', () => {
      const on = msw.checked; srv.proactive = Object.assign({}, srv.proactive, { memory_read: on });
      patch({ proactive: { memory_read: on } }, () => { srv.proactive.memory_read = !on; paint(); });
    });
    [['qStartRow', 'qStartWrap', qS], ['qEndRow', 'qEndWrap', qE]].forEach(([r, w, inp]) => {
      $(r).onclick = () => { const wr = $(w); wr.hidden = !wr.hidden; if (!wr.hidden) inp.focus(); };
      inp.addEventListener('input', showQ); inp.addEventListener('change', showQ);
    });
    function saveSettings() {                           // '완료': only changed keys
      if (!srv || !srv.proactive?.enabled) return;
      const q = srv.proactive.quiet_hours || {}, next = { start: qS.value, end: qE.value };
      if (!/^\d{2}:\d{2}$/.test(next.start) || !/^\d{2}:\d{2}$/.test(next.end) || next.start === next.end) return;
      if (next.start === (q.start || '22:00') && next.end === (q.end || '08:00')) return;
      const old = srv.proactive.quiet_hours; srv.proactive.quiet_hours = next;
      patch({ proactive: { quiet_hours: next } }, () => { srv.proactive.quiet_hours = old; });
    }
    const b64u = s => { const b = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4)); return Uint8Array.from(b, ch => ch.charCodeAt(0)); };
    function allowedEndpoint(u) { try { const x = new URL(u); return x.protocol === 'https:' && (x.port === '' || x.port === '443') && !x.username && !x.password && PUSH_HOSTS.includes(x.hostname); } catch { return false; } }
    async function setPush(on) {
      const reg = await navigator.serviceWorker.ready; const cur = await reg.pushManager.getSubscription();
      if (!on) { if (cur) { try { await api.unsubscribe(cur.endpoint); } catch {} try { await cur.unsubscribe(); } catch {} } localStorage.removeItem(LS_PUSH); localStorage.removeItem(LS_KID); psw.checked = false; return; }
      const k = await api.vapidKey();
      let cur2 = cur;
      if (cur2 && localStorage.getItem(LS_KID) && localStorage.getItem(LS_KID) !== k.key_id) {   // key rotated → resubscribe
        try { await api.unsubscribe(cur2.endpoint); } catch {} try { await cur2.unsubscribe(); } catch {} cur2 = null;
      }
      const sub = cur2 || await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64u(k.key) });
      if (!allowedEndpoint(sub.endpoint)) { try { await sub.unsubscribe(); } catch {} throw Object.assign(new Error('host'), { pushHost: true }); }
      await api.subscribe(sub.toJSON(), k.key_id);
      localStorage.setItem(LS_PUSH, '1'); localStorage.setItem(LS_KID, k.key_id);
    }
    psw.addEventListener('change', async () => {
      const want = psw.checked;
      if (want) {
        if (!('serviceWorker' in navigator && 'PushManager' in self && 'Notification' in self)) { psw.checked = false; pnote.textContent = '이 기기는 알림을 지원하지 않아요.'; return; }
        const perm = await Notification.requestPermission();   // first await: stays inside the tap gesture (iOS)
        if (perm !== 'granted') { psw.checked = false; pnote.textContent = '알림 권한이 꺼져 있어요. iPhone 설정 › 알림에서 Eve를 허용해 주세요.'; return; }
      }
      psw.disabled = true;
      try { await setPush(want); pnote.textContent = want ? '알림에는 내용 없이 “Eve에게서 새 메시지가 있어요”만 표시돼요.' : '알림을 껐어요.'; }
      catch (e) { psw.checked = false; localStorage.removeItem(LS_PUSH); pnote.textContent = e.pushHost ? '이 기기의 푸시 서버는 아직 허용되지 않았어요.' : api.unsupported(e) ? '서버가 아직 알림을 지원하지 않아요.' : '알림을 켜지 못했어요. 다시 시도해 주세요.'; }
      psw.disabled = false;
    });

    async function checkKeyRotation() {               // push on + server key_id changed → resubscribe silently (permission already granted)
      if (localStorage.getItem(LS_PUSH) !== '1' || !h.isServer() || !h.online() || !('serviceWorker' in navigator)) return;
      try { const k = await api.vapidKey(); if (k && k.key_id && k.key_id !== localStorage.getItem(LS_KID)) await setPush(true); } catch {}
    }
    setTimeout(checkKeyRotation, 3000);
    if (navigator.serviceWorker) navigator.serviceWorker.addEventListener('message', e => { const d = e.data || {}; if (d.type === 'eve-open' && ULID.test(d.nid || '')) { pendingNid = d.nid; refresh(); } });
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') refresh(); });
    pollT = setInterval(() => { if (document.visibilityState === 'visible' && h.online()) refresh(); }, POLL_MS);
    return { refresh, badge, decorateRow, decorateMsg, afterRender, streamCard, actionResult, openSettings, saveSettings, sanitize };
  }
  self.EveProactive = { init, renderConfirmCard, setCardState, ULID, when };
})();
