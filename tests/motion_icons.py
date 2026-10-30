# 1.2.2 motion + icons (design a197571 REFRESH-SPEC P0)
import os, re
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
R = []
def check(name, ok, extra=''): R.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, extra)
D = os.path.join(os.path.dirname(__file__), '..')
css = open(os.path.join(D, 'styles.css')).read(); js = open(os.path.join(D, 'app.js')).read(); pjs = open(os.path.join(D, 'proactive.js')).read()
check('tokens 120/200/320/450 + ease-standard', all(t in css for t in ['--d-1:120ms', '--d-2:200ms', '--d-3:320ms', '--d-4:450ms', '--ease-standard:cubic-bezier(.32,.72,0,1)']))
check('no transition:all / shadow / radius / filter / height / grid-template transitions', not re.search(r'transition(-property)?:[^;}]*\b(all|box-shadow|border-radius|filter|height|grid-template-rows|top|left)\b', css))
check('ctx dim without blur', not re.search(r'#ctx\{[^}]*backdrop-filter', css))
check('no global svg rule; .i rule', not re.search(r'(^|[}\n])svg\{width', css) and '.i{width:22px' in css)
check('reduced motion: 200ms opacity (not .01ms)', '.01ms' not in css and 'transition-property:opacity!important' in css)
check('tail contain:content; keyboard via --kb translate', '.md .tail{contain:content}' in css and 'calc(-1 * var(--kb))' in css)
check('icon() helper replaces inline ICON/MI/proactive strings', "const icon = (n" in js and "icon('copy')" in js and "icon('sparkle')" in pjs and 'ICON = {' in js)
check('streaming scroll throttled 100ms', 'scrollBottomThrottled' in js and '100 - (performance.now() - sbLast)' in js)
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark').new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1500)
    check('version 2.0.0', pg.evaluate('__app.version') == '2.0.0')
    check('sprite inlined first in body', pg.evaluate("document.body.firstElementChild.id === 'eveSprite' && !!document.getElementById('i-settings')"))
    check('settings uses sliders icon', pg.evaluate("!!document.querySelector('#openSettings use[href=\"#i-settings\"]')"))
    w = pg.evaluate("Math.round(document.querySelector('#openSettings svg').getBoundingClientRect().width)")
    check('.i icons sized 22', w == 22, w)
    # M1: resize → only --kb during movement, --vvh committed after 150ms of quiet
    r = pg.evaluate("""async()=>{const s=document.documentElement.style;const v0=s.getPropertyValue('--vvh');
      dispatchEvent(new Event('resize')); await new Promise(r=>setTimeout(r,60)); const mid=s.getPropertyValue('--vvh');
      await new Promise(r=>setTimeout(r,250)); return [v0,mid,s.getPropertyValue('--vvh'),s.getPropertyValue('--kb')]}""")
    check('M1: --vvh unchanged mid-resize, committed after 150ms, --kb reset', r[0] == r[1] and r[3] == '0px', r)
    # M9: rendered thread has no .enter; new message gets .enter only on the last
    pg.evaluate("__app.newChat()"); pg.wait_for_timeout(400); pg.fill('#input', 'hello'); pg.click('#sendBtn'); pg.wait_for_timeout(2500)
    n = pg.evaluate("[document.querySelectorAll('#messages .msg.enter').length, [...document.querySelectorAll('#messages .msg')].pop().classList.contains('enter')]")
    check('M9: enter class only on the newly appended last message', n == [1, True], n)
    pg.reload(); pg.wait_for_timeout(1500)
    check('M9: no enter animation on thread render', pg.evaluate("document.querySelectorAll('#messages .msg.enter').length") == 0)
    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
