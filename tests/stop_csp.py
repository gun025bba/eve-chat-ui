"""v14: generation stop (stream + non-stream, local + server) and CSP compliance under the gateway's /ui policy."""
from playwright.sync_api import sync_playwright
import urllib.request, json, time
B = 'http://127.0.0.1:8765'
def put(path, body=None):
    r = urllib.request.Request(B + path, method='PUT', data=json.dumps(body).encode() if body else None, headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(r))
def db(): return json.load(urllib.request.urlopen(B + '/__db'))
FAIL = []
def check(name, ok, info=''):
    print(('PASS ' if ok else 'FAIL ') + name + (' ' + str(info) if info and not ok else ''))
    if not ok: FAIL.append(name)

with sync_playwright() as p:
    b = p.chromium.launch()
    put('/auth/on'); put('/reset'); put('/db/reset'); put('/csp/on')
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, service_workers='allow')
    pg = ctx.new_page()
    viol, errs, cons = [], [], []
    ctx.add_init_script("""document.addEventListener('securitypolicyviolation', e => { (window.__csp = window.__csp || []).push(e.violatedDirective + ' ' + e.blockedURI + ' ' + (e.sourceFile||'') + ':' + e.lineNumber); });""")
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: cons.append(m.text) if ('Content Security Policy' in m.text or 'Refused' in m.text) else None)
    def openFirst(t):
        if not pg.is_visible('#input'): pg.evaluate("document.querySelector('#convList li.row .row-main').click()"); pg.wait_for_timeout(t)
    def allviol(page=pg): return (page.evaluate("window.__csp || []") or []) + cons
    hdr = urllib.request.urlopen(B + '/ui/').headers.get('Content-Security-Policy')
    check('mock serves CSP header', hdr and "default-src 'self'" in hdr, hdr)

    # ---------- server mode ----------
    put('/persist/on')
    pg.goto(B + '/ui/'); pg.wait_for_timeout(800)
    pg.evaluate("location.hash='#/c/new'"); pg.wait_for_timeout(200)
    if pg.is_visible('#newChat'): pg.click('#newChat'); pg.wait_for_timeout(500)
    check('empty-state chips staggered via CSSOM (no style attr)', pg.evaluate("[...document.querySelectorAll('.chip')].every(c => !c.getAttribute('style') || c.style.animationDelay)"))
    pg.fill('#input', 'slow stop test'); pg.click('#sendBtn'); pg.wait_for_timeout(1500)
    btn = pg.locator('#sendBtn')
    check('send morphs to stop', pg.evaluate("document.querySelector('#sendBtn').classList.contains('stop')"))
    check("stop aria-label '생성 중지'", btn.get_attribute('aria-label') == '생성 중지', btn.get_attribute('aria-label'))
    hit = pg.evaluate("(()=>{const b=document.querySelector('#sendBtn'),r=b.getBoundingClientRect(),s=getComputedStyle(b,'::before');return {w:r.width-2*parseFloat(s.left||0),h:r.height-2*parseFloat(s.top||0),pos:s.position}})()")
    check('stop hit area >= 44pt', hit['w'] >= 44 and hit['h'] >= 44, hit)
    check('composer usable during generation', pg.is_editable('#input'))
    before = pg.locator('.msg.assistant').last.inner_text()
    btn.click(); pg.wait_for_timeout(700)
    a = pg.locator('.msg.assistant').last
    check('partial reply kept on screen', '조각0' in a.inner_text(), a.inner_text()[:80])
    check("'중지됨' marker under message", a.locator('.stopped').count() == 1 and a.locator('.stopped').inner_text().strip() == '중지됨')
    check('marker not in content text', '*(중지됨)*' not in a.locator('.bubble').inner_text())
    check('reasoning kept', a.locator('details.think').count() == 1)
    check('no error bubble on user abort', pg.locator('.msg.error').count() == 0)
    check('no toast on user abort', not pg.evaluate("document.querySelector('#toast').classList.contains('show')"), pg.text_content('#toast'))
    check('button back to send', not pg.evaluate("document.querySelector('#sendBtn').classList.contains('stop')") and btn.get_attribute('aria-label') == '전송')
    check('no outbox entries after abort', pg.evaluate("window.__app.state().outbox") == 0)
    pg.wait_for_timeout(1500)
    d = db(); am = [m for m in d['messages'] if m['role'] == 'assistant']
    check('server stored status=incomplete', am and am[-1]['status'] == 'incomplete', am[-1:] )
    mid = pg.evaluate("document.querySelector('.msg.assistant:last-of-type')?.dataset.mid || [...document.querySelectorAll('.msg.assistant')].pop().dataset.mid")
    check('stopped msg id resolved from server', mid == am[-1]['id'], (mid, am[-1]['id'] if am else None))
    check('regenerate available on stopped reply', a.locator('.actions .r').count() == 1)
    pg.fill('#input', 'x'); check('composer usable right after stop', not pg.is_disabled('#sendBtn')); pg.fill('#input', '')
    # regenerate replaces the same server message (no duplicate user msg)
    nuser = len([m for m in db()['messages'] if m['role'] == 'user'])
    a.locator('.actions .r').click(); pg.wait_for_timeout(500)
    check('regenerate sends replace_message_id of stopped msg', db()['state'].get('lastBody', {}).get('replace_message_id') == am[-1]['id'])
    pg.wait_for_function("() => !document.querySelector('#sendBtn').classList.contains('stop')", timeout=30000); pg.wait_for_timeout(500)
    d = db(); check('regenerate replaced in place', len([m for m in d['messages'] if m['role'] == 'user']) == nuser and d['messages'][-1]['status'] == 'complete', [(m['role'], m['status']) for m in d['messages']])
    check('regenerated reply has no marker', pg.locator('.msg.assistant').last.locator('.stopped').count() == 0)
    # reload: server incomplete messages show the marker
    pg.fill('#input', 'slow again'); pg.click('#sendBtn'); pg.wait_for_timeout(1200)
    pg.keyboard.press('Escape'); pg.wait_for_timeout(1500)
    check('Escape stops generation', pg.locator('.msg.assistant').last.locator('.stopped').count() == 1 and not pg.evaluate("document.querySelector('#sendBtn').classList.contains('stop')"))
    pg.evaluate("localStorage.removeItem('llmchat.srvcache')"); pg.reload(); pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('#convList li.row .row-main').click()"); pg.wait_for_timeout(1500)
    check('server incomplete message rendered with marker after reload', pg.locator('.msg.assistant .stopped').count() >= 1, (pg.locator('.msg.assistant').count(), pg.is_visible('#input'), [(m['role'], m['status'], m['content'][:15]) for m in db()['messages']], pg.evaluate("location.hash")))
    # markdown links / images
    pg.fill('#input', 'mdlinks'); pg.click('#sendBtn'); pg.wait_for_timeout(1500)
    md = pg.locator('.msg.assistant').last.locator('.md')
    links = md.evaluate("e => [...e.querySelectorAll('a')].map(a => [a.getAttribute('rel'), a.getAttribute('target'), a.textContent])")
    check('links rel=noopener noreferrer target=_blank', len(links) == 2 and all(l[0] == 'noopener noreferrer' and l[1] == '_blank' for l in links), links)
    check('markdown image rendered as link, no <img>', md.locator('img').count() == 0 and any('고양이' in l[2] for l in links), links)
    # ---------- local-only mode ----------
    put('/persist/off'); pg.evaluate("localStorage.clear()"); pg.reload(); pg.wait_for_timeout(1000)
    if pg.is_visible('#newChat'): pg.click('#newChat'); pg.wait_for_timeout(400)
    pg.fill('#input', 'slow local'); pg.click('#sendBtn'); pg.wait_for_timeout(1200); pg.click('#sendBtn'); pg.wait_for_timeout(600)
    a = pg.locator('.msg.assistant').last
    check('local: partial kept + marker', '조각0' in a.inner_text() and a.locator('.stopped').count() == 1)
    st = pg.evaluate("JSON.parse(localStorage.getItem('llmchat.convs'))[0].messages.at(-1)")
    check('local: saved as incomplete', st.get('status') == 'incomplete' and '중지됨' not in st['content'], st)
    check('local: no error', pg.locator('.msg.error').count() == 0 and not pg.evaluate("document.querySelector('#toast').classList.contains('show')"), pg.text_content('#toast'))
    pg.reload(); pg.wait_for_timeout(900)
    openFirst(600)
    check('local: marker persists after reload', pg.locator('.msg.assistant').last.locator('.stopped').count() == 1)
    pg.fill('#input', 'after'); pg.click('#sendBtn'); pg.wait_for_timeout(1500)
    body = db()['state'].get('lastBody'); check('next request ok after stop', pg.locator('.msg.error').count() == 0)
    # non-stream stop
    pg.fill('#input', 'slownostream'); pg.click('#sendBtn'); pg.wait_for_timeout(800); pg.click('#sendBtn'); pg.wait_for_timeout(600)
    check('non-stream request aborted', not pg.evaluate("document.querySelector('#sendBtn').classList.contains('stop')") and pg.locator('.msg.error').count() == 0 and pg.locator('.msg.assistant').last.locator('.stopped').count() == 1)
    pg.wait_for_timeout(5500)
    check('late non-stream reply not rendered', 'late non-stream' not in pg.inner_text('#messages'))
    # settings / sheets under CSP
    pg.evaluate("document.querySelector('#openSettings')?.click() || document.querySelector('#settings').showModal()"); pg.wait_for_timeout(500)
    check('version label v14', 'v14' in pg.text_content('#appVersion'), pg.text_content('#appVersion'))
    pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
    # offline page under CSP
    op = ctx.new_page(); op.goto(B + '/ui/offline.html'); op.wait_for_timeout(400)
    check('offline page styled from file', op.evaluate("getComputedStyle(document.querySelector('button')).borderRadius") == '12px')
    v_off = allviol(op)
    # SW registered under CSP
    pg.wait_for_timeout(500)
    swv = pg.evaluate("navigator.serviceWorker.getRegistration().then(r => r && (r.active||r.waiting||r.installing) ? (r.active||r.waiting||r.installing).scriptURL : null)")
    check('service worker registers under CSP', bool(swv), swv)
    pg.evaluate("location.hash = '#/archive'"); pg.wait_for_timeout(600)
    v = allviol()
    check('no CSP violations (app)', not v, v)
    check('no CSP violations (offline page)', not v_off, v_off)
    check('no page errors', not errs, errs)
    put('/csp/off'); b.close()
print('ALL PASS' if not FAIL else f'{len(FAIL)} FAILED: {FAIL}')
