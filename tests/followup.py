# 1.10.0 follow-up (designer approval of #21–#24): a accent-fill · b + menu close · c chips fade token · d #messages label · e one sun icon · f nav ::before easing
# · g confirm card inside the event body · h usage line on one line · i snoozed items out of the pending strip/sheet · j button transitions · k briefing.enabled
import re, os
from playwright.sync_api import sync_playwright
from b3_common import *
R = []; errs = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CSS = open(f'{ROOT}/styles.css').read(); APP = open(f'{ROOT}/app.js').read()
LUM = """(c) => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4) }; const m = c.match(/\\d+(\\.\\d+)?/g).map(Number); return .2126 * f(m[0]) + .7152 * f(m[1]) + .0722 * f(m[2]) }"""
def cr_white(pg, color): l = pg.evaluate(f'({LUM})("{color}")'); return round(1.05 / (l + .05), 2)
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---- a) --accent-fill
    for scheme, want, fill in (('dark', 'rgb(10, 111, 232)', '#0A6FE8'), ('light', 'rgb(0, 113, 227)', '#0071E3')):
        reset(); rich(); seed_act(act(1, title='치과 예약', exp=60 * 24), title='치과 예약')
        ctx, pg = newpg(b, errs, scheme=scheme); goto_today(pg)
        tok = pg.evaluate("(() => { const e = document.createElement('i'); e.style.color = 'var(--accent-fill)'; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c })()")
        acc = pg.evaluate("(() => { const e = document.createElement('i'); e.style.color = 'var(--accent)'; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c })()")
        check(f'{scheme}: --accent-fill = {fill}', tok == want, tok)
        check(f'{scheme}: --accent (text / links) is unchanged', acc == ('rgb(10, 132, 255)' if scheme == 'dark' else 'rgb(0, 122, 255)'), acc)
        check(f'{scheme}: white on --accent-fill = {cr_white(pg, tok)}:1 ≥ 4.5', cr_white(pg, tok) >= 4.5, cr_white(pg, tok))
        go = pg.evaluate("getComputedStyle(document.querySelector('#todayList .pend .pd-go')).backgroundColor")
        check(f'{scheme}: Today 검토하기 (.pd-go) uses it', go == want, go)
        open_thread(pg, '치과 예약'); pg.wait_for_timeout(600)
        cc = pg.evaluate("getComputedStyle(document.querySelector('.cc-actions .cc-primary')).backgroundColor")
        check(f'{scheme}: confirm button (.cc-primary) uses it', cc == want, cc)
        pg.goto(pg.url.split('#')[0] + '#/log'); pg.wait_for_timeout(900)
        wk = pg.evaluate("(() => { const e = document.querySelector('.wk-c.sel .wk-n'); return e && getComputedStyle(e).backgroundColor })()")
        check(f'{scheme}: selected week day (.wk-c.sel .wk-n) uses it', wk == want, wk)
        ok_txt = pg.evaluate("(() => { const e = document.querySelector('#logView .text-btn, .navbar .icon, .nav-back'); return e ? getComputedStyle(e).color : '' })()")
        check(f'{scheme}: nav text/icon accent stays --accent', ok_txt == acc, (ok_txt, acc)); ctx.close()
    check('no other background:var(--accent) left on solid buttons (.send, .primary and chips keep it; only the four above moved)', len(re.findall(r'--accent-fill', CSS)) >= 6)
    # ---- b) + menu closes on transitionend (or 200ms)
    reset(); rich(); ctx, pg = newpg(b, errs); goto_today(pg); open_thread(pg, '코드 리뷰'); pg.wait_for_timeout(500)
    btn = '#tPlus' if pg.locator('#tPlus').is_visible() else '#plusBtn'; menu = '#tMenu' if btn == '#tPlus' else '#plusMenu'
    check('source: no setTimeout(done, 160) any more; transitionend + 200ms fallback', 'setTimeout(done, 160)' not in APP and "addEventListener('transitionend', onEnd)" in APP and 'setTimeout(done, 200)' in APP)
    pg.click(btn); pg.wait_for_timeout(400)
    pg.evaluate(f"window.__t0 = performance.now(); window.__ev = 0; document.querySelector('{menu}').addEventListener('transitionend', () => window.__ev++)")
    pg.click(btn)
    for _ in range(100):   # polled with evaluate (wait_for_function evals a string; the mock may still carry a CSP flag from an earlier suite)
        if pg.evaluate(f"document.querySelector('{menu}').hidden"): break
        pg.wait_for_timeout(10)
    dt = pg.evaluate('performance.now() - window.__t0')
    check(f'closes: hidden when the 200ms transition has ended, not before ({dt:.0f}ms, 150–330)', 150 <= dt <= 330, dt)
    pg.click(btn); pg.wait_for_timeout(400); pg.click(btn); pg.wait_for_timeout(30); pg.click(btn); pg.wait_for_timeout(500)
    check('close then quick re-open: stays open (no late hide)', not pg.evaluate(f"document.querySelector('{menu}').hidden")); pg.keyboard.press('Escape'); ctx.close()
    # ---- c) chips fade token, f) nav easing, j) button transition
    ctx, pg = newpg(b, errs); goto_today(pg)
    check('c) .mchips.fresh uses var(--d-1) var(--ease-out)', '.mchips.fresh{animation:srcFade var(--d-1) var(--ease-out) both}' in CSS)
    f = pg.evaluate("(() => { const n = document.querySelector('#todayView .navbar'); const cs = getComputedStyle(n, '::before'); return [cs.transitionTimingFunction, cs.transitionDuration] })()")
    check('f) nav ::before opacity transition: --ease-out (not linear), 200ms', f[0].startswith('cubic-bezier') and 'linear' not in f[0] and f[1] == '0.2s', f)
    j = pg.evaluate("(() => { const b = document.createElement('button'); document.body.appendChild(b); const cs = getComputedStyle(b); const o = [cs.transitionProperty, cs.transitionDuration, cs.transitionTimingFunction]; b.remove(); return o })()")
    tf = re.findall(r'cubic-bezier\([^)]*\)|linear\([^)]*\)|\bease\b|\blinear\b', j[2])
    check('j) button: transform / background-color / opacity each with its own duration and an easing token (no default ease)', j[0] == 'transform, background-color, opacity' and j[1] == '0.2s, 0.12s, 0.2s' and 'ease' not in tf and len(tf) == 3, j)
    ctx.close()
    # ---- d) #messages label, e) icon, g) card in the body
    for scheme in ('dark', 'light'):
        reset(); rich(); seed_act(act(1, title='치과 예약', exp=60 * 24), title='치과 예약'); put('/pro/set', {})
        ctx, pg = newpg(b, errs, scheme=scheme); goto_today(pg); open_thread(pg, '치과 예약'); pg.wait_for_timeout(700)
        lab = pg.evaluate("[document.getElementById('messages').getAttribute('aria-label'), document.getElementById('title').textContent]")
        check(f'{scheme} d) #messages aria-label = thread title ({lab[0]!r})', lab[0] and lab[0] == lab[1] and lab[0] == '치과 예약', lab)
        g = pg.evaluate("""(() => { const c = document.querySelector('.confirm-card'), ev = c.closest('.ev'), st = c.closest('.cc-stack'), tx = ev && ev.querySelector(':scope > .tx'), act = ev && ev.querySelector(':scope > .actions');
          const r = e => e.getBoundingClientRect(); return { inEv: !!ev && st.parentElement === ev, gap: Math.round((r(st).top - r(tx).bottom) * 10) / 10, before: !!act && !!(st.compareDocumentPosition(act) & Node.DOCUMENT_POSITION_FOLLOWING), left: Math.round(r(c).left - r(tx).left), sibling: !!document.querySelector('#messages > .cc-stack'), rail: getComputedStyle(ev).backgroundImage.includes('linear-gradient') } })()""")
        check(f'{scheme} g) confirm card is inside the .ev body, 8px under the text, before the action row, same left edge, no sibling stack', g['inEv'] and abs(g['gap'] - 8) <= .6 and g['before'] and g['left'] == 0 and not g['sibling'], g)
        rl = pg.evaluate("""(() => { const st = document.querySelector('.cc-stack'), ev = st.closest('.ev'), r = e => e.getBoundingClientRect(); const x = r(ev).left + 51;
          const rails = e => [e, ...e.querySelectorAll('*')].filter(n => { const cs = getComputedStyle(n); return cs.backgroundImage.includes('gradient') && parseFloat(cs.backgroundSize.split(' ')[0]) <= 2 }).length;
          const c = document.querySelector('.confirm-card'); return { stackBg: getComputedStyle(st).backgroundImage, stackRails: rails(st), evRail: getComputedStyle(ev).backgroundImage.includes('gradient'), railX: Math.round(x), cardLeft: Math.round(r(c).left), stackLeft: Math.round(r(st).left) } })()""")
        check(f'{scheme} g-fix) no rail line over the confirm card: .cc-stack and its children draw no 1px gradient, the .ev rail (x={rl["railX"]}) is left of the card ({rl["cardLeft"]})', rl['stackBg'] == 'none' and rl['stackRails'] == 0 and rl['evRail'] and rl['railX'] < rl['stackLeft'] and rl['railX'] < rl['cardLeft'], rl)
        pg.screenshot(path=f'/tmp/fu_card_{scheme}.png')
        ctx.close()
    # e) one icon name
    reset(); rich(); brief_thread([ev('a', 9, 0)]); ctx, pg = newpg(b, errs); goto_today(pg)
    ic = pg.evaluate("[...new Set([...document.querySelectorAll('#todayList .ev.pro svg use')].map(u => u.getAttribute('href')))]")
    open_thread(pg, '아침 브리핑'); pg.wait_for_timeout(600)
    ic2 = pg.evaluate("[...new Set([...document.querySelectorAll('#messages .who-ic use, #messages .bc-head use, #messages .pim-card use')].map(u => u.getAttribute('href')))]")
    src = ''.join(open(f'{ROOT}/{f}').read() for f in ('proactive.js', 'pim.js', 'briefing.js', 'today.js', 'app.js'))
    check('e) one name: #i-sun-horizon everywhere, no #i-sun / icon("sun") / `sun:` key left', '#i-sun"' not in src and "icon('sun')" not in src and not re.search(r"\bsun:\s", src) and not [h for h in ic + ic2 if h in ('#i-sun',)] and '#i-sun-horizon' in ic + ic2, (ic, ic2))
    ctx.close()
    # ---- h) usage line on one line (light + dark, 320/375/390)
    for scheme in ('light', 'dark'):
        for w in (320, 375, 390):
            reset(); rich(); put('/b2/seed', dict(title='통계 대화', created=at(9, 0), updated=at(9, 1), messages=[dict(role='user', content='질문', created_at=at(9, 0)), dict(role='assistant', content='답변이에요.', created_at=at(9, 1), usage={'prompt_tokens': 12345, 'completion_tokens': 6789}, latency_ms=52000, model='x')]))
            ctx, pg = newpg(b, errs, scheme=scheme, w=w); goto_today(pg); open_thread(pg, '통계 대화'); pg.wait_for_timeout(500)
            u = pg.evaluate("(() => { const e = document.querySelector('#messages .usage'); if (!e) return null; const r = e.getBoundingClientRect(); return { h: Math.round(r.height), lh: parseFloat(getComputedStyle(e).lineHeight), over: document.scrollingElement.scrollWidth > innerWidth } })()")
            check(f'{scheme} {w}px h) stats line is one line, no overflow', u and u['h'] <= u['lh'] * 1.2 and not u['over'], u); ctx.close()
    # ---- i) snoozed items leave the strip count, the sheet and the direct jump
    reset(); rich(); memory(2)
    for n, t in enumerate(['치과 예약', '장보기', '운동 예약'], 1): seed_act(act(n, title=t, exp=60 * 24 * 3, created=isoz(-90 + n)), title=t)
    ctx, pg = newpg(b, errs); goto_today(pg)
    num = lambda: pg.evaluate("(() => { const c = document.querySelector('.stc[data-k=pend]'); return c ? c.querySelector('.sn').textContent : null })()")
    check('i) 3 pending → cell 3', num() == '3', num())
    pg.click('#todayList .pend .pd-later'); pg.wait_for_timeout(700)
    check('… "나중에" on the first one → cell 2', num() == '2', num())
    pg.locator('.stc[data-k=pend]').click(); pg.wait_for_timeout(600)
    tx = pg.evaluate("[document.getElementById('ssTitle').textContent, [...document.querySelectorAll('#ssList .ss-row')].map(r => r.innerText)]")
    check('… the sheet is "확인 대기 2건" and lists neither the snoozed one', tx[0] == '확인 대기 2건' and len(tx[1]) == 2 and not any('치과 예약' in r for r in tx[1]), tx)
    pg.keyboard.press('Escape'); pg.wait_for_timeout(450)
    pg.click('#todayList .pend .pd-later'); pg.wait_for_timeout(700)
    check('… snooze again → cell 1, a tap jumps straight to the last thread (no sheet)', num() == '1', num())
    pg.locator('.stc[data-k=pend]').click(); pg.wait_for_timeout(1300)
    check('… (direct jump)', rt(pg) == 'chat' and pg.locator('#stripSheet:not([hidden])').count() == 0, rt(pg)); ctx.close()
    # ---- k) briefing.enabled
    base = {'proactive': {'enabled': False, 'quiet_hours': {'start': '22:00', 'end': '08:00'}, 'memory_read': False}, 'memory': {'enabled': True}}
    for label, br, want in (('briefing.enabled=false', {'enabled': False, 'time': '07:30'}, False), ('briefing.enabled=true', {'enabled': True, 'time': '07:30'}, True), ('no briefing key (unknown)', None, True), ('briefing without a boolean enabled', {'time': '07:30'}, True)):
        reset(); rich(); memory(2); brief_thread([ev('a', 9, 0), ev('b', 23, 0)])
        s = dict(base); s.update({} if br is None else {'briefing': br}); put('/pro/set', {'settings': s, 'memItems': mem_items(2)})
        ctx, pg = newpg(b, errs); goto_today(pg); pg.wait_for_timeout(500)
        check(f'k) {label} → 오늘 일정 cell {"shown" if want else "hidden"}', ('sch' in keys(pg)) == want, keys(pg)); ctx.close()
    check('k) TODO for the architect is left in app.js', 'TODO(architect)' in APP and 'briefing.enabled' in APP)
    # ---- a2) .primary / .mem-intro-ok on --accent-fill, c2) .sources.fresh token, b2) reopen without a jump
    for scheme in ('dark', 'light'):
        ctx, pg = newpg(b, errs, scheme=scheme); goto_today(pg)
        o = pg.evaluate("""(() => { const out = {}; for (const c of ['primary', 'mem-intro-ok']) { const e = document.createElement('button'); e.className = c; document.body.appendChild(e); const cs = getComputedStyle(e); out[c] = [cs.backgroundColor, cs.color]; e.remove() } return out })()""")
        want = 'rgb(10, 111, 232)' if scheme == 'dark' else 'rgb(0, 113, 227)'
        for c in ('primary', 'mem-intro-ok'):
            cr = cr_white(pg, o[c][0])
            check(f'{scheme} a2) .{c}: white on --accent-fill = {cr}:1 (was {"3.7" if scheme == "dark" else "4.0"}:1) ≥ 4.5', o[c][0] == want and o[c][1] == 'rgb(255, 255, 255)' and cr >= 4.5, o[c])
        ctx.close()
    check('c2) .sources.fresh uses var(--d-1) var(--ease-out); no 120ms literal left in animations', '.sources.fresh{animation:srcFade var(--d-1) var(--ease-out) both}' in CSS and 'srcFade 120ms' not in CSS)
    reset(); rich(); ctx, pg = newpg(b, errs); goto_today(pg); open_thread(pg, '코드 리뷰'); pg.wait_for_timeout(500)
    btn = '#tPlus' if pg.locator('#tPlus').is_visible() else '#plusBtn'; menu = '#tMenu' if btn == '#tPlus' else '#plusMenu'
    pg.click(btn); pg.wait_for_timeout(400)
    r = pg.evaluate(f"""new Promise(res => {{ const m = document.querySelector('{menu}'), b = document.querySelector('{btn}'); b.click();
      requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(() => {{ const before = parseFloat(getComputedStyle(m).opacity); b.click(); requestAnimationFrame(() => {{ const after = parseFloat(getComputedStyle(m).opacity); requestAnimationFrame(() => res({{ before, after, shown: m.classList.contains('show'), hidden: m.hidden }})) }}) }})))
    }})""")
    check('b2) re-opening mid-close does not reset to opacity 0 (no one-frame jump)', r['shown'] and not r['hidden'] and r['after'] >= r['before'] - .02 and r['before'] < 1, r)
    pg.wait_for_timeout(500); check('b2) …and the menu stays open', not pg.evaluate(f"document.querySelector('{menu}').hidden")); ctx.close()
    check('no page errors', not errs, errs); b.close()
print(f'{sum(R)}/{len(R)} checks'); raise SystemExit(0 if all(R) else 1)
