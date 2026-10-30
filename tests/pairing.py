from assets_common import source_path
# 1.6.0: 4.0.0 identity-transport (eve-serving #23 @8871f9f/1fdc436) — 401 → pairing code entry, re-pair notice, 403 scope_denied keeps session
import os, json, urllib.request
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
R = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
def put(path): return json.load(urllib.request.urlopen(urllib.request.Request(B + path, method='PUT')) ) if path == '/x' else urllib.request.urlopen(urllib.request.Request(B + path, method='PUT')).read()
errs = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        for path in ['/auth/on', '/auth4/on', '/scope403/off', '/deny/off', '/db/reset']: put(path)
        ctx = b.new_context(viewport={'width': 390, 'height': 844}); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.add_init_script("localStorage.setItem('eve.mem.introSeen','1')")
        put('/auth/off'); pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1500)
        check('401 at startup (first time) → pairing screen', pg.is_visible('#authNotice') and pg.is_visible('#pairCode') and pg.text_content('#authTitle') == '이 기기를 연결해 주세요', pg.text_content('#authTitle'))
        check('submit disabled until 8 chars', pg.is_disabled('#pairSubmit'))
        check('single-use / 10-minute hint shown', '10분 동안 한 번만' in pg.text_content('#pairHint'))
        attrs = pg.evaluate("(()=>{const i=document.querySelector('#pairCode');return [i.getAttribute('autocapitalize'),i.getAttribute('autocorrect'),i.getAttribute('spellcheck'),i.getAttribute('autocomplete'),i.maxLength]})()")
        check('code input attrs', attrs == ['characters', 'off', 'false', 'one-time-code', 9], attrs)
        pg.fill('#pairCode', ''); pg.type('#pairCode', 'abcdo1il')
        check('normalized to Crockford XXXX-XXXX', pg.input_value('#pairCode') == 'ABCD-0111', pg.input_value('#pairCode'))
        put('/paircode/WXYZ-2345')
        pg.click('#pairSubmit'); pg.wait_for_timeout(600)
        check('wrong code → inline error, notice stays', pg.is_visible('#pairErr') and '코드가 맞지 않거나' in pg.text_content('#pairErr') and pg.is_visible('#authNotice'))
        check('input marked invalid', pg.get_attribute('#pairCode', 'aria-invalid') == 'true')
        check('failure shows remaining attempts (4)', '남은 시도 4번' in pg.text_content('#pairErr'), pg.text_content('#pairErr'))
        bodies = json.loads(urllib.request.urlopen(urllib.request.Request(B + '/__db')).read())['state'].get('pairBodies')
        check('POST /v1/pair body {code:"XXXX-XXXX"}', bodies == [{'code': 'ABCD-0111'}], bodies)
        mut = [m for m in json.loads(urllib.request.urlopen(urllib.request.Request(B + '/__mut', method='PUT')).read()) if m['p'] == '/v1/pair']
        check('pair POST passes CSRF gate (X-Eve-Request + Origin)', mut and all(m['ok'] for m in mut), mut)
        pg.fill('#pairCode', ''); pg.type('#pairCode', 'wxyz2345'); pg.click('#pairSubmit'); pg.wait_for_timeout(1200)
        check('right code → session, notice hidden', pg.is_hidden('#authNotice'))
        check('paired flag stored (no code/token in storage)', pg.evaluate("localStorage.getItem('eve.paired')") == '1' and 'WXYZ' not in pg.evaluate("JSON.stringify(localStorage)"))
        # chat works after pairing
        pg.evaluate("__app.newChat()"); pg.wait_for_timeout(400); pg.fill('#input', 'hello'); pg.click('#sendBtn'); pg.wait_for_timeout(1500)
        check('chat works after pairing', pg.locator('.msg.assistant').count() >= 1 and pg.locator('.msg.error').count() == 0)
        # session expires → re-pair notice; message resent after pairing
        put('/auth/off'); put('/paircode/QRST-6789')
        pg.fill('#input', 'after expiry'); pg.click('#sendBtn'); pg.wait_for_timeout(800)
        check('401 after being paired → re-pair notice', pg.is_visible('#authNotice') and pg.text_content('#authTitle') == '다시 연결해 주세요' and pg.is_visible('#pairCode'), pg.text_content('#authTitle'))
        n0 = pg.locator('.msg.user').count()
        pg.type('#pairCode', 'qrst6789'); pg.click('#pairSubmit'); pg.wait_for_timeout(2000)
        check('re-pair → notice hidden, pending send retried without error', pg.is_hidden('#authNotice') and pg.locator('.msg.error').count() == 0, pg.locator('.msg.error').all_text_contents())
        check('no duplicate user bubble on retry', pg.locator('.msg.user').count() == n0)
        # 5 failures → locked state (server voids codes for 10 min)
        put('/auth/off'); put('/paircode/MNPQ-2222'); pg.reload(); pg.wait_for_timeout(1200)
        put('/auth/on'); pg.click('#authRetry'); pg.wait_for_timeout(800)
        check('"이미 연결했어요" retry clears notice when session is back', pg.is_hidden('#authNotice'))
        put('/auth/off'); pg.reload(); pg.wait_for_timeout(1200)
        for _ in range(5):
            pg.fill('#pairCode', ''); pg.type('#pairCode', 'aaaa0000'); pg.click('#pairSubmit'); pg.wait_for_timeout(300)
        check('5 failures → locked message, input + submit disabled', '잠겼어요' in pg.text_content('#pairErr') and '10분' in pg.text_content('#pairErr') and pg.is_disabled('#pairCode') and pg.is_disabled('#pairSubmit'), pg.text_content('#pairErr'))
        pg.reload(); pg.wait_for_timeout(1200)
        check('lock survives reload', pg.is_disabled('#pairCode') and '잠겼어요' in pg.text_content('#pairErr'))
        check('lock stores no code', 'AAAA' not in pg.evaluate("JSON.stringify(localStorage)") and 'MNPQ' not in pg.evaluate("JSON.stringify(localStorage)"))
        pg.evaluate("localStorage.setItem('eve.pairLock', JSON.stringify({fails:0, until:Date.now()-1}))"); pg.reload(); pg.wait_for_timeout(1200)
        check('lock expiry → entry enabled again', pg.is_enabled('#pairCode') and pg.is_hidden('#pairErr'))
        # 401 invalid_session → re-pair notice even without local paired flag
        put('/auth/on'); pg.evaluate("localStorage.removeItem('eve.paired')"); put('/invalidsession/on'); pg.reload(); pg.wait_for_timeout(1200)
        check('401 invalid_session → re-pair notice', pg.is_visible('#authNotice') and pg.text_content('#authTitle') == '다시 연결해 주세요' and pg.is_visible('#pairCode'), pg.text_content('#authTitle'))
        put('/paircode/HJKM-3456'); pg.type('#pairCode', 'hjkm3456'); pg.click('#pairSubmit'); pg.wait_for_timeout(1000)
        check('re-pair clears invalid_session', pg.is_hidden('#authNotice'))
        # 403 scope_denied: session kept, message, no pairing
        put('/scope403/on')
        (pg.is_visible('#input') or pg.evaluate("__app.newChat()")); pg.wait_for_timeout(400); pg.fill('#input', 'scope'); pg.click('#sendBtn'); pg.wait_for_timeout(1000)
        check('403 scope_denied → no auth/pairing notice', pg.is_hidden('#authNotice'))
        check('403 scope_denied → not-allowed-in-this-session message', '이 세션에서는 할 수 없는 작업이에요' in ' '.join(pg.locator('.msg.error').all_text_contents()), pg.locator('.msg.error').all_text_contents())
        check('paired flag kept', pg.evaluate("localStorage.getItem('eve.paired')") == '1')
        put('/scope403/off')
        # identity_not_allowed keeps its own notice, no pairing form
        put('/deny/on'); pg.reload(); pg.wait_for_timeout(1200)
        check('identity_not_allowed → distinct notice without pairing form', pg.text_content('#authTitle') == '이 계정은 쓸 수 없어요' and pg.is_hidden('#pairForm'))
        put('/deny/off'); pg.click('#authRetry'); pg.wait_for_timeout(600)
        check('denied clears on retry', pg.is_hidden('#authNotice'))
        check('no page errors', not errs, errs)
        d = os.path.join(os.path.dirname(__file__), '..'); import re as _re
        stat = ''.join(open(source_path(os.path.join(d, f))).read() for f in ['index.html', 'manifest.webmanifest', 'sw.js', 'app.js'])
        check('public /ui static files carry no codes/tokens/hosts', not _re.search(r'eve_session=|ts\.net|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.', stat))
        b.close()
finally:
    for path in ['/auth/on', '/auth4/off', '/scope403/off', '/deny/off', '/paircode/', '/invalidsession/off']: put(path)
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
