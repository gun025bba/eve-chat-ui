# 1.3.2: iOS standalone fixes — opaque headers without backdrop-filter, composer outside any <form> (iOS contact AutoFill)
import os, re, json
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
R = []
def check(name, ok, extra=''): R.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, extra)
d = os.path.join(os.path.dirname(__file__), '..')
html = open(os.path.join(d, 'index.html')).read(); man = json.load(open(os.path.join(d, 'manifest.webmanifest')))
css = open(os.path.join(d, 'styles.css')).read()
import re as _re
hdr = [m for m in _re.findall(r'([^{}]*)\{([^{}]*)\}', css) if _re.search(r'\.navbar|#topbar', m[0])]
check('no backdrop-filter on any header rule', not [m[0].strip() for m in hdr if 'backdrop-filter' in m[1] and 'none' not in m[1]], [m[0].strip() for m in hdr if 'backdrop-filter' in m[1]])
check('no !important header overrides left', not [m[0] for m in hdr if 'background' in m[1] and '!important' in m[1]])
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for touch in [False, True]:
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=touch, is_mobile=touch); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.add_init_script("localStorage.setItem('eve.mem.introSeen','1')")
        pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1200); pg.click('#newChat'); pg.wait_for_timeout(400)
        if not touch:
            check('version 1.4.0', pg.evaluate('__app.version') == '1.4.0')
            a = pg.evaluate("""(()=>{const i=document.getElementById('input');const txt=[i.placeholder,i.getAttribute('aria-label'),i.id,i.name||''].join(' ');
              return {form:!!i.form, inForm:!!i.closest('form'), forms:document.querySelectorAll('#chatView form').length, name:i.hasAttribute('name'), txt, btn:document.getElementById('sendBtn').type}})()""")
            check('composer textarea has no form owner / no <form> in chat view', not a['form'] and not a['inForm'] and a['forms'] == 0, a)
            check('textarea has no name attr', not a['name'], a)
            check('no contact words in placeholder/label/id', not re.search(r'name|이름|email|이메일|phone|전화|연락처|contact|address|주소|tel', a['txt'], re.I), a['txt'])
            check('send button is type=button', a['btn'] == 'button', a)
            hb = pg.evaluate("[...document.querySelectorAll('.navbar,#topbar')].map(n=>{const c=getComputedStyle(n);return [c.backgroundColor,c.backdropFilter||'none']})")
            check('headers opaque at rest', all(not bg.startswith('rgba') and bf == 'none' for bg, bf in hb), hb)
            pg.evaluate("document.querySelector('#listView .navbar')?.classList.add('collapsed')")
            hb2 = pg.evaluate("(()=>{const c=getComputedStyle(document.querySelector('#listView .navbar'));return [c.backgroundColor,c.backdropFilter||'none']})()")
            check('collapsed list navbar stays opaque, no blur', not hb2[0].startswith('rgba') and hb2[1] == 'none', hb2)
            ac = pg.evaluate("[document.getElementById('input').getAttribute('autocorrect'),document.getElementById('input').getAttribute('spellcheck')]")
            check('autocorrect/spellcheck kept for Korean prediction', ac == ['on', 'true'], ac)
            # IME: Enter while composing must not send (Korean)
            pg.fill('#input', '안녕')
            pg.evaluate("document.getElementById('input').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',isComposing:true,bubbles:true,cancelable:true}))"); pg.wait_for_timeout(500)
            check('Enter during IME composition does not send', pg.locator('.msg.user').count() == 0 and pg.input_value('#input') == '안녕')
            pg.press('#input', 'Enter'); pg.wait_for_timeout(2500)
            check('Enter sends Korean text (desktop)', pg.locator('.msg.user').count() == 1 and '안녕' in pg.inner_text('.msg.user') and pg.input_value('#input') == '')
        else:
            pg.fill('#input', '테스트 메시지'); pg.click('#sendBtn'); pg.wait_for_timeout(2500)
            check('touch: tapping send sends', pg.locator('.msg.user').count() == 1 and '테스트' in pg.inner_text('.msg.user'))
            pg.fill('#input', '두 줄'); pg.press('#input', 'Enter')
            check('touch: Enter inserts newline, no send', pg.locator('.msg.user').count() == 1)
        ctx.close()
    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
