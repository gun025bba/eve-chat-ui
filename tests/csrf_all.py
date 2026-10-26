# CSRF rule e2e (1.1.0): every POST/PUT/PATCH/DELETE the app sends — old paths (send, feedback, thread edit/archive,
# import, outbox replay) and 선톡 paths — carries X-Eve-Request: 1, the exact Origin, and JSON Content-Type when it has a body.
import json, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
M = 'http://127.0.0.1:'+__import__('os').environ.get('EVE_PORT','8765')+''
def req(method, path, body=None, headers=None):
    r = urllib.request.Request(M + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers=headers or {'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r) as f: t = f.read(); return f.status, (json.loads(t) if t else None)
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b'null')
put = lambda p, b=None: req('PUT', p, b)[1]
R = []
def check(name, ok, extra=''): R.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, extra)
SETTINGS = "localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit',system:'',showThink:false,noThink:false}));"
put('/auth/on'); put('/persist/on'); put('/db/reset'); put('/fail/clear'); put('/pro/reset')
# server side of the rule (mock mirrors the gateway): missing header / wrong Origin / text/plain → 403 {error_code:'invalid'}
st, b = req('POST', '/v1/threads', {'title': 'x'}, {'Content-Type': 'application/json', 'Origin': M})
check('no X-Eve-Request → 403 invalid', st == 403 and b == {'error_code': 'invalid'}, [st, b])
st, b = req('POST', '/v1/threads', {'title': 'x'}, {'Content-Type': 'application/json', 'Origin': 'https://evil.example', 'X-Eve-Request': '1'})
check('foreign Origin → 403', st == 403, st)
st, b = req('POST', '/v1/threads', {'title': 'x'}, {'Content-Type': 'text/plain', 'Origin': M, 'X-Eve-Request': '1'})
check('text/plain body → 403', st == 403, st)
st, b = req('POST', '/v1/threads', {'title': 'x'}, {'Content-Type': 'application/json', 'Origin': M, 'X-Eve-Request': '1'})
check('header + Origin + JSON → allowed', st == 201, st)
put('/db/reset'); put('/mut/reset')
seed = put('/pro/seed', {'title': '선톡', 'proactive': ['읽어 주세요']})
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 390, 'height': 844})
    ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "}")
    pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(M + '/ui/#/'); pg.wait_for_timeout(1500)
    pg.click('#newChat'); pg.wait_for_timeout(300); pg.fill('#input', 'hello'); pg.click('#sendBtn'); pg.wait_for_timeout(3500)   # POST /v1/chat/completions
    pg.locator('.msg.assistant .fb.up').last.click(); pg.wait_for_timeout(1200)                                                       # PUT feedback (outbox)
    tid = pg.evaluate('__app.state().currentId')
    ctx.set_offline(True); pg.evaluate("window.dispatchEvent(new Event('offline'))")
    pg.evaluate(f"""__app.enqueue('patch','patch:{tid}',{{id:'{tid}',patch:{{title:'바뀐 제목'}}}});
                    __app.enqueue('read','read:{seed['msgs'][0]}',{{id:'{seed['msgs'][0]}'}});
                    __app.enqueue('readThread','readThread:{seed['thread']}',{{id:'{seed['thread']}'}});""")
    pg.wait_for_timeout(500)
    ctx.set_offline(False); pg.evaluate("window.dispatchEvent(new Event('online'))"); pg.wait_for_timeout(3000)   # outbox replay
    pg.evaluate(f"__app.enqueue('archive','archive:{tid}',{{id:'{tid}'}})"); pg.wait_for_timeout(2000)                # DELETE (body-less)
    def home():
        pg.goto(M + '/ui/#/'); pg.reload(); pg.wait_for_timeout(1300)
        if pg.evaluate("document.getElementById('app').dataset.route") == 'chat': pg.evaluate('history.back()'); pg.wait_for_timeout(400)
    home(); pg.click('#newChat'); pg.wait_for_timeout(300); pg.fill('#input', 'confirm 치과'); pg.click('#sendBtn'); pg.wait_for_timeout(2500)
    pg.locator('.confirm-card .cc-primary').last.click(); pg.wait_for_timeout(1200)                                  # POST approve
    home()
    pg.click('#openSettings'); pg.wait_for_timeout(700); pg.click('label:has(#sProactive)'); pg.wait_for_timeout(800)  # PATCH settings
    mut = req('PUT', '/__mut')[1]
    seen = {(x['m'], x['p'].split('/')[2] if x['p'].count('/') > 1 else x['p']) for x in mut}
    kinds = {(x['m'], x['p']) for x in mut}
    def has(m, frag): return any(x['m'] == m and frag in x['p'] for x in mut)
    for m, frag in [('POST', '/v1/chat/completions'), ('PUT', '/feedback'), ('PATCH', '/v1/threads/'), ('DELETE', '/v1/threads/'),
                    ('POST', '/v1/messages/'), ('POST', '/read'), ('POST', '/reissue'), ('POST', '/approve'), ('PATCH', '/v1/settings')]:
        check(f'covered {m} …{frag}', has(m, frag))
    bad = [x for x in mut if not x['ok']]
    check(f'all {len(mut)} mutating requests pass the rule', mut and not bad, bad[:3])
    check('every one sent X-Eve-Request: 1', all(x['xer'] == '1' for x in mut))
    check('bodies always application/json', all((x['ct'] or '').startswith('application/json') for x in mut if x['body']))
    # same-origin only: base on another origin → approve disabled with a message, no token/decision call leaves the page
    FOREIGN = 'http://localhost:' + M.rsplit(':', 1)[1]          # different origin (host differs), same mock behind it
    x2 = b.new_context(viewport={'width': 390, 'height': 844})
    x2.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);localStorage.setItem('llmchat.settings',JSON.stringify({base:'" + FOREIGN + "',model:'m',system:'',showThink:false,noThink:false}));}")
    sent = []
    def foreign(route):
        r = route.request; sent.append((r.method, r.url))
        if r.method == 'OPTIONS': return route.fulfill(status=204, headers={'Access-Control-Allow-Origin': M, 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*', 'Access-Control-Allow-Credentials': 'true'})
        resp = route.fetch(url=r.url.replace(FOREIGN, M), headers=dict(r.headers, origin=M))
        route.fulfill(response=resp, headers=dict(resp.headers, **{'access-control-allow-origin': M, 'access-control-allow-credentials': 'true'}))
    x2.route(FOREIGN + '/**', foreign)
    q = x2.new_page(); q.on('pageerror', lambda e: errs.append(str(e)))
    put('/pro/reset'); sx = put('/pro/seed', {'title': '다른 서버', 'actions': [{'action_id': '01JACT0000000000000000000X', 'tool': 'calendar_create_event', 'summary': '일정', 'scopes': ['calendar.write'], 'payload_view': {'제목': 'x'}, 'payload_hash': 'sha256:x', 'expires_at': '2099-01-01T00:00:00Z', 'provenance': {'actor': 'user'}}]})
    q.goto(M + '/ui/#/'); q.reload(); q.wait_for_timeout(1500)
    if q.evaluate("document.getElementById('app').dataset.route") == 'chat': q.evaluate('history.back()'); q.wait_for_timeout(400)
    q.locator(f'#convList li.row[data-id="{sx["thread"]}"]').first.click(); q.wait_for_timeout(1500)
    cx = q.locator('.confirm-card[data-aid="01JACT0000000000000000000X"]')
    check('cross-origin base: card shown', cx.count() == 1, q.evaluate('__app.state()'))
    check('cross-origin base: approve + reject disabled', cx.locator('.cc-primary').is_disabled() and cx.locator('.cc-secondary').is_disabled())
    check('cross-origin base: clear message', '서버 주소가 이 앱과 다른 곳' in cx.inner_text(), cx.inner_text())
    cx.locator('.cc-primary').click(force=True); q.wait_for_timeout(800)
    check('cross-origin base: no reissue/approve/actions call', not any(k in u for _, u in sent for k in ('/reissue', '/approve', '/reject', '/v1/actions')), [u for _, u in sent if '/v1/actions' in u])
    x2.close()
    check('no page errors', not errs, errs)
    b.close()
print('ALL PASS' if all(R) else 'SOME FAIL'); raise SystemExit(0 if all(R) else 1)
