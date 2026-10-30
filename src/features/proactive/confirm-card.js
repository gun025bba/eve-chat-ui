import { el } from '../../shared/dom.js';
export default function createConfirmCards(context) {
  return {
    renderConfirmCard: (action, opts) => renderConfirmCard(context, action, opts),
    setCardState: (id, state, message) => setCardState(context, id, state, message),
    actionResult: (result) => actionResult(context, result)
  };
}
  function renderConfirmCard(context, action, opts) {
  const { model, Pim, shared, say } = context;
  const { CROSS, DENIED, EXEC_ERR, EXPIRED, F, IC, OUTCOME_UNKNOWN, PIM, VAR,
    dangerOf, deniedText, pimRows, sanitize, shortDate, variantOf } = model;

    const P = opts.P, a = sanitize(action), x = F().action(action), id = x.id;
    const variant = variantOf(x), V = VAR[variant], danger = dangerOf(x, variant), n = ++shared.seq;
    const retries = opts.retries || 0;               // "다시 요청" count, carried across in-place replacement
    const card = el('div', 'confirm-card'); card.dataset.variant = variant; card.dataset.aid = id || '';
    card.setAttribute('role', 'group'); card.setAttribute('aria-labelledby', 'cct' + n);
    if (id) shared.cards.set(id, card);
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
      const v = x.view, dl = el('dl', 'cc-view'), pim = PIM(x) && Pim.isWrite(x.tool), ks = pim ? pimRows(x) : Object.keys(v).filter(k => k !== 'verb').map(k => { const val = v[k], raw = typeof val === 'string' ? val : JSON.stringify(val); return [k, k, raw, null]; });   // verb is metadata (button label), not a row
      ks.forEach(([k, label, text, raw], i) => {
        const dt = el('dt', null, label), dd = el('dd', null, text);
        if (raw) dd.title = raw;
        dt.dataset.k = k; if (i >= 6) dt.hidden = dd.hidden = true; dl.append(dt, dd);
      });
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
    const blocked = () => cross() || (variant === 'tool' && !shared.system.tools) || ((variant === 'remember' || variant === 'forget') && shared.system.memoryRO);
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
      if (e.outcomeUnknown === true || (e.outcomeUnknown === undefined && !e.code && (e.http === 502 || e.http === 504))) { retryFn = null; return setState('error', OUTCOME_UNKNOWN(x)); }   // #78 502 outcome_unknown: the card is consumed server-side → no retry, no re-approve, no recheck
      if (e.outcomeUnknown === false && e.code !== 'writes_disabled' && e.code !== 'not_found' && e.code !== 'kill_switch' && e.code !== 'item_gone')   // #78 502, card released: nothing was written, a fresh reissue → approve is safe
        return setState('error', EXEC_ERR[e.code] || '실행하지 못했어요. 잠시 후 다시 시도해 주세요', { retry });
      if (e.code === 'expired') return setState('expired', EXPIRED);          // branch on body.error_code, never on HTTP status
      if (e.code === 'internal_error') return setState('error', '저장하지 못했어요. 잠시 후 다시 시도해 주세요', { retry });   // 500 fail-closed: nothing changed, fresh reissue → approve is safe
      if (e.code === 'memory_read_only') { shared.system.memoryRO = true; }
      if (e.code === 'conflict') return recheck(() => setState('denied', DENIED.conflict));   // 1.1.1: load the real outcome first
      return setState('denied', deniedText(e.code || 'invalid'));
    }
    async function revise(itemIds, nextRetries) {     // partial forget / 다시 요청 → new proposal replaces this card in place
      setState('revising');
      try {
        const next = await P.api.revise(id, itemIds);
        if (!next || !next.action_id) throw Object.assign(new Error('bad'), { http: 400 });
        shared.cards.delete(id); clearInterval(timer);   // any token in the revise response is ignored: approve fetches its own
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
        retryFn = () => { setState('pending'); yes.onclick(); }; settleErr(e, retryFn);
      }
    };
    async function recheck(onFail) {                         // GET /v1/actions/{id} (fallback: pending list) to learn the real outcome
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
        if (st === 'executing') continue;                 // 1.1.1: still running, keep polling
        if (st === 'executed') return setState('confirmed', V.done(x, checked().length || x.items.length));
        if (st === 'pending') return setState('pending');   // not executed: user may press again (fresh reissue → approve)
        if (st === 'rejected') return setState('declined', '취소했어요');
        if (st === 'expired') return setState('expired', EXPIRED);
        if (st === 'failed') return setState('error', '실행하지 못했어요');
        if (onFail) return onFail();
        return setState('error', '결과를 확인하지 못했어요. 대화를 새로고침해 확인해 주세요');
      }
      meta.textContent = ''; if (onFail) return onFail(); setState('error', '결과를 확인하지 못했어요. 연결되면 다시 확인할게요', { retry: recheck });
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
    card._replace = (next, r) => { const c2 = renderConfirmCard(context, next, Object.assign({}, opts, { retries: r == null ? retries : r })); card.replaceWith(c2); return c2; };
    if (!st || st === 'pending') say('확인이 필요해요: ' + V.title(x));
    return card;
  }
  function setCardState(context, id, s, msg) { const { shared } = context; const c = shared.cards.get(id); if (c && c._setState) c._setState(s, msg); }
  function actionResult(context, j) {
  const { shared, model: { EXPIRED } } = context;
    const map = { executed: ['confirmed', '실행했어요'], rejected: ['declined', '취소했어요'], expired: ['expired', EXPIRED], failed: ['error', '실행하지 못했어요'] };
    const c = shared.cards.get(j.action_id); if (!c || !c._setState || ['confirmed', 'declined', 'expired', 'error', 'denied'].includes(c.dataset.state)) return;
    const m = map[j.status] || map.failed; c._setState(m[0], m[1]);
  }

