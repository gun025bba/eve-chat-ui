# 2.1.0 icon F (ICON-SPEC): assets + ?v=f1 wiring, the 24x16 Eve avatar in the timeline (chat + Today), rise on new events, blink while streaming,
# 88px hero on the empty Today, 40px mark in settings, 72px mark in the connection notice, reduced motion, 320/375/390 no horizontal scroll
import re, json, struct, urllib.request
from playwright.sync_api import sync_playwright
from b2_common import *
R = []; errs = []
put('/csp/off')   # an earlier suite may leave the mock's CSP on; wait_for_function needs eval
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
def rd(f, mode='r'): return open(os.path.join(ROOT, f), mode).read() if mode == 'r' else open(os.path.join(ROOT, f), mode).read()
def png_size(f): d = rd(f, 'rb'); return struct.unpack('>II', d[16:24])
def get(path):
    with urllib.request.urlopen(B + '/ui/' + path) as r: return r.status, r.read()

# ---- 1) files, versions, ?v=f1 wiring
html, man, sw, app = rd('index.html'), json.loads(rd('manifest.webmanifest')), rd('sw.js'), rd('app.js')
for f, wh in [('icons/icon-512.png', (512, 512)), ('icons/icon-192.png', (192, 192)), ('icons/icon-maskable-512.png', (512, 512)), ('icons/icon-maskable-192.png', (192, 192)),
              ('icons/apple-touch-icon.png', (180, 180)), ('apple-touch-icon.png', (180, 180)), ('apple-touch-icon-precomposed.png', (180, 180)), ('icons/favicon-32.png', (32, 32)), ('icons/favicon-16.png', (16, 16))]:
    check(f'{f} is {wh[0]}x{wh[1]}', png_size(f) == wh, png_size(f))
ico = rd('favicon.ico', 'rb'); n = struct.unpack('<H', ico[4:6])[0]; sizes = sorted((ico[6 + 16 * i] or 256) for i in range(n))
check('favicon.ico contains 16, 32 and 48', sizes == [16, 32, 48], sizes)
for f in ('favicon.svg', 'icons/mark-dark.svg', 'icons/mark-light.svg'):
    s = rd(f); check(f'{f}: no external reference, no filter/blur/gradient', not re.search(r'href=["\'](?!#)|<image|filter|blur|Gradient|<text', s), s[:120])
check('mark-dark body #00D2BE, mark-light body #00C4B2', '#00D2BE'.lower() in rd('icons/mark-dark.svg').lower() and '#00C4B2'.lower() in rd('icons/mark-light.svg').lower())
check('manifest: the 4 icons carry ?v=f1 (purposes kept)', [i['src'] for i in man['icons']] == ['icons/icon-192.png?v=f1', 'icons/icon-512.png?v=f1', 'icons/icon-maskable-192.png?v=f1', 'icons/icon-maskable-512.png?v=f1'] and [i['purpose'] for i in man['icons']] == ['any', 'any', 'maskable', 'maskable'], man['icons'])
check('manifest: colors and shortcuts unchanged', man['background_color'] == '#000000' and man['theme_color'] == '#101011' and 'shortcut-new.png' in json.dumps(man['shortcuts']))
links = re.findall(r'<link rel="(?:icon|apple-touch-icon)"[^>]*href="([^"]+)"', html)
check('index.html: 5 icon links, order ico → svg → 32 → 16 → apple-touch, all ?v=f1', [re.sub(r'^/ui/', '', l) for l in links] == ['favicon.ico?v=f1', 'favicon.svg?v=f1', 'icons/favicon-32.png?v=f1', 'icons/favicon-16.png?v=f1', 'icons/apple-touch-icon.png?v=f1'], links)
spl = re.findall(r'apple-touch-startup-image"[^>]*href="([^"]+)"', html)
check('index.html: 22 splash links, all ?v=f1 and a real file', len(spl) == 22 and all(s.endswith('.png?v=f1') and os.path.exists(os.path.join(ROOT, s.split('?')[0])) for s in spl), spl[:2])
check('index.html: no icon URL without ?v=f1', not re.findall(r'(?:favicon|apple-touch-icon|icon-\d+|icon-maskable-\d+|splash/[^"]*)\.(?:ico|svg|png)(?!\?v=f1)"', html), re.findall(r'[^"]*(?:favicon|apple-touch-icon)[^"]*"', html))
check('theme-color metas unchanged', '#101011' in html and '#F6F6F7' in html)
cache = re.search(r"const CACHE = '(llmchat-[\d.]+)'", sw).group(1); ver = re.search(r"APP_VERSION = '([\d.]+)'", app).group(1)
check('CACHE, APP_VERSION and README agree on 2.1.0', cache == 'llmchat-2.1.0' and ver == '2.1.0' and '**2.1.0**' in rd('README.md') and 'styles.css?v=2.1.0' in html and 'v2.1.0' in html, (cache, ver))
check('sw.js: ICONS are the same ?v=f1 URLs as the page links and are in SHELL', '.map(f => `${f}?v=f1`)' in sw and '...ICONS' in sw and all(f"'{x.split('?')[0].replace('/ui/', '')}'" in sw for x in links))

