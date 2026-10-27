# 1.3.2: gateway #57 — 403 identity_not_allowed is treated exactly like 401 (auth notice); other 403s keep their behavior
import os, json, re
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
R = []
def check(name, ok, extra=''): R.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, extra)
SHAPES = {'ec': lambda c: {'error_code': c}, 'legacy': lambda c: {'error': {'code': c, 'message': c, 'type': 'x'}}}
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    def page(routes):
        ctx = b.new_context(viewport={'width': 390, 'height': 844}); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        for pat, (st, body) in routes.items():
            pg.route(re.compile(pat), lambda r, _req=None, st=st, body=body: r.fulfill(status=st, content_type='application/json', body=json.dumps(body)))
        pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1500); return ctx, pg
    vis = lambda pg: pg.is_visible('#authNotice')
    def send(pg):
        pg.click('#newChat'); pg.wait_for_timeout(400)
        pg.fill('#input', 'hi'); pg.click('#sendBtn'); pg.wait_for_timeout(1200)
    ctx, pg = page({}); check('version 1.3.2', pg.evaluate('__app.version') == '1.3.2'); check('baseline: no auth notice', not vis(pg)); ctx.close()
    for sh, mk in SHAPES.items():
        ctx, pg = page({r'/whoami$': (403, mk('identity_not_allowed'))}); check(f'[{sh}] whoami 403 identity_not_allowed → auth notice', vis(pg)); ctx.close()
        ctx, pg = page({r'/v1/threads\?': (403, mk('identity_not_allowed'))}); check(f'[{sh}] api() threads 403 identity_not_allowed → auth notice', vis(pg)); ctx.close()
        ctx, pg = page({r'/v1/chat/completions': (403, mk('identity_not_allowed'))}); send(pg); check(f'[{sh}] chat 403 identity_not_allowed → auth notice', vis(pg)); ctx.close()
        ctx, pg = page({r'/v1/models': (403, mk('identity_not_allowed'))}); pg.evaluate("document.getElementById('loadModels').click()"); pg.wait_for_timeout(800); check(f'[{sh}] models 403 identity_not_allowed → auth notice', vis(pg)); ctx.close()
        for code in ['invalid', 'scope_denied', 'kill_switch']:
            ctx, pg = page({r'/whoami$': (403, mk(code)), r'/v1/threads\?': (403, mk(code)), r'/v1/models': (403, mk(code))}); pg.evaluate("document.getElementById('loadModels').click()"); pg.wait_for_timeout(800)
            check(f'[{sh}] 403 {code} (whoami/threads/models) → no auth notice', not vis(pg)); ctx.close()
            ctx, pg = page({r'/v1/chat/completions': (403, mk(code))}); send(pg); check(f'[{sh}] chat 403 {code} → no auth notice, error shown', not vis(pg) and pg.locator('.msg.error').count() > 0); ctx.close()
    ctx, pg = page({r'/v1/chat/completions': (401, SHAPES['legacy']('unauthenticated'))}); send(pg); check('401 still → auth notice', vis(pg)); ctx.close()
    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
