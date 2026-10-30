/* eve-web 1.10.0 — calendar & reminders (M1) UI pieces. Contract: eve-serving #66 §11 (35c1260).
 * Everything here is DOM-only (textContent): titles, calendar/list names and locations are untrusted text. */
(function () {
  'use strict';
  const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
  const own = (o, k) => typeof k === 'string' && Object.hasOwn(o, k);
  const isObj = x => !!x && typeof x === 'object' && !Array.isArray(x);
  const str = x => (typeof x === 'string' ? x : '');
  const cnt = x => (typeof x === 'number' && Number.isFinite(x) && x >= 0 ? Math.floor(x) : null);

  /* ---------- KST display (§11.4): Asia/Seoul, 24h, one-letter weekday, year only when not the current KST year, no suffix ---------- */
  const DAY = 86400000, WD = ['일', '월', '화', '수', '목', '금', '토'];
  function parse(v) { if (typeof v !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v)) return NaN; return Date.parse(v); }
  function kst(ms) { const d = new Date(ms + 9 * 3600000); return { y: d.getUTCFullYear(), m: d.getUTCMonth() + 1, d: d.getUTCDate(), wd: WD[d.getUTCDay()], h: d.getUTCHours(), mi: d.getUTCMinutes() }; }
  const p2 = n => String(n).padStart(2, '0');
  function dateOf(k, now) { return (k.y === kst(now).y ? '' : k.y + '/') + k.m + '/' + k.d + ' (' + k.wd + ')'; }
  const timeOf = k => p2(k.h) + ':' + p2(k.mi);
  const sameDay = (a, b) => a.y === b.y && a.m === b.m && a.d === b.d;
  /** start/end RFC3339 (+09:00). all-day: end is the exclusive next day 00:00 → shown inclusive. Unparsable input is returned as written. */
  function fmtRange(start, end, allDay, now) {
    now = now == null ? Date.now() : now;
    const s = parse(start); if (Number.isNaN(s)) return str(start);
    const e = parse(end), ks = kst(s);
    if (allDay === true) {
      const last = Number.isNaN(e) || e <= s ? ks : kst(e - DAY);
      return sameDay(ks, last) ? dateOf(ks, now) + ' 종일' : dateOf(ks, now) + ' – ' + dateOf(last, now) + ' 종일';
    }
    if (Number.isNaN(e) || e <= s) return dateOf(ks, now) + ' ' + timeOf(ks);
    const ke = kst(e);
    return sameDay(ks, ke) ? dateOf(ks, now) + ' ' + timeOf(ks) + '–' + timeOf(ke) : dateOf(ks, now) + ' ' + timeOf(ks) + ' – ' + dateOf(ke, now) + ' ' + timeOf(ke);
  }
  function fmtDue(due, now) { const s = parse(due); if (Number.isNaN(s)) return str(due); const k = kst(s); return dateOf(k, now == null ? Date.now() : now) + ' ' + timeOf(k); }
  /** date-only label for a [from,to) range: 10/28 (수) or 10/28 (수) – 10/30 (금) (end inclusive) */
  function fmtDays(from, to, now) {
    now = now == null ? Date.now() : now;
    const a = parse(from); if (Number.isNaN(a)) return '';
    const b = parse(to), ka = kst(a), kb = Number.isNaN(b) || b <= a ? ka : kst(b - 1);
    return sameDay(ka, kb) ? dateOf(ka, now) : dateOf(ka, now) + ' – ' + dateOf(kb, now);
  }

  /* ---------- tools, status text, error copy (§11.1 / §11.2) ---------- */
  const READ = { calendar_list_events: '일정 확인 중…', reminders_list: '리마인더 확인 중…' };
  const WRITE = { reminders_add: 1, reminders_complete: 1, calendar_add_event: 1 };
  const PREP = '확인 카드를 준비하는 중…', READ_FAILED = '확인하지 못한 채로 답변 작성 중…', COMPOSE = '답변 작성 중…';
  const isTool = t => own(READ, t) || own(WRITE, t);
  const ERR = {
    pim_unavailable: '캘린더·리마인더에 연결할 수 없어요', permission_denied: '캘린더·리마인더 접근 권한이 없어요. 서버에서 권한을 허용해야 해요',
    scope_denied: '이 작업은 할 수 있는 권한이 없어요', kill_switch: '지금은 이 기능을 쓸 수 없어요', timeout: '응답이 늦어 확인하지 못했어요',
    invalid_arguments: '요청 내용이 올바르지 않아요', not_found: '대상을 찾을 수 없어요', writes_disabled: '지금은 쓰기가 꺼져 있어요'
  };
  const errText = code => (own(ERR, code) ? ERR[code] : ERR.invalid_arguments);   // unknown codes (Q14 secret_detected, cap_exceeded …) use the `invalid` copy
  const callText = tool => (own(READ, tool) ? READ[tool] : own(WRITE, tool) ? PREP : '');
  function resultText(j) {
    const ok = j.status === 'ok';
    if (own(WRITE, j.tool)) return j.status === 'pending_confirmation' ? PREP : COMPOSE;
    return ok ? COMPOSE : READ_FAILED;
  }

  /* ---------- result cards ---------- */
  const ICON = {
    cal: '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="3"/><path d="M4 10h16M9 3v4M15 3v4"/></svg>',
    rem: '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M8.5 12.2l2.4 2.4 4.6-5"/></svg>',
    'sun-horizon': '<svg class="i" aria-hidden="true"><use href="#i-sun-horizon"/></svg>',
    warn: '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.2v.1"/></svg>'
  };
  const FOLD = 10;
  function head(ic, title, sub) {
    const h = el('div', 'bc-head'); h.insertAdjacentHTML('beforeend', ic); h.appendChild(el('span', 'bc-title', title));
    if (sub) h.appendChild(el('span', 'pc-sub', sub)); return h;
  }
  function list(items, build) {
    const ul = el('ul', 'pc-list'); let more = null;
    items.forEach((it, i) => { const li = build(it); if (i >= FOLD) li.hidden = true; ul.appendChild(li); });
    if (items.length > FOLD) {
      const b = el('button', 'pc-more', `${items.length - FOLD}건 더 보기`); b.type = 'button';
      b.onclick = () => { ul.querySelectorAll('li[hidden]').forEach(x => { x.hidden = false; }); b.remove(); }; more = b;
    }
    return [ul, more];
  }
  const row = (title, meta, extra) => {
    const li = el('li', 'pc-row' + (extra || '')); li.appendChild(el('span', 'pc-ti', title || '(제목 없음)'));
    if (meta) li.appendChild(el('span', 'pc-meta', meta)); return li;
  };
  function eventsCard(card, j, now) {
    const items = (Array.isArray(card.items) ? card.items : []).filter(isObj).map(x => ({ title: str(x.title), start: str(x.start), end: str(x.end), allDay: x.all_day === true, cal: str(x.calendar) }));
    const r = isObj(card.range) ? card.range : {}, c = el('section', 'brief-card pim-card'); c.dataset.kind = 'calendar_events'; c.setAttribute('aria-label', '일정');
    c.appendChild(head(ICON.cal, items.length ? `일정 ${items.length}건` : '일정', fmtDays(r.from, r.to, now)));
    if (!items.length) c.appendChild(el('p', 'bc-none', '일정이 없어요'));
    else { const [ul, more] = list(items, x => row(x.title, [fmtRange(x.start, x.end, x.allDay, now), x.cal].filter(Boolean).join(' · '))); c.appendChild(ul); if (more) c.appendChild(more); }
    if (j && j.truncated === true) c.appendChild(el('p', 'pc-trunc', '일부만 보여요. 기간을 좁히면 더 볼 수 있어요'));
    return c;
  }
  function remindersCard(card, j, now) {
    const items = (Array.isArray(card.items) ? card.items : []).filter(isObj).map(x => ({ title: str(x.title), due: typeof x.due === 'string' ? x.due : null, list: str(x.list), done: x.done === true }));
    const c = el('section', 'brief-card pim-card'); c.dataset.kind = 'reminders'; c.setAttribute('aria-label', '리마인더');
    const db = parse(card.due_before), sub = Number.isNaN(db) ? '' : fmtDays(db - 1, db, now) + '까지';
    c.appendChild(head(ICON.rem, items.length ? `리마인더 ${items.length}건` : '리마인더', sub));
    if (!items.length) c.appendChild(el('p', 'bc-none', '리마인더가 없어요'));
    else { const [ul, more] = list(items, x => { const li = row(x.title, [x.due ? fmtDue(x.due, now) : '기한 없음', x.list].filter(Boolean).join(' · '), x.done ? ' is-done' : ''); if (x.done) li.appendChild(el('span', 'pc-done', '완료')); return li; }); c.appendChild(ul); if (more) c.appendChild(more); }
    if (j && j.truncated === true) c.appendChild(el('p', 'pc-trunc', '일부만 보여요. 기한을 좁히면 더 볼 수 있어요'));
    return c;
  }
  function errorCard(card, j) {
    const code = typeof card.error_code === 'string' ? card.error_code : str(j && j.error_code);
    const c = el('section', 'brief-card pim-card pim-err'); c.dataset.kind = 'error'; c.dataset.code = code; c.setAttribute('role', 'status');
    c.insertAdjacentHTML('beforeend', ICON.warn); c.appendChild(el('p', 'pc-errtx', errText(code))); return c;
  }
  /** tool_result.card → element, or null (unknown kind / newer v / malformed → the status text alone stays) */
  function resultCard(j, now) {
    if (!j || !isTool(j.tool) || !isObj(j.card)) return null;
    const card = j.card; if (typeof card.v !== 'number' || card.v < 1 || card.v > 1) return null;
    if (card.kind === 'error') return errorCard(card, j);
    if (j.status !== 'ok') return null;
    if (card.kind === 'calendar_events' && j.tool === 'calendar_list_events') return eventsCard(card, j, now);
    if (card.kind === 'reminders' && j.tool === 'reminders_list') return remindersCard(card, j, now);
    return null;
  }
  /** the stream-only stack that also holds the confirm card (same .cc-stack proactive.js mounts into) */
  function mount(node, after) {
    if (!node || !after) return;
    let host = after.querySelector(':scope > .cc-stack');   // §8.2: inside the event body, after the text and before the action row
    if (!host) { host = el('div', 'cc-stack'); const act = after.querySelector(':scope > .actions'); if (act) act.before(host); else after.appendChild(host); }
    host.appendChild(node);
  }

  /* ---------- saved briefing message (§11.3): validated once, rendered from the top-level `briefing` ---------- */
  const SEC = { events: { name: '일정', ic: 'cal' }, reminders: { name: '리마인더', ic: 'rem' } };
  function cleanBriefing(b) {
    if (!isObj(b) || b.schema !== 1) return null;                    // newer schema → content only
    const secs = (Array.isArray(b.sections) ? b.sections : []).filter(s => isObj(s) && own(SEC, s.kind)).map(s => {
      const ok = s.status === 'ok', n = cnt(s.count), its = (Array.isArray(s.items) ? s.items : []).filter(isObj).slice(0, 10);
      return { kind: s.kind, ok, code: ok ? null : (typeof s.error_code === 'string' ? s.error_code : null), count: n == null ? its.length : n, truncated: s.truncated === true,
        items: its.map(x => s.kind === 'events' ? { title: str(x.title), start: str(x.start), end: str(x.end), allDay: x.all_day === true, cal: str(x.calendar) }
          : { title: str(x.title), due: typeof x.due === 'string' ? x.due : null, list: str(x.list), overdue: x.overdue === true }) };
    });
    return { schema: 1, status: ['ok', 'partial', 'unavailable'].includes(b.status) ? b.status : 'partial', date: str(b.date), source: ['model', 'template', 'fixed'].includes(b.text_source) ? b.text_source : null, sections: secs };
  }
  function briefingCard(b, now) {
    if (!b || !b.sections.length) return null;
    const c = el('section', 'brief-card pim-card pim-brief'); c.dataset.status = b.status; if (b.source) c.dataset.source = b.source; c.setAttribute('aria-label', '아침 브리핑');
    const dm = /^(\d{4})-(\d{2})-(\d{2})$/.exec(b.date), dl = dm ? fmtDays(`${b.date}T00:00:00+09:00`, `${b.date}T00:00:00+09:00`, now) : '';
    c.appendChild(head(ICON['sun-horizon'], '아침 브리핑', dl));
    b.sections.forEach(s => {
      const sec = el('div', 'pc-sec'); sec.dataset.kind = s.kind; const h = el('p', 'bc-h'); h.appendChild(el('span', null, SEC[s.kind].name));
      if (!s.ok) { h.appendChild(el('span', 'bc-note pc-bad', '확인 불가')); sec.appendChild(h); if (s.code) sec.appendChild(el('p', 'pc-why', errText(s.code))); c.appendChild(sec); return; }
      h.appendChild(el('span', 'bc-n', s.count + '건')); sec.appendChild(h);
      if (!s.items.length) sec.appendChild(el('p', 'bc-none', s.kind === 'events' ? '일정이 없어요' : '리마인더가 없어요'));
      else {
        const ul = el('ul', 'pc-list');
        s.items.forEach(x => { const meta = s.kind === 'events' ? [fmtRange(x.start, x.end, x.allDay, now), x.cal] : [x.due ? fmtDue(x.due, now) : '기한 없음', x.list]; const li = row(x.title, meta.filter(Boolean).join(' · '), x.overdue ? ' is-overdue' : ''); if (x.overdue) li.appendChild(el('span', 'pc-late', '기한 지남')); ul.appendChild(li); });
        sec.appendChild(ul);
        const rest = s.count - s.items.length; if (rest > 0) sec.appendChild(el('p', 'pc-trunc', `외 ${rest}건`));
      }
      c.appendChild(sec);
    });
    return c;
  }

  self.EvePim = { isTool, isWrite: t => own(WRITE, t), callText, resultText, errText, resultCard, mount, fmtRange, fmtDue, fmtDays, cleanBriefing, briefingCard, ERR };
})();
