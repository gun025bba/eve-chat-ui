import { el } from '../../shared/dom.js';
import createPresentation from './model.js';
import createConfirmCards from './confirm-card.js';
export default function createProactive({ proactiveAPI, pim: Pim, briefing }) {
  const shared = { system: { proactive: true, tools: true, memoryRO: false }, cards: new Map(), seq: 0, live: null };
  const model = createPresentation({ proactiveAPI, Pim });
  function say(text) {
    if (!shared.live) {
      shared.live = el('div', 'sr-only'); shared.live.setAttribute('role', 'status');
      shared.live.id = 'proLive'; document.body.appendChild(shared.live);
    }
    shared.live.textContent = ''; setTimeout(() => { shared.live.textContent = text; }, 30);
  }
  const cardController = createConfirmCards({ model, Pim, shared, say });
  const context = { proactiveAPI, Pim, briefing, shared, say, model, cardController };
  return { init: h => init(context, h), ...cardController, ULID: model.ULID, when: model.when };
}

  function init(context, h) {
  const { proactiveAPI, Pim, briefing, shared, say, model, cardController } = context;
  const { F, IC, LS_KID, LS_PUSH, POLL_MS, PUSH_HOSTS, ULID, VERB_LABEL, hm, sanitize, variantOf, verbOf } = model;
  const { renderConfirmCard, actionResult } = cardController;
    const api = proactiveAPI.make(h.api, h.sameOrigin || (() => true));
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
      if (b) { const k = n - (cur ? unreadOf(cur) : 0); b.hidden = k <= 0; b.textContent = k > 99 ? '99+' : String(k);
        const bb = document.getElementById('backBtn'); if (bb) bb.setAttribute('aria-label', k > 0 ? `대화 목록, 안 읽은 메시지 ${k}개` : '대화 목록'); }
    }
    async function refresh() {
      if (!supported || !h.isServer() || !h.online()) return badge();
      if (!sysLoaded) { sysLoaded = true; api.getSettings().then(j => { shared.system = F().system(j); }).catch(() => { sysLoaded = false; }); }
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
      if (m.origin === 'proactive') {   // 1.10.0 B1 (DIRECTION-B §3): the who line + time replace the origin line and the time separator
        const label = m.kind === 'digest' ? 'Eve · 조용한 시간 동안 요약' : m.jobName ? 'Eve · ' + m.jobName : 'Eve가 먼저 보냄', t = m.created || Date.now();
        wrap.classList.add('proactive'); wrap.dataset.origin = 'proactive'; if (m.jobId) wrap.dataset.job = m.jobId;
        wrap.setAttribute('aria-label', (m.readAt ? '' : '읽지 않음, ') + (wrap.querySelector(':scope > .tm')?.textContent || '') + ' ' + label);
        if (!m.readAt) wrap.dataset.unread = '';
        const who = wrap.querySelector(':scope > .who');
        if (who) {
          who.querySelector('.who-ic')?.remove();
          const ic = IC[{ briefing: 'sun-horizon', watch: 'eye', followup: 'uturn' }[m.templateKind] || 'sparkle']; if (ic) who.insertAdjacentHTML('afterbegin', ic.replace('class="i"', 'class="i who-ic"'));
          who.querySelector('.who-n').textContent = label;
        }
      }
      if (m.briefing && Pim && !wrap.querySelector(':scope > .pim-brief')) {   // saved briefing message (eve-serving #66 §11.3): structured card under the summary text
        let c = null; try { c = Pim.briefingCard(m.briefing); } catch {}
        if (c) { const b = wrap.querySelector(':scope > .bubble'); if (b) b.after(c); else wrap.appendChild(c); }
      }
      (m.pendingActions || []).forEach(a => mountCard(a, wrap));
    }
    function ccHost(after) {   // the .cc-stack lives inside the message (.ev body column): after the text / chips / briefing card, before the action row
      let s = after.querySelector(':scope > .cc-stack'); if (s) return s;
      s = el('div', 'cc-stack'); const act = after.querySelector(':scope > .actions'); if (act) act.before(s); else after.appendChild(s); return s;
    }
    function mountCard(a, after) {
      if (shared.cards.has(a.action_id) && document.body.contains(shared.cards.get(a.action_id))) return;
      const host = ccHost(after);   // §8.2: inside the Eve event body (under the text, 8px), not a sibling row
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
            if (shared.cards.has(a.action_id) && document.body.contains(shared.cards.get(a.action_id))) return;
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
    let srv = null, vapidOK = false;               // pushRow only after a successful vapid-key fetch                                    // last server copy of settings
    const showQ = () => { qSV.textContent = hm(qS.value); qEV.textContent = hm(qE.value); const bad = qS.value && qS.value === qE.value; qErr.hidden = !bad; };
    function paint() {
      const p = srv?.proactive || {};
      sw.checked = !!p.enabled; more.hidden = !p.enabled;
      const q = p.quiet_hours || {}; qS.value = q.start || '22:00'; qE.value = q.end || '08:00'; showQ();
      memRow.hidden = !(srv?.memory?.enabled); msw.checked = !!p.memory_read;
      pushRow.hidden = !(p.enabled && h.isStandalone() && vapidOK); psw.checked = localStorage.getItem(LS_PUSH) === '1';
    }
    /* 아침 브리핑 미리보기 (1.10.0): row only when GET /v1/settings carries `briefing` (the gateway adds it only when briefing is enabled) */
    const bSec = $('briefSection'), bRun = $('briefRun'), bOut = $('briefOut'); let bSeq = 0;
    async function briefingRun() {
      if (bRun.disabled) return; const my = ++bSeq;
      bRun.disabled = true; bRun.setAttribute('aria-busy', 'true'); bOut.replaceChildren(briefing.loading());
      const done = c => { if (my !== bSeq) return; bRun.disabled = false; bRun.removeAttribute('aria-busy'); bOut.replaceChildren(c); };
      const retry = () => briefingRun();
      try { done(briefing.card(F().briefing(await api.briefingPreview()), { onRetry: retry })); }
      catch (e) {
        if (!e.http) return done(briefing.card({ fail: 'net' }, { onRetry: retry }));
        if (e.http === 404) { bSec.hidden = true; return done(briefing.card({ fail: 'off' })); }     // switched off since settings loaded
        if (e.code === 'scope_denied') return done(briefing.card({ fail: 'denied' }));
        if (e.http === 502 && e.body && typeof e.body.status === 'string') return done(briefing.card(F().briefing(e.body), { onRetry: retry }));   // {status, sections}, no text
        done(briefing.card({ fail: 'error' }, { onRetry: retry }));
      }
    }
    bRun.addEventListener('click', () => { if (!h.online()) { h.showToast('연결되면 확인할 수 있어요'); return; } briefingRun(); });
    async function openSettings() {
      $('qStartWrap').hidden = $('qEndWrap').hidden = true; bSec.hidden = true; bSeq++; bOut.replaceChildren(); bRun.disabled = false;
      if (!h.isServer()) { sw.disabled = true; more.hidden = true; note.textContent = '서버에 연결되면 설정할 수 있어요.'; return; }
      sw.disabled = true; note.textContent = 'Eve가 브리핑이나 알림을 먼저 보낼 수 있어요. 하루 최대 3번.';
      try {
        srv = await api.getSettings() || {}; shared.system = F().system(srv); delete srv.system;   // system.* is read-only: never PATCHed
        sw.disabled = !shared.system.proactive; paint();
        bSec.hidden = !(srv.briefing && typeof srv.briefing === 'object' && P.sameOrigin());
        if (!shared.system.proactive) { more.hidden = true; note.textContent = '지금은 이 기능을 쓸 수 없어요'; }
        msw.disabled = shared.system.memoryRO;
        if (!vapidOK && h.isStandalone()) api.vapidKey().then(k => { if (k && k.key) { vapidOK = true; paint(); } }).catch(() => {});
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
    /* 오늘 · 확인 대기 (DIRECTION-B §6): the pending confirmations as plain data for the Today card. Read-only — no token, no approve. Throws on any API error. */
    async function pendingList() {
      if (!h.isServer() || !h.online()) return null;
      const j = await api.pendingActions(), raw = j && Array.isArray(j.data) ? j.data : [];
      const items = raw.map(a => {
        const x = F().action(a), v = x.view || {}, verb = verbOf(x), t = typeof v.title === 'string' && v.title.trim() ? v.title.trim() : x.summary.trim();
        return { id: x.id, title: t, verb, verbLabel: VERB_LABEL[verb], display: variantOf(x) === 'proactive' && x.display ? x.display : null,   // 2nd line only for a scheduled reminder
          expiresAt: x.expiresAt, threadId: x.threadId, messageId: x.messageId, created: Date.parse(a && a.created_at) || 0, status: x.status };
      }).filter(i => i.id && i.threadId && (!i.status || i.status === 'pending'));
      if (items.length && items.every(i => i.created)) items.sort((a, b) => a.created - b.created);   // oldest first (server order otherwise)
      return items;
    }
    /* 오늘 일정 cell (B3 §7): GET /v1/settings `briefing.enabled`. false → the briefing is switched off → the cell is hidden; no `briefing` key / no boolean → unknown (null) → the saved briefing message decides. */
    async function briefingEnabled() {
      if (!h.isServer() || !h.online()) return null;
      const s = await api.getSettings(), b = s && s.briefing;
      return b && typeof b === 'object' && typeof b.enabled === 'boolean' ? b.enabled : null;
    }
    return { pendingList, briefingEnabled, refresh, badge, decorateRow, decorateMsg, afterRender, streamCard, actionResult, openSettings, saveSettings, sanitize };
  }
