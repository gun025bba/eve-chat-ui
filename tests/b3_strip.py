# 1.10.0 B3 현황 띠 (DIRECTION-B-SPEC §5): cells, visibility rules (§14: no field → hide only that cell, silently), values/aria, loading, errors, refresh, nav subtitle
import re, time
from playwright.sync_api import sync_playwright
from b3_common import *
R = []; errs = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
def run(b, setup, scheme='dark', wait=1800, w=390, **kw):
    reset(); setup(); ctx, pg = newpg(b, errs, scheme=scheme, w=w, **kw); goto_today(pg, wait=wait); return ctx, pg
def full():
    rich(); memory(12); seed_act(act(1, title='치과 예약 · 내일 10시'), act(2, title='장보기 알림', verb='remind'))
    brief_thread([ev('팀 스탠드업', 0, 5, 20, '회사'), ev('저녁 약속', 23, 0, 30), ev('늦은 통화', 23, 40, 15, '개인')])
pro = lambda: put('/__pro')

with sync_playwright() as p:
    b = p.chromium.launch()
    # ---- 1) all three cells
    ctx, pg = run(b, full); S = strip(pg)
    check('3 cells in the order 기억 · 확인 대기 · 오늘 일정, --n=3', [c['k'] for c in S['cells']] == ['mem', 'pend', 'sch'] and S['n'] == '3', S)
    check('values 12 / 2 / 2 (the 00:05 stand-up is over, two left tonight)', [c['n'] for c in S['cells']] == ['12', '2', '2'], S)
    check('labels', [c['label'] for c in S['cells']] == ['기억', '확인 대기', '오늘 일정'], S)
    check('aria-labels per spec', [c['aria'] for c in S['cells']] == ['기억 12개', '확인 대기 2건', '오늘 일정 2개, 오늘 아침 기준'], S)
    g = pg.evaluate("""() => { const w = document.getElementById('todayStrip'), s = w.firstElementChild, d = document.getElementById('todayDate').getBoundingClientRect(), l = document.getElementById('todayList').getBoundingClientRect(), r = s.getBoundingClientRect(), cs = getComputedStyle(s);
      return { dTop: d.bottom, sTop: r.top, sBot: r.bottom, lTop: l.top, h: r.height, rad: cs.borderTopLeftRadius, disp: cs.display, cols: cs.gridTemplateColumns, kids: [...s.children].map(c => [c.tagName, c.getBoundingClientRect().height, c.getBoundingClientRect().width]), left: r.left, right: innerWidth - r.right } }""")
    check('strip sits between the date and the timeline', g['dTop'] <= g['sTop'] <= g['sBot'] <= g['lTop'], g)
    check('grid of 3 equal columns, radius 16, cells are <button> ≥44 tall (≈63)', g['disp'] == 'grid' and g['rad'] == '16px' and len(set(round(float(x[:-2])) for x in g['cols'].split())) == 1 and all(k[0] == 'BUTTON' and k[1] >= 44 and 60 <= k[1] <= 66 for k in g['kids']), g)
    check('16px side margin at 390 (same column as the timeline)', abs(g['left'] - 16) < 1 and abs(g['right'] - 16) < 1, g)
    t = pg.evaluate("""() => { const c = document.querySelector('.stc'), n = c.querySelector('.sn'), l = c.querySelector('.sl'), cs = getComputedStyle(n), ls = getComputedStyle(l.querySelector('span'));
      return { fs: cs.fontSize, lh: cs.lineHeight, fw: cs.fontWeight, ls: cs.letterSpacing, lfs: ls.fontSize, lfw: ls.fontWeight, llh: ls.lineHeight, pad: getComputedStyle(c).padding, icon: l.querySelector('svg').getBoundingClientRect().width } }""")
    check('type: number 22/26 600 −0.3px · label 12/16 500 · icon 13 · padding 10 14 11', t['fs'] == '22px' and t['lh'] == '26px' and t['fw'] == '600' and t['ls'] == '-0.3px' and t['lfs'] == '12px' and t['llh'] == '16px' and t['lfw'] == '500' and t['icon'] == 13 and t['pad'] == '10px 14px 11px', t)
    ic = pg.evaluate("[...document.querySelectorAll('.stc')].map(c => { const s = c.querySelector('svg'); return s ? s.querySelector('use').getAttribute('href') : null })")
    check('icons: memory, bell, none on the schedule cell', ic == ['#i-memory', '#i-bell', None], ic)
    sub = pg.evaluate("[document.getElementById('todayNavSub').textContent, document.getElementById('todayNavSub').hidden]")
    check('nav subtitle "기억 12 · 대기 2"', sub == ['기억 12 · 대기 2', False], sub)
    tr = pg.evaluate("""() => { const c = document.querySelector('.stc'), a = getComputedStyle(c, '::after'); return [getComputedStyle(c).transitionProperty, a.transitionProperty, a.transitionDuration, a.backgroundColor !== 'rgba(0, 0, 0, 0)', getComputedStyle(c, '::after').opacity] }""")
    check('press = a --fill layer fading by opacity at --d-1 (120ms), no scale on the cell', tr[1] == 'opacity' and tr[2] == '0.12s' and tr[0] in ('none', 'all') and tr[4] == '0', tr)
    pg.evaluate("document.querySelector('.stc').dispatchEvent(new PointerEvent('pointerdown'))")
    check('no scale transform on :active', pg.evaluate("(() => { const s = document.createElement('style'); return getComputedStyle(document.querySelector('.stc')).transform })()") == 'none')
    check('no page errors', not errs, errs)
    ctx.close()

    # ---- 2) the schedule cell hides itself (and only itself) when its data is missing/unusable
    def sch_case(name, f):
        def setup(): rich(); memory(5); seed_act(act(1, title='A')); f()
        ctx, pg = run(b, setup); S = strip(pg)
        check(f'schedule hidden: {name} → 2 cells, --n=2', [c['k'] for c in S['cells']] == ['mem', 'pend'] and S['n'] == '2' and not S['hidden'], S); ctx.close()
    sch_case('no briefing today', lambda: None)
    sch_case('briefing is from yesterday', lambda: brief_thread([ev('어제 일정', 9, 0)], date=day_ymd(-1)))
    sch_case('events section status=error', lambda: brief_thread([], count=0, status='error'))
    sch_case('events count 0', lambda: brief_thread([], count=0))
    sch_case('briefing has no events section (reminders only)', lambda: brief_thread([], sections=[{'kind': 'reminders', 'status': 'ok', 'count': 1, 'truncated': False, 'items': [{'title': '세금', 'due': day_ymd() + 'T09:00:00+09:00', 'list': '할 일', 'overdue': False}]}]))
    sch_case('briefing schema from the future (content only)', lambda: brief_thread([ev('x', 9, 0)], extra={'schema': 2}))
    def nobrief_kind():
        put('/b2/seed', dict(title='가격 알림', created=at(9, 0), updated=at(9, 0), messages=[dict(pro_msg('가격', 9, 0, job='가격 알림', tkind='watch'), briefing={'schema': 1, 'status': 'ok', 'date': day_ymd(), 'sections': [{'kind': 'events', 'status': 'ok', 'count': 1, 'truncated': False, 'items': [ev('x', 23, 0)]}]})]))
    sch_case('template_kind is not "briefing"', nobrief_kind)
    # latest of several briefing messages wins
    def two():
        brief_thread([ev('이른 일정', 23, 0)], h=6, m=0); brief_thread([ev('a', 23, 0), ev('b', 23, 10), ev('c', 23, 20)], h=7, m=42)
    ctx, pg = run(b, lambda: (rich(), memory(2), seed_act(), two())); check('latest briefing of the day is the one counted (3, not 1)', strip(pg)['cells'][-1]['n'] == '3', strip(pg)); ctx.close()

    # ---- 3) schedule numbers: N+, all past → 0 disabled, all-day never past
    ctx, pg = run(b, lambda: (rich(), memory(1), seed_act(), brief_thread([ev('a', 23, 0), ev('b', 23, 10)], count=14, truncated=True))); c = strip(pg)['cells'][-1]
    check('truncated → "N+" (2 listed + 12 more = 14+)', c['n'] == '14+' and not c['dis'], c); ctx.close()
    ctx, pg = run(b, lambda: (rich(), memory(1), seed_act(), brief_thread([ev('a', 0, 1, 5), ev('b', 0, 10, 5)]))); c = strip(pg)['cells'][-1]
    check('all events over → "0", aria-disabled (not hidden)', c['n'] == '0' and c['dis'] and c['aria'].startswith('오늘 일정 0개'), c)
    pg.locator('.stc[data-k=sch]').click(force=True); pg.wait_for_timeout(500); check('tapping the disabled 0 cell opens nothing', pg.locator('#stripSheet:not([hidden])').count() == 0)
    check('0 → number in --sub', pg.evaluate("(() => { const p = document.createElement('i'); p.style.color = 'var(--sub)'; document.body.appendChild(p); const a = getComputedStyle(p).color, b = getComputedStyle(document.querySelector('.stc[data-k=sch] .sn')).color; p.remove(); return a === b })()"))
    ctx.close()
    ctx, pg = run(b, lambda: (rich(), memory(1), seed_act(), brief_thread([ev('종일 행사', 0, 0, 60, '회사', all_day=True), ev('a', 0, 1, 5)]))); c = strip(pg)['cells'][-1]
    check('all-day events are never "over"', c['n'] == '1', c); ctx.close()

    # ---- 4) memory cell visibility = system.memory_available AND memory.enabled (and nothing else)
    def mem_case(name, **kw):
        ctx, pg = run(b, lambda: (rich(), memory(4, **kw), seed_act(act(1, title='A')))); S = strip(pg)
        check(f'memory hidden: {name}', [c['k'] for c in S['cells']] == ['pend'] and S['n'] == '1' and not S['hidden'], S)
        check(f'  … and no error UI / no toast ({name})', pg.locator('#todayList .t-err').count() == 0 and pg.locator('#toast.show').count() == 0 and not errs, errs); ctx.close()
    mem_case('memory.enabled=false', enabled=False)
    mem_case('kill switch (memory_available=false)', mode='availOff')
    mem_case('server memory off (404 {"detail":"Not Found"})', mode='off')
    mem_case('settings without a memory key', nokey=True)
    ctx, pg = run(b, lambda: (rich(), memory(4), seed_act(act(1, title='A')))); check('(control) the same state with memory on shows 4', strip(pg)['cells'][0]['n'] == '4'); ctx.close()
    reset(); rich(); memory(4); seed_act(act(1, title='A'))
    ctx = new_ctx(b); ctx.add_init_script("localStorage.removeItem('eve.flag.memory')"); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); n0 = len(pro()['bodies']); goto_today(pg)
    check('memory feature flag off → no cell and no /v1/memory request', keys(pg) == ['pend'] and not [x for x in pro()['bodies'][n0:] if x['p'].startswith('/v1/memory')], keys(pg)); ctx.close()
    # memory 0: shown, --sub, tappable
    ctx, pg = run(b, lambda: (rich(), memory(0), seed_act(act(1, title='A')))); c = strip(pg)['cells'][0]
    check('memory 0 → "0" shown and still tappable', c['n'] == '0' and not c['dis'] and c['aria'] == '기억 0개', c)
    pg.locator('.stc[data-k=mem]').click(); pg.wait_for_timeout(1500)
    check('… tap opens the settings sheet straight at #memoryView (empty state)', pg.evaluate("document.getElementById('settings').open") and pg.is_visible('#memoryView') and '아직 기억한 게 없어요' in pg.text_content('#memState'), pg.evaluate("document.getElementById('settings').open")); ctx.close()

    # ---- 5) pending: always shown (0 → disabled), "–" on error, hidden only when there is no endpoint
    ctx, pg = run(b, lambda: (rich(), memory(3))); c = strip(pg)['cells'][1]
    check('0 pending → "0", aria-disabled, label unchanged, bell icon kept', c['n'] == '0' and c['dis'] and c['aria'] == '확인 대기 0건', c)
    check('0 pending: bell is --sub (not --pend)', pg.evaluate("getComputedStyle(document.querySelector('.stc[data-k=pend] .sl svg')).color") == pg.evaluate("getComputedStyle(document.querySelector('.stc[data-k=pend] .sl span')).color"))
    pg.locator('.stc[data-k=pend]').click(force=True); pg.wait_for_timeout(500); check('tapping 0 pending does nothing', rt(pg) == 'today' and pg.locator('#stripSheet:not([hidden])').count() == 0); ctx.close()
    def pend_err(): rich(); memory(3); seed_act(act(1, title='A')); put('/pro/set', {'actFail': 503})
    ctx, pg = run(b, pend_err); S = strip(pg); c = S['cells'][1]
    check('GET /v1/actions 503 → "–", disabled, no toast', c['n'] == '–' and c['dis'] and S['cells'][0]['n'] == '3' and pg.locator('#toast.show').count() == 0, S)
    check('error aria says it failed', '불러오지 못' in c['aria'], c)
    ctx.close()
    def mem_err(): rich(); memory(3); seed_act(act(1, title='A')); put('/pro/set', {'memListFail': 503})
    ctx, pg = run(b, mem_err); S = strip(pg); c = S['cells'][0]
    check('GET /v1/memory 503 (memory is on) → "–", disabled, no toast', c['n'] == '–' and c['dis'] and S['cells'][1]['n'] == '1' and pg.locator('#toast.show').count() == 0, S)
    check('error state: the strip is still tappable elsewhere', not S['cells'][1]['dis']); ctx.close()
    def mem_drop(): rich(); memory(3); seed_act(act(1, title='A')); put('/pro/set', {'memMode': 'drop'})
    ctx, pg = run(b, mem_drop); check('memory routes dropping the connection → settings read ok, list fails → "–"', strip(pg)['cells'][0]['n'] == '–', strip(pg)); ctx.close()
    def nopend(): rich(); memory(3); seed_act(act(1, title='A')); put('/pro/supported/off')
    ctx, pg = run(b, nopend); check('GET /v1/actions 404 (no endpoint) → pending cell not drawn, no error UI', 'pend' not in keys(pg) and pg.locator('#todayList .t-err').count() == 0, strip(pg)); ctx.close()
    def nothing(): rich(); memory(3, enabled=False); put('/pro/supported/off')
    ctx, pg = run(b, nothing); S = strip(pg)
    check('no cell has a data source → the strip is not drawn and takes no space', S['hidden'] and pg.evaluate("document.getElementById('todayStrip').getBoundingClientRect().height") == 0 and pg.evaluate("document.getElementById('todayNavSub').hidden"), S)
    check('… Today is otherwise fine', pg.locator('#todayList .ev').count() >= 3 and pg.locator('#todayList .t-err').count() == 0); ctx.close()

    # ---- 6) loading: skeleton in the number slot after 250ms when there is no cache; cells not tappable until loaded
    def slow(): rich(); memory(7); seed_act(act(1, title='A'), act(2, title='B')); put('/pro/set', {'actDelay': 1500, 'memDelay': 1500})
    reset(); slow(); ctx, pg = newpg(b, errs); pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(900)
    sk = pg.evaluate("[...document.querySelectorAll('.stc')].map(c => [c.dataset.k, !!c.querySelector('.sk'), c.getAttribute('aria-disabled')])")
    check('while loading (no cache, >250ms): skeleton bars, cells disabled', sk == [['mem', True, 'true'], ['pend', True, 'true']], sk)
    pg.wait_for_timeout(2200); S = strip(pg)
    check('then the real numbers replace them', [c['n'] for c in S['cells']] == ['7', '2'] and not pg.locator('.stc .sk').count(), S); ctx.close()
    put('/pro/set', {'actDelay': 0, 'memDelay': 0})

    # ---- 7) refresh: visibilitychange, 60s foreground poll (pending only), Today re-entry (memory/schedule), cache while offline
    reset(); rich(); memory(5); seed_act(act(1, title='A')); ctx, pg = newpg(b, errs); goto_today(pg); S = strip(pg)
    check('start: 5 / 1', [c['n'] for c in S['cells']] == ['5', '1'], S)
    put('/pro/set', {'memItems': mem_items(6)}); n0 = len(pro()['bodies'])
    pg.wait_for_timeout(300); mems = lambda: len([x for x in pro()['bodies'][n0:] if x['p'] == '/v1/memory' and x['m'] == 'GET']); acts = lambda: len([x for x in pro()['bodies'][n0:] if x['p'] == '/v1/actions'])
    refresh(pg); check('visibilitychange → visible refetches both', mems() >= 1 and acts() >= 1 and strip(pg)['cells'][0]['n'] == '6', (mems(), acts()))
    put('/pro/seed', dict(title='t2', user=['x'], proactive=['y'], restore=[act(5, title='새 요청')])); n1 = len(pro()['bodies']); m1 = mems()
    pg.wait_for_timeout(62000)
    check('60s foreground poll updates 확인 대기 (1 → 2) without touching memory', strip(pg)['cells'][1]['n'] == '2' and mems() == m1, (strip(pg), mems(), m1))
    chg = pg.evaluate("[...document.querySelectorAll('.stc .sn')].map(n => [n.classList.contains('chg'), getComputedStyle(n).animationName, getComputedStyle(n).animationDuration])")
    check('a changed number cross-fades by opacity at --d-1 (120ms); unchanged ones do not animate', chg[1] == [True, 'stripIn', '0.12s'] and chg[0][0] is False, chg)
    ctx.set_offline(True); pg.evaluate("window.dispatchEvent(new Event('offline'))"); refresh(pg); pg.wait_for_timeout(500)
    check('offline: the last values stay (cache), nothing turns into "–"', [c['n'] for c in strip(pg)['cells']] == ['6', '2'], strip(pg))
    ctx.set_offline(False); ctx.close()

    # ---- 8) reduced motion + strip fade + forbidden CSS
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, reduced_motion='reduce'); ctx.add_init_script(SETTINGS); pg = ctx.new_page(); reset(); full(); goto_today(pg)
    rm = pg.evaluate("[getComputedStyle(document.querySelector('.strip')).animationDuration, getComputedStyle(document.querySelector('.strip')).animationName]")
    check('reduced motion: the strip appears with a plain opacity fade (--d-2), nothing else moves', rm[1] in ('stripIn', 'none') and rm[0] in ('0.2s', '0s'), rm); ctx.close()
    css = open('../styles.css').read(); i = css.index('1.10.0 B3 현황 띠'); blk = css[i:]
    check('B3 CSS: no backdrop-filter / blur / transition:all', not re.search(r'backdrop-filter|blur\(|transition:\s*all', blk))
    js = open('../today.js').read() + open('../app.js').read()
    check('no hostname or IP literal introduced in the strip code', not re.search(r'https?://(?!www\.w3\.org)[a-z0-9.-]+\.[a-z]{2,}|\b\d{1,3}(\.\d{1,3}){3}\b', open('../today.js').read()))
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
