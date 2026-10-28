# 1.8.0: 409 generation_in_progress → attach to the in-progress message via recover() (eve-serving #62), all body shapes
import os, json, urllib.request
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
R = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
def put(path): return urllib.request.urlopen(urllib.request.Request(B + path, method='PUT')).read()
def state(): return json.loads(urllib.request.urlopen(B + '/__db').read())['state']
errs = []
BAD = ['답변을 끝내지 못했어요', '이미 답변을']
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        for path in ['/auth/on', '/auth4/off', '/db/reset']: put(path)
        for shape in ['nested', 'top', 'details', 'none']:
            put('/dupshape/' + shape)
            ctx = b.new_context(viewport={'width': 390, 'height': 844}); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.add_init_script("localStorage.setItem('eve.mem.introSeen','1')")
            pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1200)
            if pg.is_visible('#tInput') and not pg.is_visible('#input'): pg.evaluate("__app.newChat()"); pg.wait_for_timeout(300)
            pg.fill('#input', 'hello'); pg.keyboard.press('Enter'); pg.wait_for_timeout(3500)
            q = 'dup409 ' + shape
            pg.fill('#input', q); pg.keyboard.press('Enter'); pg.wait_for_timeout(1500)
            check(shape + ': first send failed visibly (busy)', '요청이 많아요' in pg.inner_text('#messages') or '다시' in pg.inner_text('#messages'))
            pg.fill('#input', q); pg.keyboard.press('Enter'); pg.wait_for_timeout(1500)
            check(shape + ': 409 hit once', state().get('dup409n') == 1, state().get('dup409n'))
            n_user = pg.evaluate("t => [...document.querySelectorAll('.msg.user')].filter(e => e.innerText.includes(t)).length", q)
            if shape == 'none':
                check('none: no message_id → existing error behaviour', any(t in pg.inner_text('#messages') for t in ['지금', '답변', '다시']))
            else:
                pg.wait_for_timeout(13000); txt = pg.inner_text('#messages')
                check(shape + ': duplicate user turn dropped', n_user == 1, n_user)
                check(shape + ': no error shown after attach', not any(t in txt.split(q)[-1] for t in BAD) and '요청이 많아요' not in txt.split(q)[-1], txt.split(q)[-1][-200:])
                check(shape + ': attached reply streamed', len(txt.split(q)[-1].strip()) > 20)
                ids = pg.evaluate("[...document.querySelectorAll('.msg.assistant[data-mid]')].map(e=>e.dataset.mid)")
                check(shape + ': single assistant row for the in-progress id', len(ids) == len(set(ids)), ids)
            ctx.close()
        b.close()
except Exception as e: check('run', False, repr(e))
check('no page errors', not errs, errs)
print(f'{sum(R)}/{len(R)}'); raise SystemExit(0 if all(R) else 1)
