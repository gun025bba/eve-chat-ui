# 1.10.0 release gate: every new surface stays OFF/hidden against a 5.0.1-like backend (no new fields, §14) — and with the feature flags off on a newer one.
#   A) 5.0.1-like: /v1/settings, /v1/actions, /v1/memory, /v1/briefing/* all 404 (mock supported=off), memory flag off AND on
#   B) newer server but nothing enabled: settings without memory/briefing/proactive keys, no actions, no briefing, no calendar/reminder tool events
# Asserted: Today works, 현황 띠 takes no space, no pim/briefing/confirm cards, no memory chips, plain chat streams, no error UI, no page errors.
from playwright.sync_api import sync_playwright
from b3_common import *
R = []; errs = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
CARDS = ".pim-card, .pim-brief, .confirm-card, .cc-stack, .mchips, .pim-cards, .bc-head"
def surfaces(pg): return pg.evaluate(f"""() => ({{ cards: document.querySelectorAll('{CARDS}').length,
  strip: (() => {{ const w = document.getElementById('todayStrip'); return !w || w.hidden || w.getBoundingClientRect().height === 0 }})(),
  cells: [...document.querySelectorAll('#todayStrip .stc')].map(c => c.dataset.k + ':' + c.querySelector('.sn').textContent), pend: document.querySelectorAll('#todayList .pend').length,
  toast: document.getElementById('toast') ? document.getElementById('toast').classList.contains('show') : false,
  err: document.querySelectorAll('.err, .error-banner, [role=alert]:not([hidden])').length }})""")
def run(label, mem_flag, prep, cells0=()):
    reset(); prep(); del errs[:]
    ctx = new_ctx(b)
    if mem_flag: ctx.add_init_script("localStorage.setItem('eve.flag.memory', '1')")
    pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    goto_today(pg, wait=2000)
    s = surfaces(pg)
    check(f'{label}: Today renders (route today), 현황 띠 hidden / no space, no cells, no pending card', rt(pg) == 'today' and (s['strip'] if not cells0 else not s['strip']) and s['cells'] == list(cells0) and s['pend'] == 0, (rt(pg), s))
    check(f'{label}: no toast / error banner on Today', not s['toast'] and s['err'] == 0, s)
    pg.evaluate("__app.newChat()"); pg.wait_for_timeout(500)
    pg.fill('#input', '안녕, 오늘 뭐 해?'); pg.click('#sendBtn'); pg.wait_for_timeout(2500)
    n = pg.evaluate("document.querySelectorAll('#messages .msg.assistant, #messages .ev .bubble').length")
    t = pg.evaluate("[...document.querySelectorAll('#messages .msg.assistant')].map(e => e.innerText).join('|').length")
    s = surfaces(pg)
    check(f'{label}: plain chat streams an answer ({t} chars)', n >= 1 and t > 0, (n, t))
    check(f'{label}: no calendar / briefing / confirm / memory-chip card is rendered', s['cards'] == 0, s)
    check(f'{label}: no toast / error banner after the answer', not s['toast'] and s['err'] == 0, s)
    pg.evaluate("location.hash = '#/'"); pg.wait_for_timeout(900)
    s = surfaces(pg)
    check(f'{label}: back on Today: same strip, no cards, a list of threads is there', s['cells'] == list(cells0) and s['cards'] == 0 and pg.evaluate("document.querySelectorAll('#todayList .msg, #todayList .ev, #todayList .row, #todayList li, #todayList a').length") > 0, s)
    st = pg.evaluate("document.getElementById('settingsView') ? 1 : 0")
    pg.evaluate("document.querySelector('#settingsBtn, [data-act=settings], #todaySettings') && document.querySelector('#settingsBtn, [data-act=settings], #todaySettings').click()"); pg.wait_for_timeout(700)
    check(f'{label}: settings opens, still no strip/cards, no page errors', not errs and surfaces(pg)['cards'] == 0, errs)
    ctx.close()
with sync_playwright() as p:
    b = p.chromium.launch()
    def a_501(): put('/pro/supported/off')
    def b_new():
        put('/pro/supported/on'); put('/pro/set', {'settings': {}, 'memItems': [], 'memNoKey': True})
    run('A 5.0.1-like (all new endpoints 404), memory flag off', False, a_501)
    run('A 5.0.1-like (all new endpoints 404), memory flag ON', True, a_501)
    run('B newer server, nothing enabled (no memory/briefing/proactive keys, empty /v1/actions: only a disabled 확인 대기 0)', False, b_new, ('pend:0',))
    run('B newer server, nothing enabled, memory flag ON (no 기억 cell: no memory.enabled)', True, b_new, ('pend:0',))
    # rich day (선톡 threads) but no briefing/calendar fields: nothing structured renders on the briefing thread
    reset(); rich(); put('/pro/set', {'settings': {}, 'memNoKey': True}); del errs[:]
    ctx = new_ctx(b); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); goto_today(pg, wait=2000)
    open_thread(pg, '아침 브리핑'); pg.wait_for_timeout(800)
    check('C briefing thread without briefing/pim fields: text only, no card, no error', surfaces(pg)['cards'] == 0 and pg.evaluate("document.querySelectorAll('#messages .bubble.tx, #messages .tx').length") >= 1 and not errs, (surfaces(pg), errs)); ctx.close()
    b.close()
print(f'{sum(R)}/{len(R)} checks'); raise SystemExit(0 if all(R) else 1)
