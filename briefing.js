/* Eve 아침 브리핑 카드 (1.10.0). Built from POST /v1/briefing/preview (eve-serving #77): {status, text, sections:[{name, code?, count}]}.
 * The briefing text is model output: every line is rendered with textContent, nothing is parsed as HTML.
 * Unknown status / section names / codes degrade to generic copy; the card never throws on a shape it does not know. */
(function () {
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const SUN_HORIZON = '<svg class="i" aria-hidden="true"><use href="#i-sun-horizon"/></svg>';
  const SECTION = { events: '일정', reminders: '리마인더' };                    // names the gateway sends today; anything else is shown as given
  const CODE = { pim_unavailable: '연결하지 못했어요', permission_denied: '접근이 허용되지 않았어요', kill_switch: '지금은 꺼져 있어요', timeout: '응답이 늦어요' };
  const STATUS = { skipped_off: '브리핑이 꺼져 있어요', skipped_empty: '오늘은 보여 드릴 내용이 없어요' };
  const FAIL = { off: '지금은 이 기능을 쓸 수 없어요', denied: '이 작업은 할 수 있는 권한이 없어요', net: '연결이 끊겼어요', error: '브리핑을 만들지 못했어요. 잠시 후 다시 시도해 주세요' };
  const own = (o, k) => typeof k === 'string' && Object.hasOwn(o, k);
  const secName = n => (own(SECTION, n) ? SECTION[n] : n) || '항목';
  const TIME = /^(종일|시간 없음|\(기한 지남\) \d{1,2}\/\d{1,2}|(?:\d{1,2}\/\d{1,2} )?\d{1,2}:\d{2})\s+(\S.*)$/;
  const HEAD = /^(\S.*?)\s+(\d+)건$/, FAILED = /^(\S.*?):\s*확인하지 못했어요$/, TRUNC = /일부만 보여요/;

  function renderText(text) {                          // the prompt's fixed shape: "오늘 … 브리핑" / "일정 N건" / "- 시각 제목" (+ deterministic fallback "일정: 확인하지 못했어요", "없음")
    const box = el('div', 'bc-text'); let ul = null, first = true;
    String(text).split(/\r?\n/).map(l => l.trim()).filter(Boolean).forEach(line => {
      let m;
      if (line.startsWith('- ')) {
        if (!ul) { ul = el('ul', 'bc-list'); box.appendChild(ul); }
        const body = line.slice(2).trim(), li = el('li'); m = TIME.exec(body);
        if (TRUNC.test(body)) li.className = 'bc-trunc';
        if (m && !li.className) { li.append(el('span', 'bc-t', m[1]), el('span', 'bc-ti', m[2])); } else li.textContent = body;
        ul.appendChild(li); return;
      }
      ul = null;
      if (first && /^오늘/.test(line)) box.appendChild(el('p', 'bc-date', line));
      else if ((m = FAILED.exec(line))) { const h = el('p', 'bc-h'); h.append(el('span', null, m[1]), el('span', 'bc-note', '확인하지 못했어요')); box.appendChild(h); }
      else if ((m = HEAD.exec(line))) { const h = el('p', 'bc-h'); h.append(el('span', null, m[1]), el('span', 'bc-n', m[2] + '건')); box.appendChild(h); }
      else if (line === '없음') box.appendChild(el('p', 'bc-none', line));
      else box.appendChild(el('p', 'bc-p', line));
      first = false;
    });
    return box;
  }
  function renderSections(list) {
    const ul = el('ul', 'bc-secs'); ul.setAttribute('aria-label', '확인한 항목');
    list.forEach(s => {
      const li = el('li', 'bc-sec' + (s.code ? ' bc-bad' : '')); li.dataset.name = s.name; if (s.code) li.dataset.code = s.code;
      li.append(el('span', 'bc-sn', secName(s.name)),
        el('span', 'bc-sv', s.code ? (own(CODE, s.code) ? CODE[s.code] : '확인하지 못했어요') : s.count == null ? '' : s.count + '건'));
      ul.appendChild(li);
    });
    return ul;
  }
  /* x: normalized preview (EveProactiveAPI.FIELDS.briefing) or {fail:'off'|'denied'|'net'|'error', sections?}; opts.onRetry shows 다시 시도 */
  function card(x, opts = {}) {
    const c = el('section', 'brief-card'); c.setAttribute('aria-label', '아침 브리핑');
    const head = el('div', 'bc-head'); head.insertAdjacentHTML('beforeend', SUN_HORIZON); head.appendChild(el('span', 'bc-title', '아침 브리핑')); head.appendChild(el('span', 'bc-tag', '미리보기')); c.appendChild(head);
    const sections = Array.isArray(x.sections) ? x.sections : [];
    let state, msg = '', body = null, retry = false;
    if (x.fail) { state = x.fail === 'off' || x.fail === 'denied' ? 'off' : 'error'; msg = own(FAIL, x.fail) ? FAIL[x.fail] : FAIL.error; retry = x.fail === 'net' || x.fail === 'error'; }
    else if (x.status === 'ok' || (x.text && !own(STATUS, x.status) && x.status !== 'error')) {   // ok, or an unknown status that still carries text
      if (x.text) { state = 'ok'; body = renderText(x.text); } else { state = 'empty'; msg = STATUS.skipped_empty; }
    }
    else if (own(STATUS, x.status)) { state = 'empty'; msg = STATUS[x.status]; }
    else { state = 'error'; msg = FAIL.error; retry = true; }   // 502 error, or a status we do not know without text
    c.dataset.state = state; c.dataset.status = x.status || '';
    if (body) c.appendChild(body);
    else { const p = el('p', 'bc-msg', msg); p.tabIndex = -1; if (state === 'error') p.setAttribute('role', 'alert'); c.appendChild(p); }
    if (sections.length) c.appendChild(renderSections(sections));
    if (retry && opts.onRetry) { const b = el('button', 'bc-retry', '다시 시도'); b.type = 'button'; b.onclick = opts.onRetry; c.appendChild(b); }
    return c;
  }
  const loading = () => { const c = el('section', 'brief-card'); c.dataset.state = 'loading'; c.setAttribute('aria-busy', 'true'); c.setAttribute('aria-label', '아침 브리핑');
    const head = el('div', 'bc-head'); head.insertAdjacentHTML('beforeend', SUN_HORIZON); head.appendChild(el('span', 'bc-title', '아침 브리핑')); c.appendChild(head); c.appendChild(el('p', 'bc-msg', '브리핑을 만드는 중이에요…')); return c; };
  self.EveBriefing = { card, loading, renderText };
})();
