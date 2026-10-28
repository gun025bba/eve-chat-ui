# 1.10.0 B3 현황 띠: no horizontal scroll at 320 / 375 / 390 with the strip (3 cells, long numbers, "N+"), the nav subtitle and both sheets (long titles / calendars) — dark + light
import json
from playwright.sync_api import sync_playwright
from b3_common import *
R = []; errs = []; ROWS = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
LONGT = '아주아주아주 긴 일정 제목입니다 ' * 4 + 'https://example.com/' + 'a' * 90
def setup():
    reset(); rich(); memory(1234)
    seed_act(act(1, title=LONGT, exp=60 * 24 * 3, created=isoz(-90)), title='긴 확인 ' + LONGT)
    seed_act(act(2, title='장보기 알림 ' * 12, verb='remind', exp=5, created=isoz(-30)), title='장보기')
    items = [ev(LONGT + str(i), 8 + i, 0, cal='아주아주 긴 캘린더 이름 ' * 4) for i in range(5)] + [ev('종일 일정', 0, 0, all_day=True)]
    brief_thread(items, count=140, truncated=True)
JS = """() => { const s = document.scrollingElement; let worst = 0, who = '';
  for (const e of document.querySelectorAll('#todayView *, #stripSheet *')) { const r = e.getBoundingClientRect(); if (r.width && r.right > innerWidth + .5 && r.right - innerWidth > worst) { worst = r.right - innerWidth; who = (e.id || e.className || e.tagName) + '' } }
  const st = document.querySelector('.strip'), cells = [...document.querySelectorAll('.stc')].map(c => { const r = c.getBoundingClientRect(), l = c.querySelector('.sl span'), n = c.querySelector('.sn'); return { k: c.dataset.k, w: Math.round(r.width), lbl: l.scrollWidth <= l.clientWidth + .5, num: n.scrollWidth <= n.clientWidth + .5, h: Math.round(r.height) } });
  return { sw: s.scrollWidth, cw: s.clientWidth, worst, who, cells, stripW: st ? Math.round(st.getBoundingClientRect().width) : 0 } }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        for w in (320, 375, 390):
            setup(); ctx, pg = newpg(b, errs, scheme=scheme, w=w, h=800); goto_today(pg); pg.wait_for_timeout(500)
            m = pg.evaluate(JS)
            ok = m['sw'] <= m['cw'] and m['worst'] <= .5
            check(f'{scheme} {w}px Today + strip: scrollWidth {m["sw"]} ≤ clientWidth {m["cw"]}', ok, m); ROWS.append(['Today + strip', scheme, w, m['sw'], m['cw'], 'OK' if ok else 'OVERFLOW'])
            check(f'{scheme} {w}px: 3 cells, label + number fit without ellipsis ({[c["w"] for c in m["cells"]]}px wide)', len(m['cells']) == 3 and all(c['lbl'] and c['num'] for c in m['cells']) and all(c['w'] >= 90 for c in m['cells']), m['cells'])
            check(f'{scheme} {w}px: nav subtitle is one line inside the bar', pg.evaluate("(() => { const s = document.getElementById('todayNavSub'); if (s.hidden) return 'hidden'; const r = s.getBoundingClientRect(); return r.height < 20 && r.right <= innerWidth && r.left >= 0 })()") is True)
            for key, name in (('pend', '확인 대기 sheet'), ('sch', '오늘 일정 sheet')):
                pg.locator(f'.stc[data-k={key}]').click(); pg.wait_for_timeout(600)
                m = pg.evaluate(JS); sh = pg.evaluate("(() => { const e = document.getElementById('stripSheet'), r = e.getBoundingClientRect(); return { open: !e.hidden, l: r.left, r: r.right, rowsOk: [...e.querySelectorAll('.ss-row')].every(x => x.getBoundingClientRect().right <= innerWidth + .5 && x.scrollWidth <= x.clientWidth + .5) } })()")
                ok = m['sw'] <= m['cw'] and m['worst'] <= .5 and sh['open'] and sh['rowsOk'] and sh['l'] >= -.5 and sh['r'] <= w + .5
                check(f'{scheme} {w}px {name}: no horizontal overflow, rows inside the sheet', ok, (m, sh)); ROWS.append([name, scheme, w, m['sw'], m['cw'], 'OK' if ok else 'OVERFLOW'])
                pg.keyboard.press('Escape'); pg.wait_for_timeout(450)
            ctx.close()
    check('no page errors', not errs, errs); b.close()
print('| screen | scheme | width | scrollWidth | clientWidth | result |\n|---|---|---|---|---|---|')
for r in ROWS: print('| ' + ' | '.join(map(str, r)) + ' |')
json.dump(ROWS, open('/tmp/b3_overflow_rows.json', 'w')); print(f'{sum(R)}/{len(R)} checks'); raise SystemExit(0 if all(R) else 1)