check('own module: eve-mark.js + eve-mark.css are linked (?v=2.1.0, css after styles.css, js before today.js), precached, and styles.css/today.js hold no mark markup',
      html.index('styles.css?v=2.1.0') < html.index('eve-mark.css?v=2.1.0') and html.index('eve-mark.js?v=2.1.0') < html.index('today.js?v=2.1.0') and "'eve-mark.css', 'eve-mark.js'" in sw
      and 'eve-mark' not in rd('styles.css') and 'viewBox="0 0 24 16"' not in rd('today.js') and 'viewBox="0 0 24 16"' in rd('eve-mark.js') and '.av{' in rd('eve-mark.css'))
with sync_playwright() as p:
    b = p.chromium.launch()
    def newpg(scheme='dark', reduced=False, w=390):
        ctx = new_ctx(b, w=w, scheme=scheme, reduced_motion='reduce' if reduced else 'no-preference'); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); return ctx, pg
    # ---- 2) the files are served and the service worker precaches the exact URLs
    reset(); ctx, pg = newpg(); goto_today(pg, wait=1200)
    check('served: icons answer 200 with the right type', all(get(l.replace('/ui/', ''))[0] == 200 for l in links) and get('icons/icon-512.png?v=f1')[1][:4] == b'\x89PNG')
    pg.evaluate("navigator.serviceWorker.ready.then(()=>1)"); pg.wait_for_timeout(1200)
    keys = pg.evaluate("(async()=>{const c=await caches.open('llmchat-2.1.0');return (await c.keys()).map(r=>r.url.replace(location.origin+'/ui/',''))})()")
    check('SW cache llmchat-2.1.0 holds every ?v=f1 link URL (offline icons) and the old cache is gone', all(l.replace('/ui/', '') in keys for l in links) and 'icons/icon-192.png?v=f1' in keys and 'icons/mark-dark.svg?v=f1' in keys and '/ui/eve-mark.css?v=2.1.0'.replace('/ui/', '') in keys and 'eve-mark.js?v=2.1.0' in keys
          and pg.evaluate("caches.keys()") == ['llmchat-2.1.0'], (keys, pg.evaluate("caches.keys()")))
    ctx.close()

    for scheme in ('dark', 'light'):
        body, eye = ('rgb(0, 210, 190)', 'rgb(16, 16, 17)') if scheme == 'dark' else ('rgb(0, 196, 178)', 'rgb(16, 16, 17)')
        # ---- 3) chat timeline: avatar for Eve, dots for the rest
        reset(); seed('아바타 대화', [{'role': 'user', 'content': '안녕', 'created_at': at(7, 41, -1)}, {'role': 'assistant', 'content': '안녕하세요.', 'created_at': at(7, 42, -1)},
                                      {'role': 'user', 'content': '고마워', 'created_at': at(8, 5)}, {'role': 'assistant', 'content': '별말씀을요.', 'created_at': at(8, 6)}])
        ctx, pg = newpg(scheme); open_thread(pg, '아바타 대화'); pg.wait_for_timeout(500)
        m = pg.evaluate("""(()=>{const out=[];for(const e of document.querySelectorAll('#messages > .msg')){const av=e.querySelector(':scope>.av'),dot=e.querySelector(':scope>.dot'),r=e.getBoundingClientRect();
          const o={c:e.className,av:!!av,dot:!!dot};
          if(av){const a=av.getBoundingClientRect(),s=av.querySelector('svg.eve-mark'),cs=getComputedStyle(av),b=av.querySelector('.b'),ey=av.querySelector('.e');
            Object.assign(o,{l:a.left-r.left,t:a.top-r.top,w:a.width,h:a.height,ah:av.getAttribute('aria-hidden'),sh:s&&s.getAttribute('aria-hidden'),sw:s&&s.getAttribute('width'),ov:cs.overflow,
              body:getComputedStyle(b).fill,eye:getComputedStyle(ey).fill,eyes:av.querySelectorAll('.e').length,filt:getComputedStyle(s).filter,shadow:cs.boxShadow,anim:getComputedStyle(s).animationName,
              cx:a.left+a.width/2, rail:(e.getBoundingClientRect().left+51.5)})}
          out.push(o)}return out})()""")
        eve = [x for x in m if 'e' in x['c'].split() and 'me' not in x['c'].split()]; me = [x for x in m if 'me' in x['c'].split()]
        check(f'[{scheme}] 2 Eve events have .av and no .dot; 2 user events keep .dot', len(eve) == 2 and all(x['av'] and not x['dot'] for x in eve) and len(me) == 2 and all(x['dot'] and not x['av'] for x in me), m)
        a = eve[0]
        check(f'[{scheme}] avatar geometry: 24x16 at left 39.5 / top 2, overflow hidden, centre on the rail (51.5)', a['w'] == 24 and a['h'] == 16 and abs(a['l'] - 39.5) < .6 and abs(a['t'] - 2) < .6 and a['ov'] == 'hidden' and abs(a['cx'] - a['rail']) < .6, a)
        check(f'[{scheme}] decorative: aria-hidden on .av and svg, two eyes', a['ah'] == 'true' and a['sh'] == 'true' and a['eyes'] == 2, a)
        check(f'[{scheme}] colors: body {body}, eye {eye}', a['body'] == body and a['eye'] == eye, a)
        check(f'[{scheme}] no blur / glow: no filter, only the 3px halo ring', a['filt'] == 'none' and not re.search(r'\d+px \d+px (?:[1-9]\d*|0\.\d+)px', a['shadow'].replace('0px 0px 0px 3px', '')), a['shadow'])
        check(f'[{scheme}] re-opening the thread: no rise animation, no blink', all(x['anim'] == 'none' for x in eve) and pg.locator('#messages .streaming').count() == 0, eve)
        check(f'[{scheme}] aria-label of an Eve event stays "HH:mm Eve"', re.fullmatch(r'\d\d:\d\d Eve', pg.get_attribute('#messages > .msg.e', 'aria-label') or '') is not None)
        check(f'[{scheme}] the Eve dot glow is gone (no .ev.e .dot)', pg.evaluate("[...document.querySelectorAll('#messages > .msg.e .dot')].length") == 0)
        ctx.close()

        # ---- 4) new answer: rise once on the new last event, blink every 4s while streaming, stop when done
        reset(); ctx, pg = newpg(scheme)
        pg.goto(B + '/ui/'); pg.wait_for_timeout(800); pg.evaluate("location.hash='#/c/new'"); pg.wait_for_timeout(300)
        if pg.is_visible('#tInput'): pg.evaluate("__app.newChat()"); pg.wait_for_timeout(400)
        pg.fill('#input', 'slow 응답'); pg.click('#sendBtn'); pg.wait_for_timeout(700)
        s = pg.evaluate("""(()=>{const e=document.querySelector('#messages > .msg.e'),m=e.querySelector('.av .eve-mark'),ey=e.querySelector('.av .eyes'),cm=getComputedStyle(m),ce=getComputedStyle(ey);
          const anims=document.getAnimations().filter(a=>a.effect&&a.effect.target&&a.effect.target.closest&&a.effect.target.closest('.av'));
          const props=new Set();anims.forEach(a=>a.effect.getKeyframes().forEach(k=>Object.keys(k).forEach(p=>props.add(p))));
          return {streaming:e.classList.contains('streaming'),n:document.querySelectorAll('#messages .streaming').length,rise:cm.animationName,riseD:cm.animationDuration,riseDelay:cm.animationDelay,blink:ce.animationName,blinkD:ce.animationDuration,blinkIt:ce.animationIterationCount,
            blinkDelay:ce.animationDelay,props:[...props].sort(),enter:e.classList.contains('enter'),infinite:anims.filter(a=>a.effect.getTiming().iterations===Infinity).length}})()""")
        check(f'[{scheme}] new Eve event: .enter + avRise 320ms (delay 80ms) on the svg', s['enter'] and s['rise'] == 'avRise' and s['riseD'] == '0.32s' and s['riseDelay'] == '0.08s', s)
        check(f'[{scheme}] streaming: exactly one .streaming, eyes blink 4s infinite, first blink 0.8s in (delay -3s)', s['streaming'] and s['n'] == 1 and s['blink'] == 'eveBlink' and s['blinkD'] == '4s' and s['blinkIt'] == 'infinite' and s['blinkDelay'] == '-3s', s)
        check(f'[{scheme}] only transform / opacity are animated on the avatar; one infinite animation', set(s['props']) <= {'transform', 'opacity', 'offset', 'computedOffset', 'easing', 'composite'} and s['infinite'] == 1, s)
        pg.wait_for_function("!document.querySelector('#messages .streaming')", timeout=60000); pg.wait_for_timeout(300)
        d = pg.evaluate("(()=>{const e=document.querySelector('#messages > .msg.e'),ey=e.querySelector('.av .eyes');return {st:e.classList.contains('streaming'),blink:getComputedStyle(ey).animationName,tf:getComputedStyle(ey).transform,inf:document.getAnimations().filter(a=>a.effect.getTiming().iterations===Infinity&&a.effect.target&&a.effect.target.closest&&a.effect.target.closest('.av')).length}})()")
        check(f'[{scheme}] done: streaming removed, blink stopped, eyes open', not d['st'] and d['blink'] == 'none' and d['inf'] == 0 and d['tf'] in ('none', 'matrix(1, 0, 0, 1, 0, 0)'), d)
        pg.fill('#input', '다음 질문'); pg.click('#sendBtn'); pg.wait_for_function("document.querySelectorAll('#messages > .msg.assistant').length===2", timeout=15000); pg.wait_for_timeout(300)
        one = pg.evaluate("[...document.querySelectorAll('#messages > .msg.assistant')].map(e=>e.classList.contains('enter'))")
        check(f'[{scheme}] only the newest Eve event keeps .enter', one.count(True) == 1 and one[-1] is True, one)
        pg.wait_for_function("!document.querySelector('#messages .streaming')", timeout=60000)
        ctx.close()

        # ---- 5) Today: empty → hero 88x58 once per session; events → avatar, no hero
        reset(); ctx, pg = newpg(scheme); pg.goto(B + '/ui/#/'); pg.wait_for_timeout(2000)   # no reload: the first render of the session is the one that animates
        h = pg.evaluate("""(()=>{const f=document.getElementById('todayFree'),hero=f&&f.querySelector('.hero'),svg=hero&&hero.querySelector('svg'),r=svg&&svg.getBoundingClientRect(),d=document.getElementById('todayDate').getBoundingClientRect(),n=document.querySelector('.rail-now').getBoundingClientRect(),c=document.getElementById('tComposer').getBoundingClientRect();
          return {vis:!!f&&!f.hidden&&f.getBoundingClientRect().height>0,w:r&&r.width,h:r&&r.height,cx:r&&r.left+r.width/2,top:r&&r.top,bot:r&&r.bottom,dateB:d.bottom,nowT:n.top,nowB:n.bottom,compT:c.top,aria:svg&&svg.getAttribute('aria-hidden'),
            enter:hero&&hero.classList.contains('enter'),an:svg&&getComputedStyle(svg).animationName,eyesAn:svg&&getComputedStyle(svg.querySelector('.eyes')).animationName,over:document.getElementById('todayScroller').scrollWidth-document.getElementById('todayScroller').clientWidth,
            sy:document.getElementById('todayScroller').scrollHeight-document.getElementById('todayScroller').clientHeight,mid:(r.top+r.bottom)/2,free:(()=>{const q=f.getBoundingClientRect();return [q.top,q.bottom]})()}})()""")
        check(f'[{scheme}] empty Today: hero visible, 88x58, horizontally centred, aria-hidden', h['vis'] and round(h['w']) == 88 and round(h['h']) == 58 and abs(h['cx'] - 195) < 1.5 and h['aria'] == 'true', h)
        check(f'[{scheme}] hero sits between the date and 지금; 지금 hugs the composer', h['top'] > h['dateB'] and h['bot'] < h['nowT'] and h['compT'] - h['nowB'] < 40, h)
        check(f'[{scheme}] hero is in the upper part of the free area (≈45%)', 0.30 < (h['mid'] - h['free'][0]) / max(1, h['free'][1] - h['free'][0]) < 0.52, h)
        check(f'[{scheme}] first visit of the session: hero rises (avRise) and blinks once (heroBlink)', h['enter'] and h['an'] == 'avRise' and h['eyesAn'] == 'heroBlink', h)
        check(f'[{scheme}] empty Today: no scroll overflow', h['over'] <= 0 and h['sy'] <= 1, h)
        pg.reload(); pg.wait_for_timeout(1500)
        h2 = pg.evaluate("(()=>{const hero=document.querySelector('#todayFree .hero');return {vis:!document.getElementById('todayFree').hidden,enter:hero.classList.contains('enter'),an:getComputedStyle(hero.querySelector('svg')).animationName}})()")
        check(f'[{scheme}] revisit in the same session: static hero (no .enter, no animation)', h2['vis'] and not h2['enter'] and h2['an'] == 'none', h2)
        ctx.close()
        reset(); ids = rich(); ctx, pg = newpg(scheme); goto_today(pg, wait=1500)
        t = pg.evaluate("""(()=>({free:document.getElementById('todayFree').hidden,emptyCls:document.getElementById('todayScroller').classList.contains('is-empty'),
          pro:[...document.querySelectorAll('#todayList .ev.e.pro')].map(e=>({av:!!e.querySelector(':scope>.av'),dot:!!e.querySelector(':scope>.dot'),l:e.querySelector('.av')?.getBoundingClientRect().left-e.getBoundingClientRect().left,w:e.querySelector('.av')?.getBoundingClientRect().width,h:e.querySelector('.av')?.getBoundingClientRect().height})),
          other:[...document.querySelectorAll('#todayList .ev:not(.e), #todayList .rail-now')].map(e=>({c:e.className.split(' ')[1]||e.className,av:!!e.querySelector(':scope>.av'),dot:!!e.querySelector(':scope>.dot')}))}))()""")
        check(f'[{scheme}] Today with events: hero hidden; 선톡 events have the avatar (24x16 @39.5), me / 이어서 / 지금 keep dots', t['free'] and not t['emptyCls'] and len(t['pro']) == 3 and all(x['av'] and not x['dot'] and abs(x['l'] - 39.5) < .6 and x['w'] == 24 and x['h'] == 16 for x in t['pro'])
              and t['other'] and all(x['dot'] and not x['av'] for x in t['other']), t)
        ctx.close()

        # ---- 6) settings top mark 40px, connection notice mark 72px
        reset(); ctx, pg = newpg(scheme); goto_today(pg); pg.click('#openSettings'); pg.wait_for_timeout(900)
        s = pg.evaluate("""(()=>{const m=document.querySelector('.s-top .hero svg').getBoundingClientRect(),p=document.getElementById('sPriv').getBoundingClientRect();return {w:m.width,h:m.height,left:m.right<=p.left,aria:document.querySelector('.s-top .hero svg').getAttribute('aria-hidden'),txt:document.getElementById('sPriv').textContent.trim(),vis:m.width>0}})()""")
        check(f'[{scheme}] settings top: 40x26 mark left of "로컬 · 비공개"', round(s['w']) == 40 and round(s['h']) == 26 and s['left'] and s['aria'] == 'true' and s['txt'] == '로컬 · 비공개', s)
        pg.evaluate("{const n=document.getElementById('authNotice');n.hidden=false;n.classList.add('in')}"); pg.wait_for_timeout(500)
        a = pg.evaluate("""(()=>{const m=document.querySelector('.auth-hero svg').getBoundingClientRect(),cs=getComputedStyle(document.querySelector('.auth-hero .b')).fill;return {w:m.width,h:m.height,t:document.getElementById('authTitle').textContent,b:document.getElementById('authBody').textContent,fill:cs}})()""")
        check(f'[{scheme}] connection notice: 72x47 mark above unchanged copy', round(a['w']) == 72 and round(a['h']) == 47 and a['t'] == '서버에 연결할 수 없어요' and 'Tailscale' in a['b'] and a['fill'] == 'rgb(0, 210, 190)', a)
        ctx.close()

    # ---- 7) reduced motion: no blink, rise only fades, hero only fades
    reset(); ctx, pg = newpg('dark', reduced=True)
    pg.goto(B + '/ui/'); pg.wait_for_timeout(800); pg.evaluate("location.hash='#/c/new'"); pg.wait_for_timeout(300)
    if pg.is_visible('#tInput'): pg.evaluate("__app.newChat()"); pg.wait_for_timeout(400)
    pg.fill('#input', 'slow 응답'); pg.click('#sendBtn'); pg.wait_for_timeout(800)
    r = pg.evaluate("(()=>{const e=document.querySelector('#messages > .msg.e');return {st:e.classList.contains('streaming'),blink:getComputedStyle(e.querySelector('.av .eyes')).animationName,rise:getComputedStyle(e.querySelector('.av .eve-mark')).animationName,riseD:getComputedStyle(e.querySelector('.av .eve-mark')).animationDuration}})()")
    check('reduced motion: still .streaming but no blink; the avatar only fades in (avFade 200ms)', r['st'] and r['blink'] == 'none' and r['rise'] == 'avFade' and r['riseD'] == '0.2s', r)
    pg.wait_for_function("!document.querySelector('#messages .streaming')", timeout=60000); ctx.close()

    # ---- 8) 320/375/390: no horizontal scroll (chat with avatars, empty Today)
    for w in (320, 375, 390):
        reset(); seed('가로 확인', [{'role': 'user', 'content': 'x' * 80, 'created_at': at(8, 5)}, {'role': 'assistant', 'content': 'y' * 120 + ' `code_long_identifier_that_does_not_break_anywhere_at_all`', 'created_at': at(8, 6)}])
        ctx, pg = newpg('dark', w=w); open_thread(pg, '가로 확인'); pg.wait_for_timeout(400)
        o1 = pg.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth"); ctx.close()
        reset(); ctx, pg = newpg('light', w=w); goto_today(pg, wait=1300)
        o2 = pg.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth"); ctx.close()
        check(f'{w}px: no horizontal scroll (thread with avatar, empty Today with hero)', o1 <= 0 and o2 <= 0, (o1, o2))
    b.close()
check('no page errors', not errs, errs)
print(f'{sum(R)} passed, {len(R) - sum(R)} failed'); raise SystemExit(0 if all(R) else 1)
