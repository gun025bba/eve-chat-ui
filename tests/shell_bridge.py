# 1.7.0: iOS shell bridge v1 (eve-serving #64 ios-shell.md §3, eve-ios #1) + QuickType mitigation on the composer
import os, re, json, urllib.request
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
R = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
def put(path): return urllib.request.urlopen(urllib.request.Request(B + path, method='PUT')).read()
def state(): return json.loads(urllib.request.urlopen(B + '/__db').read())['state']
d = os.path.join(os.path.dirname(__file__), '..')
html = open(os.path.join(d, 'index.html')).read(); css = open(os.path.join(d, 'styles.css')).read()
check('viewport-fit=cover', 'viewport-fit=cover' in re.search(r'<meta name="viewport"[^>]*>', html).group(0))
check('safe-area env() used for all four edges', all(f'env(safe-area-inset-{e})' in css for e in ['top', 'right', 'bottom', 'left']))
check('shell.js loaded before app.js', html.index('/ui/shell.js') < html.index('/ui/app.js'))
FAKE = """window.__sent=[];window.__vib=0;navigator.vibrate=()=>{window.__vib++;return true};
window.webkit={messageHandlers:{eve:{postMessage(m){window.__sent.push(JSON.parse(JSON.stringify(m)))}}}};
localStorage.setItem('eve.mem.introSeen','1')"""
errs = []
put('/auth/on'); put('/deny/off')
with sync_playwright() as p:
    b = p.chromium.launch()
    def page(fake=True):
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.add_init_script(FAKE if fake else "localStorage.setItem('eve.mem.introSeen','1')"); pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1200); return ctx, pg
    sent = lambda pg, t=None: [m for m in pg.evaluate('window.__sent') if t is None or m.get('type') == t]
    recv = lambda pg, m: pg.evaluate('m => window.__eveShell.receive(m)', m)
    # plain browser
    ctx, pg = page(False)
    s = pg.evaluate('__app.shell()')
    check('no bridge → plain PWA (present=false, active=false)', s['present'] is False and s['active'] is False, s)
    check('no bridge → haptic() is a no-op', pg.evaluate("EveShell.haptic('light')") is False)
    i = pg.evaluate("(()=>{const i=document.getElementById('input');return [i.getAttribute('autocorrect'),i.getAttribute('autocapitalize'),i.getAttribute('spellcheck'),i.spellcheck,i.getAttribute('autocomplete'),i.name]})()")
    check('QuickType: autocorrect/autocapitalize off, spellcheck false, meaningless autocomplete token, non-sensitive name', i == ['off', 'off', 'false', False, 'eve-composer', 'eve-composer'] and not re.search(r'name|email|tel|contact|address|user', i[5].replace('eve-composer', '')), i)
    ctx.close()
    # bridged, compatible
    ctx, pg = page()
    h = sent(pg, 'hello')
    check('hello sent once on load', len(h) == 1, sent(pg))
    check('hello shape {v:1,id,type,payload:{bridge:"1.0.0"}}', h and h[0]['v'] == 1 and isinstance(h[0]['id'], str) and h[0]['id'] and h[0]['payload'] == {'bridge': '1.0.0'}, h)
    check('before capabilities → not active', pg.evaluate('__app.shell().active') is False)
    recv(pg, {'v': 1, 're': h[0]['id'], 'ok': True})
    recv(pg, {'v': 1, 'id': 'c1', 'type': 'capabilities', 'payload': {'bridge': '1.3.0', 'shell': '0.1.0', 'features': ['haptics', 'unpair']}})
    s = pg.evaluate('__app.shell()')
    check('capabilities same major (minor differs) → active, features kept', s['active'] and s['bridge'] == '1.3.0' and s['shell'] == '0.1.0' and s['features'] == ['haptics', 'unpair'], s)
    pg.evaluate("EveShell.haptic('heavy')")
    hp = sent(pg, 'haptics')
    check('haptics message {style}', hp and hp[-1]['payload'] == {'style': 'heavy'}, hp)
    check('haptics replaces navigator.vibrate', pg.evaluate('window.__vib') == 0)
    recv(pg, {'v': 1, 'id': 'u1', 'type': 'something_new', 'payload': {}}); recv(pg, 'garbage'); recv(pg, None); recv(pg, {'v': 2, 'type': 'capabilities', 'payload': {'bridge': '9.0.0'}})
    check('unknown / malformed / wrong-v messages ignored without throwing', pg.evaluate('__app.shell().active') is True and not errs, errs)
    check('__eveShell cannot be replaced', pg.evaluate("(()=>{try{window.__eveShell={receive(){}}}catch{};return Object.isFrozen(window.__eveShell)&&typeof window.__eveShell.receive==='function'&&window.__eveShell.receive.toString().includes('capabilities')})()"))
    check('no secrets/cookies in any bridge message', not re.search(r'eve_session|cookie|token', json.dumps(sent(pg)), re.I))
    n0 = len(state().get('logouts', []))
    pg.evaluate("localStorage.setItem('eve.paired','1')")
    recv(pg, {'v': 1, 'id': 'l1', 'type': 'logout_requested', 'payload': {}}); pg.wait_for_timeout(500)
    lo = state().get('logouts', [])
    check('logout_requested → DELETE /v1/session within 500ms (shell wipes at 2s)', len(lo) == n0 + 1 and lo[-1]['xer'] == '1', lo)
    check('then unpair sent to shell', len(sent(pg, 'unpair')) == 1, sent(pg))
    check('local paired flag cleared', pg.evaluate("localStorage.getItem('eve.paired')") is None)
    put('/auth/on'); ctx.close()
    # bridged, incompatible major
    ctx, pg = page()
    recv(pg, {'v': 1, 'id': 'c2', 'type': 'capabilities', 'payload': {'bridge': '2.0.0', 'shell': '1.0.0', 'features': ['haptics', 'unpair']}})
    s = pg.evaluate('__app.shell()')
    check('major differs → bridge unused (plain PWA)', s['active'] is False and s['features'] == [] and pg.evaluate("EveShell.haptic('light')") is False, s)
    n0 = len(state().get('logouts', []))
    recv(pg, {'v': 1, 'id': 'l2', 'type': 'logout_requested', 'payload': {}}); pg.wait_for_timeout(500)
    check('major differs: logout still revokes the session, no unpair posted', len(state().get('logouts', [])) == n0 + 1 and not sent(pg, 'unpair'))
    put('/auth/on'); ctx.close()
    check('no page errors', not errs, errs)
    b.close()
put('/auth/on')
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
