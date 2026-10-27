# 1.5.1 blocker: no backdrop-filter anywhere, opaque headers/materials, composer autocorrect/spellcheck/autocomplete off, SW network-first HTML + versioned assets
import os, re
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
R = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
d = os.path.join(os.path.dirname(__file__), '..')
strip = lambda t: re.sub(r'/\*[\s\S]*?\*/', '', t)
for f in ['styles.css', 'offline.css', 'index.html', 'offline.html', 'app.js', 'memory.js', 'proactive.js']:
    t = strip(open(os.path.join(d, f)).read())
    hits = re.findall(r'(?:backdrop-filter|backdropFilter)[^;}\n]{0,40}', t)
    check(f'{f}: no backdrop-filter', not hits, hits)
css = strip(open(os.path.join(d, 'styles.css')).read())
alpha = re.findall(r'--(?:header-bg|material|layer-1|layer-2|card)\s*:\s*(rgba?\([^)]*\)|hsla?\([^)]*\)|#[0-9a-fA-F]{8}\b|transparent)', css)
check('header/material tokens are opaque (no alpha)', not [a for a in alpha if a.startswith(('rgba', 'hsla', 'transparent')) or (a.startswith('#') and len(a) == 9)], alpha)
html = open(os.path.join(d, 'index.html')).read()
tag = re.search(r'<textarea id="input"[^>]*>', html).group(0)
check('static composer attrs: autocorrect=off spellcheck=false autocomplete=off', all(a in tag for a in ['autocorrect="off"', 'spellcheck="false"', 'autocomplete="off"']), tag)
sw = open(os.path.join(d, 'sw.js')).read()
check('sw: no ignoreSearch for versioned assets, precache uses cache:reload', "cache: 'reload'" in sw and 'styles.css' not in re.search(r"const SHELL = \[[^\]]*\]", sw).group(0).replace('...ASSETS', ''), None)
OPAQ = """(()=>{const bad=[];for(const n of document.querySelectorAll('*')){const c=getComputedStyle(n);const bf=c.backdropFilter||c.webkitBackdropFilter||'none';if(bf!=='none')bad.push((n.id||n.className||n.tagName)+' '+bf)}
  const hdr=[...document.querySelectorAll('#topbar,.navbar,.sheet-head,.src-sheet-head')].filter(n=>n.offsetParent!==null).map(n=>[n.id||n.className,getComputedStyle(n).backgroundColor]);
  return {bad,hdr:hdr.filter(([,bg])=>!/^rgb\\(/.test(bg)&&!(bg==='rgba(0, 0, 0, 0)'&&false))}})()"""
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True, color_scheme=scheme); pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.add_init_script("localStorage.setItem('eve.mem.introSeen','1')")
        pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1200)
        if scheme == 'dark': check('version 1.5.1', pg.evaluate('__app.version') == '1.5.1')
        r = pg.evaluate(OPAQ); check(f'[{scheme}] list: no computed backdrop-filter; headers opaque', not r['bad'] and not r['hdr'], r)
        pg.click('#newChat'); pg.wait_for_timeout(500)
        r = pg.evaluate(OPAQ); check(f'[{scheme}] chat: no computed backdrop-filter; headers opaque', not r['bad'] and not r['hdr'], r)
        f = pg.evaluate("(()=>{const f=getComputedStyle(document.querySelector('#composer .field'));return f.backgroundColor})()")
        check(f'[{scheme}] composer field opaque', f.startswith('rgb('), f)
        i = pg.evaluate("(()=>{const i=document.getElementById('input');return {ac:i.getAttribute('autocorrect'),sc:i.spellcheck,scA:i.getAttribute('spellcheck'),acm:i.getAttribute('autocomplete'),form:!!i.closest('form')}})()")
        check(f'[{scheme}] composer: autocorrect off, spellcheck false, autocomplete off, no form', i == {'ac': 'off', 'sc': False, 'scA': 'false', 'acm': 'off', 'form': False}, i)
        pg.evaluate("window.__app && document.dispatchEvent(new Event('x'))")
        pg.click('#openSettings') if pg.is_visible('#openSettings') else None
        if pg.evaluate("!!document.querySelector('dialog#settings[open]')"):
            pg.wait_for_timeout(600); r = pg.evaluate(OPAQ); check(f'[{scheme}] settings: no backdrop-filter; sheet head opaque', not r['bad'] and not r['hdr'], r)
        check(f'[{scheme}] no page errors', not errs, errs); ctx.close()
    # SW: HTML network-first, exact versioned cache keys, old cache cannot win
    ctx = b.new_context(viewport={'width': 390, 'height': 844}); pg = ctx.new_page()
    pg.goto(B + '/ui/'); pg.wait_for_timeout(1500); pg.reload(); pg.wait_for_timeout(1500)
    ks = pg.evaluate("caches.keys().then(async ks=>{const out={};for(const k of ks){out[k]=(await (await caches.open(k)).keys()).map(r=>new URL(r.url).pathname+new URL(r.url).search)}return out})")
    keys = ks.get('llmchat-1.5.1', [])
    check('SW cache llmchat-1.5.1 holds versioned assets', '/ui/styles.css?v=1.5.1' in keys and '/ui/app.js?v=1.5.1' in keys, keys)
    check('SW cache has no unversioned styles.css/app.js', '/ui/styles.css' not in keys and '/ui/app.js' not in keys, keys)
    pg.evaluate("caches.open('llmchat-1.5.1').then(c=>Promise.all([c.put('index.html',new Response('<html><body>STALE-SHELL</body></html>',{headers:{'Content-Type':'text/html'}})),c.put('./',new Response('STALE-SHELL',{headers:{'Content-Type':'text/html'}}))]))")
    pg.evaluate("caches.open('llmchat-1.5.1').then(c=>c.put('/ui/styles.css',new Response('#topbar{backdrop-filter:blur(9px)}',{headers:{'Content-Type':'text/css'}})))")
    pg.reload(); pg.wait_for_timeout(1500)
    check('navigation is network-first (stale cached index ignored)', 'STALE-SHELL' not in pg.content() and pg.evaluate("!!window.__app"), pg.content()[:120])
    check('stale unversioned styles.css cannot satisfy styles.css?v=1.5.1', pg.evaluate("getComputedStyle(document.getElementById('topbar')).backdropFilter") in ('none', ''))
    check('controlled by SW', pg.evaluate("!!navigator.serviceWorker.controller"))
    ctx.close(); b.close()
print(f"{sum(R)}/{len(R)} passed" if all(R) else f"FAILED {R.count(False)}/{len(R)}")
