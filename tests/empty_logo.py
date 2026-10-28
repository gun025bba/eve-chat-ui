# 1.10.0 — empty new-chat screen: the Eve mark must paint with no network/SW/path dependency (inline data: URI)
import os, re, zlib, struct
from playwright.sync_api import sync_playwright

def png_pixels(data):   # minimal stdlib PNG decoder (8-bit RGB/RGBA, non-interlaced) — no Pillow dependency
    pos, idat, w = 8, b'', 0
    while pos < len(data):
        n, typ = struct.unpack('>I4s', data[pos:pos + 8]); body = data[pos + 8:pos + 8 + n]; pos += 12 + n
        if typ == b'IHDR': w, h, depth, ct = struct.unpack('>IIBB', body[:10])
        elif typ == b'IDAT': idat += body
    bpp = 4 if ct == 6 else 3; raw = zlib.decompress(idat); stride = w * bpp; rows = []; prev = bytearray(stride); i = 0
    for _ in range(h):
        f = raw[i]; line = bytearray(raw[i + 1:i + 1 + stride]); i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0; b = prev[x]; c = prev[x - bpp] if x >= bpp else 0
            if f == 1: line[x] = (line[x] + a) & 255
            elif f == 2: line[x] = (line[x] + b) & 255
            elif f == 3: line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c); line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line); prev = line
    return w, h, bpp, rows
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
R = []
def check(name, ok, extra=''): R.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, extra)
css = open(os.path.join(os.path.dirname(__file__), '..', 'styles.css')).read()
check('no mark rule points at an external icons/ file', not re.search(r'\.empty \.mark[^}]*url\(\s*["\']?icons/', css))
check('both schemes use an inline svg data: URI', len(re.findall(r'\.empty \.mark\{[^}]*url\("data:image/svg\+xml', css)) == 2)
check('no transition:all', not re.search(r'transition:\s*all', css))
SET = "localStorage.setItem('eve.mem.introSeen','1');localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit'}));Object.defineProperty(navigator,'standalone',{get:()=>true})"
def run(p, engine, scheme):
    b = getattr(p, engine).launch()
    kw = {k: v for k, v in p.devices['iPhone 14'].items() if k != 'default_browser_type'} if engine == 'webkit' else {'viewport': {'width': 390, 'height': 844}, 'is_mobile': True, 'has_touch': True, 'device_scale_factor': 3}
    ctx = b.new_context(**kw, color_scheme=scheme)
    ctx.add_init_script(SET)
    pg = ctx.new_page(); errs = []; reqs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('request', lambda r: reqs.append(r.url))
    ctx.route(re.compile(r'.*/icons/mark-.*\.svg'), lambda r: r.abort())   # the asset is unreachable (offline cache miss, wrong path, blocked): the mark must still paint
    pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1500)
    if pg.evaluate("document.getElementById('app').dataset.route") != 'chat': pg.click('#newChat'); pg.wait_for_timeout(900)
    tag = f'{engine}/{scheme}'
    info = pg.evaluate("""() => { const m = document.querySelector('.empty .mark'), t = document.querySelector('.empty .mark-tile'), r = m.getBoundingClientRect(), tr = t.getBoundingClientRect();
      return {bg: getComputedStyle(m).backgroundImage.slice(0, 30), x: r.x, y: r.y, w: r.width, h: r.height, tw: tr.width, th: tr.height, chips: document.querySelectorAll('.empty .chip').length,
              sub: document.querySelector('.empty>small')?.textContent, h1: document.querySelector('.empty h1')?.textContent, std: document.documentElement.classList.contains('standalone')} }""")
    check(f'[{tag}] standalone mode on, mark on screen', info['std'] and 0 <= info['x'] < 390, info)
    check(f'[{tag}] background is the inline data: URI', info['bg'].startswith('url("data:image/svg+xml'), info['bg'])
    check(f'[{tag}] layout unchanged: 34px mark in 56px tile, 4 chips + subtitle + h1 kept', (round(info['w']), round(info['h']), round(info['tw']), round(info['th'])) == (34, 34, 56, 56) and info['chips'] == 4 and info['sub'] == 'Eve는 이 기기 가까이에서 실행돼요' and info['h1'] == '무엇을 도와드릴까요?', info)
    pg.wait_for_timeout(600)
    w, h, bpp, rows = png_pixels(pg.screenshot())
    sx = w / pg.evaluate('innerWidth')
    x0, y0, x1, y1 = (round(v * sx) for v in (info['x'], info['y'], info['x'] + info['w'], info['y'] + info['h']))
    px = lambda x, y: tuple(rows[y][x * bpp:x * bpp + 3]); bgc = px(x0, y0)
    pts = [px(x, y) for y in range(y0, y1) for x in range(x0, x1)]
    diff = sum(1 for q in pts if sum(abs(a - b) for a, b in zip(q, bgc)) > 90)
    crop = type('C', (), {'width': x1 - x0, 'height': y1 - y0, 'size': (x1 - x0, y1 - y0)})
    check(f'[{tag}] mark pixels are painted (not an empty tile) with icons/mark-*.svg blocked', diff > 0.12 * crop.width * crop.height, (diff, crop.size))
    check(f'[{tag}] mark svg was never requested', not any('icons/mark-' in u for u in reqs), [u for u in reqs if 'mark-' in u])
    check(f'[{tag}] no page errors', not errs, errs)
    ctx.close(); b.close()
with sync_playwright() as p:
    for engine in ['webkit', 'chromium']:
        for scheme in ['dark', 'light']: run(p, engine, scheme)
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
