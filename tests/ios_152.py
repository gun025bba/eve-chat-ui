# 1.5.2: status-bar-style default (no translucent system blur), theme-color = opaque header bg, no double safe-area padding
import os, re, json
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
R = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
d = os.path.join(os.path.dirname(__file__), '..')
html = open(os.path.join(d, 'index.html')).read()
css = re.sub(r'/\*[\s\S]*?\*/', '', open(os.path.join(d, 'styles.css')).read())
check('status-bar-style default', 'name="apple-mobile-web-app-status-bar-style" content="default"' in html and 'black-translucent' not in html)
tc = dict((m, c.lower()) for c, m in re.findall(r'<meta name="theme-color" content="(#[0-9a-fA-F]{6})" media="\(prefers-color-scheme: (dark|light)\)">', html))
hb = re.findall(r'--header-bg:(#[0-9A-Fa-f]{6})', css)
check('theme-color dark == dark --header-bg', tc.get('dark') == hb[0].lower(), (tc, hb))
check('theme-color light == light --header-bg', tc.get('light') == hb[1].lower(), (tc, hb))
man = json.load(open(os.path.join(d, 'manifest.webmanifest')))
check('manifest theme_color == dark header bg', man['theme_color'].lower() == hb[0].lower(), man['theme_color'])
dbl = re.findall(r'var\(--(?:nav-h|sat)[^;}]*\)[^;}]*env\(safe-area-inset-top\)', css)
check('no double top inset (--nav-h already includes it)', not dbl, dbl)
JS = """(()=>{const r=s=>{const n=document.querySelector(s);if(!n||n.offsetParent===null)return null;const c=getComputedStyle(n);return {pt:c.paddingTop,h:n.getBoundingClientRect().height,top:n.getBoundingClientRect().top,bg:c.backgroundColor}};
 return {top:r('#topbar'),nav:r('#listView .navbar')}})()"""
hexrgb = lambda h: 'rgb(%d, %d, %d)' % tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True, color_scheme=scheme); pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.add_init_script("localStorage.setItem('eve.mem.introSeen','1')")
        pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1200)
        v = pg.evaluate(JS); hdr = v['top'] or v['nav']
        check(f'{scheme}: header at top, no inset padding, 44px tall', hdr and hdr['top'] == 0 and hdr['pt'] == '0px' and abs(hdr['h'] - 44) < 1, v)
        check(f'{scheme}: header bg matches theme-color', hdr and hdr['bg'] == hexrgb(tc[scheme]), (hdr, tc[scheme]))
        check(f'{scheme}: no page errors', not errs, errs)
        ctx.close()
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
