/* Eve 1.10.0 B2 (DIRECTION-B-SPEC §4): the "오늘" screen's timeline.
 * model()  — pure: which events to show, from the thread list (no DOM, no network)
 * init()   — renders them into #todayList with the shared .rail/.ev/.dot components
 * Pending confirmations, the status strip and today's schedule are B3: nothing here reads /v1/actions or the briefing sections. */
(function () {
  const MAX_CONV = 5, CONT_DAYS = 7, DAY = 864e5;
  const KST_YMD = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' });
  const KST_HM = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
  const WD = '일월화수목금토';
  const kstDay = t => { try { return KST_YMD.format(new Date(t)); } catch { return ''; } };
  const hhmm = t => { try { return KST_HM.format(new Date(t)); } catch { return ''; } };
  const wdOf = ymd => { const [y, m, d] = ymd.split('-').map(Number); return WD[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]; };
  const dateLine = (t = Date.now()) => { const [, m, d] = kstDay(t).split('-').map(Number); return `${m}월 ${d}일 ${wdOf(kstDay(t))}요일`; };
  const shortDay = (t, now) => { const d = kstDay(t); if (d === kstDay(now - DAY)) return '어제'; const [, m, da] = d.split('-'); return `${m}.${da}`; };
  const flat = s => String(s || '').replace(/```[\s\S]*?(```|$)/g, ' [코드] ').replace(/[#*`>_|]+/g, '').replace(/\s+/g, ' ').trim();

  const proLabel = m => (m.kind === 'digest' ? 'Eve · 조용한 시간 동안 요약' : m.jobName ? 'Eve · ' + m.jobName : 'Eve가 먼저 보냄');
  const proIcon = m => ({ briefing: 'sun-horizon', watch: 'eye', followup: 'followup' }[m.templateKind] || 'sparkle');
  const userMsgs = c => (c.messages || []).filter(m => m.role === 'user');
  const isProOnly = c => !!(c.messages && c.messages.length && !userMsgs(c).length);

  // → { events:[{kind:'pro'|'conv', t, c, m?}], more:N, cont:{c,t}|null, candidates:[c…] (threads whose messages should be loaded) }
  function model(convs, now = Date.now(), opts = {}) {
    const T = kstDay(now), live = convs.filter(c => !c.archived), ev = [], candidates = [];
    for (const c of live) {
      if (!(c.updated > 0) || kstDay(c.updated) !== T) continue;
      candidates.push(c);
      const ms = (c.messages || []).filter(m => m.created > 0 && kstDay(m.created) === T);
      for (const m of ms) if (m.role === 'assistant' && m.origin === 'proactive' && (m.content || '').trim()) ev.push({ kind: 'pro', t: m.created, c, m });
      const u = ms.find(m => m.role === 'user');
      if (u) ev.push({ kind: 'conv', t: u.created, c });
    }
    ev.sort((a, b) => a.t - b.t);
    const convEv = ev.filter(e => e.kind === 'conv');
    let more = 0, shown = ev;
    if (convEv.length > MAX_CONV) { const keep = new Set(convEv.slice(-MAX_CONV)); more = convEv.length - MAX_CONV; shown = ev.filter(e => e.kind !== 'conv' || keep.has(e)); }
    // 이어서: the latest earlier thread inside 7 days that is not a proactive-only thread
    const older = live.filter(c => c.updated > 0 && kstDay(c.updated) < T && now - c.updated <= CONT_DAYS * DAY).sort((a, b) => b.updated - a.updated);
    let cont = null;
    for (const c of older.slice(0, 3)) { candidates.push(c); if (!cont && !isProOnly(c)) { cont = { c, t: c.updated }; if (c.messages && c.messages.length) break; } }
    return { events: shown, more, cont, candidates, today: T };
  }

  function init(ctx) {
    const $ = s => document.querySelector(s), list = $('#todayList');
    let first = true;
    const ic = (name, cls) => { const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('class', 'i ' + (cls || '')); s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('aria-hidden', 'true'); const u = document.createElementNS('http://www.w3.org/2000/svg', 'use'); u.setAttribute('href', '#i-' + name); s.appendChild(u); return s; };
    function ev(cls, t, tmText, who, whoCls, body, label) {
      const li = document.createElement('li'); li.className = 'ev ' + cls; li.setAttribute('role', 'listitem'); li.setAttribute('aria-label', label || `${tmText} ${who}`);
      const tm = document.createElement('time'); tm.className = 'tm'; tm.textContent = tmText; if (t) tm.dateTime = new Date(t).toISOString();
      const dot = document.createElement('span'); dot.className = 'dot'; dot.setAttribute('aria-hidden', 'true');
      const w = document.createElement('div'); w.className = 'who'; if (whoCls) w.classList.add(whoCls); const wn = document.createElement('span'); wn.className = 'who-n'; wn.textContent = who; w.appendChild(wn);
      li.append(tm, dot, w);
      if (body) { const b = document.createElement('div'); b.className = 'tx d'; if (typeof body === 'string') b.textContent = body; else b.append(...body); li.appendChild(b); }
      return li;
    }
    const hit = (li, label, fn) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'ev-hit'; b.setAttribute('aria-label', label); b.addEventListener('click', fn); li.appendChild(b); li.classList.add('tap'); };
    function skeleton() { const f = document.createDocumentFragment(); for (let i = 0; i < 2; i++) { const li = document.createElement('li'); li.className = 'ev skel-ev'; li.setAttribute('aria-hidden', 'true'); li.innerHTML = '<i class="s-tm"></i><span class="dot"></span><i class="s-a"></i><i class="s-b"></i>'; f.appendChild(li); } return f; }
    function render() {
      const now = Date.now(), M = model(ctx.convs(), now), st = ctx.state();
      list.replaceChildren();
      const frag = document.createDocumentFragment();
      if (st.error && !ctx.convs().length) {
        const li = document.createElement('li'); li.className = 'ev t-err'; li.setAttribute('role', 'listitem');
        li.innerHTML = '<span class="dot" aria-hidden="true"></span>'; const b = document.createElement('div'); b.className = 't-err-b';
        b.append(ic('warning'), Object.assign(document.createElement('span'), { textContent: '불러오지 못했어요' }));
        const r = document.createElement('button'); r.type = 'button'; r.id = 'todayRetry'; r.className = 'text-btn'; r.textContent = '다시 시도'; r.addEventListener('click', () => ctx.retry());
        li.append(b, r); frag.appendChild(li);
      } else if (st.skeleton) frag.appendChild(skeleton());
      else {
        if (M.more) { const li = ev('more', 0, '', '기록에서 더 보기', 'sub', `오늘 대화 ${M.more}개`, `기록에서 더 보기, 오늘 대화 ${M.more}개`); hit(li, '기록에서 더 보기', () => ctx.openLog()); frag.appendChild(li); }
        for (const e of M.events) {
          if (e.kind === 'pro') {
            const label = proLabel(e.m), li = ev('e pro', e.t, hhmm(e.t), label, 'brand', flat(e.m.content).slice(0, 400), (e.m.readAt ? '' : '읽지 않음, ') + `${hhmm(e.t)} ${label}`);
            li.dataset.tid = e.c.id; if (e.m.id) li.dataset.mid = e.m.id; if (!e.m.readAt) li.dataset.unread = '';
            li.querySelector('.who').prepend(ic(proIcon(e.m), 'who-ic')); hit(li, `${label} 열기`, () => ctx.open(e.c, e.m.id)); frag.appendChild(li);
          } else {
            const li = ev('me conv', e.t, hhmm(e.t), ctx.userName(), 'sub', null, `${hhmm(e.t)} ${ctx.userName()} ${e.c.title}`);
            const b = document.createElement('div'); b.className = 'tx'; b.textContent = e.c.title || '새 대화'; li.appendChild(b); li.dataset.tid = e.c.id;
            hit(li, `${e.c.title || '새 대화'} 열기`, () => ctx.open(e.c)); frag.appendChild(li);
          }
        }
        if (M.cont) {
          const c = M.cont.c, pv = flat(ctx.preview(c)), li = ev('cont', M.cont.t, shortDay(M.cont.t, now), '이어서', 'sub', null, `${shortDay(M.cont.t, now)} 이어서 ${c.title}`);
          const b = document.createElement('div'); b.className = 'tx d'; const t = document.createElement('span'); t.className = 'ct'; t.textContent = c.title || '새 대화'; b.appendChild(t);
          if (pv) { const p = document.createElement('span'); p.className = 'cp'; p.textContent = pv; b.appendChild(p); } li.appendChild(b); li.dataset.tid = c.id;
          hit(li, `${c.title || '새 대화'} 이어서`, () => ctx.open(c)); frag.appendChild(li);
        }
      }
      const nowEl = document.createElement('li'); nowEl.className = 'rail-now'; nowEl.setAttribute('role', 'listitem'); nowEl.setAttribute('aria-label', `${hhmm(now)} 지금`);
      nowEl.innerHTML = '<time class="tm"></time><span class="dot" aria-hidden="true"></span><div class="who"><span class="who-n">지금</span></div><div class="tx d">아래에 한 줄로 남기면 오늘 기록에 쌓여요.</div>';
      nowEl.querySelector('.tm').textContent = hhmm(now); frag.appendChild(nowEl);
      list.appendChild(frag);
      list.dataset.day = M.today;
      const settled = !st.skeleton && !(st.error && !ctx.convs().length);   // the stagger is for real content only, never for a skeleton or an error
      if (first && settled && ctx.stagger()) { first = false; [...list.children].slice(0, 5).forEach((li, i) => { li.classList.add('stg'); li.style.animationDelay = i * 40 + 'ms'; }); }
      else if (settled) first = false;
      return M;
    }
    function tick() { const n = list.querySelector('.rail-now'); if (!n) return; const t = Date.now(); n.querySelector('.tm').textContent = hhmm(t); n.setAttribute('aria-label', `${hhmm(t)} 지금`); }
    return { render, tick, model: () => model(ctx.convs()) };
  }
  self.EveToday = { init, model, kstDay, hhmm, dateLine, shortDay, proLabel };
})();
