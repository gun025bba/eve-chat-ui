from version_common import VERSION, versioned
# 1.4.0 P1 visual refresh (design a1975717 REFRESH-SPEC §1)
import os, re
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
R = []
def check(name, ok, extra=''): R.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, extra)
css = open(os.path.join(os.path.dirname(__file__), '..', 'styles.css')).read()
check('no transition on layout/paint props (box-shadow, filter, radius, height…)', not re.search(r'transition:[^;}]*\b(box-shadow|filter|backdrop-filter|border-radius|height|width|padding|margin)\b', css))
check('no transition:all', not re.search(r'transition:\s*all', css))
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, color_scheme=scheme); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.add_init_script("localStorage.setItem('eve.mem.introSeen','1');localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit'}))")
        pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1200); pg.evaluate("__app.newChat()"); pg.wait_for_timeout(800)
        if scheme == 'dark':
            check(versioned('version __EVE_VERSION__'), pg.evaluate('__app.version') == VERSION)
            t = pg.evaluate("""(()=>{const r=getComputedStyle(document.documentElement),g=n=>r.getPropertyValue(n).trim();
              return [g('--r-xs'),g('--r-sm'),g('--r-md'),g('--r-lg'),g('--r-xl'),g('--layer-1'),g('--layer-2'),g('--hair'),g('--hair-strong'),g('--s1'),g('--s2')]})()""")
            check('radii 6/10/16/20/26 + two layers + hairlines + 4/8 spacing', t[:5] == ['6px','10px','16px','20px','26px'] and t[5].upper() == '#1C1C1E' and t[6].upper() == '#2C2C2E' and t[7] and t[8] and t[9:] == ['4px','8px'], t)
        nav = pg.evaluate("document.getElementById('modelName').textContent")   # 1.10.0 B1: the empty screen (tile / headline / chips) is gone — see b1_empty.py
        css = open(__import__('os').path.join(__import__('os').path.dirname(__file__), '..', 'styles.css')).read()
        check(f'[{scheme}] mig track/ring use var(--d-3), no 300ms', 'stroke-dashoffset var(--d-3)' in css and '.mig-track i{display:block;height:100%;width:100%;transform:scaleX(0);transform-origin:left;background:var(--accent);transition:transform var(--d-3)' in css)
        check(f'[{scheme}] no model name in nav subtitle or empty state (B2: "로컬 · 비공개" moved to the top of settings)', nav == '' and '로컬 · 비공개' in pg.text_content('#sPriv') and 'Qwen' not in pg.inner_text('#chatView'), nav)
        c = pg.evaluate("""(()=>{const f=document.querySelector('#composer .field'),i=document.getElementById('input'),s=document.getElementById('sendBtn');i.focus();
          const fc=getComputedStyle(f),ic=getComputedStyle(i),a=getComputedStyle(f,'::after');
          return {radius:fc.borderTopLeftRadius,shadow:fc.boxShadow,outline:ic.outlineStyle,ring:a.boxShadow,send:getComputedStyle(s,'::after').opacity,dis:s.disabled,sw:s.getBoundingClientRect().width,hit:s.getBoundingClientRect().width-2*parseFloat(getComputedStyle(s,'::before').left)}})()""")
        check(f'[{scheme}] floating capsule composer r22 (B1 one-line) + hairline + float shadow', c['radius'] == '22px' and 'inset' in c['shadow'] and '24px' in c['shadow'], c)
        check(f'[{scheme}] no focus ring (no outline, no blue ring)', c['outline'] == 'none' and '10, 132, 255' not in c['ring'] and '0, 122, 255' not in c['ring'], c)
        check(f'[{scheme}] send not blue when empty', c['dis'] and c['send'] == '0', c)
        check(f'[{scheme}] send 36px with >=44pt hit area', c['sw'] == 36 and c['hit'] >= 44, c)
        pg.fill('#input', '안녕하세요'); pg.wait_for_timeout(300)
        s2 = pg.evaluate("(()=>{const s=document.getElementById('sendBtn');return [s.disabled,getComputedStyle(s,'::after').opacity,getComputedStyle(s,'::after').backgroundColor]})()")
        check(f'[{scheme}] send blue only with input', s2[0] is False and s2[1] == '1' and s2[2] in ('rgb(10, 132, 255)', 'rgb(0, 122, 255)'), s2)
        pg.click('#sendBtn'); pg.wait_for_timeout(3000)
        m = pg.evaluate("""(()=>{const a=getComputedStyle(document.querySelector('.msg.assistant .bubble')),u=getComputedStyle(document.querySelector('.msg.user .bubble'));
          return {af:a.fontSize,al:a.lineHeight,uf:u.fontSize,ul:u.lineHeight,ur:[u.borderTopLeftRadius,u.borderBottomRightRadius],ubg:u.backgroundColor}})()""")
        check(f'[{scheme}] answers 16/24, user text 16/24 plain (B1 timeline: no bubble)', m['af'] == '16px' and m['al'] == '24px' and m['uf'] == '16px' and m['ul'] == '24px' and m['ur'] == ['0px', '0px'], m)
        hd = pg.evaluate("[...document.querySelectorAll('.navbar,#topbar')].map(n=>getComputedStyle(n).backdropFilter||'none')")
        check(f'[{scheme}] headers keep 1.3.2 (no backdrop-filter)', all(x == 'none' for x in hd), hd)
        tt = pg.evaluate("[...document.querySelectorAll('#chatView .navbar button,#chatView .navbar .icon')].filter(e=>e.offsetParent).map(e=>{const r=e.getBoundingClientRect(),b=getComputedStyle(e,'::before');const ex=b.content!=='none'&&b.position==='absolute'?-2*parseFloat(b.left||0):0;return [e.id||e.className,Math.round(r.width+ex),Math.round(r.height+ex)]})")
        check(f'[{scheme}] tap targets >= 44', all(w >= 44 and h >= 44 for _, w, h in tt), tt)
        if scheme == 'dark':
            pg.evaluate("document.querySelector('#openSettings,#settingsBtn')?.click()"); pg.wait_for_timeout(800)
            check('model name lives in Settings > 정보', 'Qwen3-30B-A3B-4bit' in (pg.text_content('#sModelInfo') or ''), pg.text_content('#sModelInfo'))
        ctx.close()
    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
