"""1.0.2: every mutating request (POST/PUT/PATCH/DELETE) sends X-Eve-Request: 1; with a body it must be Content-Type: application/json."""
from assets_common import source_path
from playwright.sync_api import sync_playwright
import urllib.request, json, re, pathlib
B = 'http://127.0.0.1:'+__import__('os').environ.get('EVE_PORT','8765')
def put(path):
    urllib.request.urlopen(urllib.request.Request(B + path, method='PUT'))
FAIL = []
def check(name, ok, info=''):
    print(('PASS ' if ok else 'FAIL ') + name + (' ' + str(info) if info and not ok else ''))
    if not ok: FAIL.append(name)

# static: no raw mutating fetch bypasses headers(method); no FormData/text/plain/sendBeacon
src = source_path(pathlib.Path(__file__).resolve().parent.parent.joinpath('app.js')).read_text()
check('no FormData / text/plain / sendBeacon / XHR', not re.search(r'FormData|text/plain|sendBeacon|XMLHttpRequest', src))
raw = [m.start() for m in re.finditer(r"\bfetch\(", src)]
bad = [src[i:i+300] for i in raw if re.search(r"method:\s*'(POST|PUT|PATCH|DELETE)'", src[i:i+300]) and "headers('" not in src[i:i+300]]
check('raw mutating fetch uses headers(method)', not bad, bad)

with sync_playwright() as p:
    b = p.chromium.launch()
    put('/auth/on'); put('/reset'); put('/db/reset'); put('/persist/on'); put('/webdisabled/off')
    ctx = b.new_context(viewport={'width': 390, 'height': 844})
    pg = ctx.new_page(); seen = []
    pg.on('request', lambda r: seen.append((r.method, r.url, r.headers, r.post_data)) if r.method in ('POST','PUT','PATCH','DELETE') and '/v1/' in r.url else None)
    pg.goto(B + '/ui/'); pg.wait_for_timeout(800)
    # message send (POST /v1/chat/completions)
    pg.evaluate("location.hash='#/c/new'"); pg.wait_for_timeout(300)
    if pg.is_visible('#tInput'): pg.evaluate("__app.newChat()"); pg.wait_for_timeout(300)
    pg.fill('#input', 'hello'); pg.click('#sendBtn'); pg.wait_for_timeout(2500)
    # feedback PUT/DELETE, thread PATCH/DELETE, import POST via the outbox/api path
    pg.evaluate("""localStorage.setItem('llmchat.outbox', JSON.stringify([
      {op:'feedback',key:'f1',payload:{id:'m1',rating:'down',reasons:['other'],comment:'x'},tries:0,nextAt:0},
      {op:'feedback',key:'f2',payload:{id:'m2',rating:null},tries:0,nextAt:0},
      {op:'patch',key:'p1',payload:{id:'t1',patch:{title:'new'}},tries:0,nextAt:0},
      {op:'archive',key:'a1',payload:{id:'t2'},tries:0,nextAt:0}]))""")
    pg.reload(); pg.wait_for_timeout(2500)
    pg.evaluate("fetch('/v1/threads/import',{method:'POST'}).catch(()=>{})")  # sanity: raw fetch lacks header -> must be detected
    pg.wait_for_timeout(300)
    probe = [s for s in seen if s[1].endswith('/v1/threads/import') and 'x-eve-request' not in s[2]]
    check('detector sees a header-less request', len(probe) == 1)
    app = [s for s in seen if s not in probe]
    want = {('POST','/v1/chat/completions'),('PUT','/v1/messages/m1/feedback'),('DELETE','/v1/messages/m2/feedback'),('PATCH','/v1/threads/t1'),('DELETE','/v1/threads/t2')}
    got = {(m, re.sub(r'^https?://[^/]+', '', u).split('?')[0]) for m, u, h, d in app}
    check('covered all mutating paths', want <= got, want - got)
    for m, u, h, d in app:
        check(f'{m} {u} X-Eve-Request: 1', h.get('x-eve-request') == '1', h)
        if d: check(f'{m} {u} body is application/json', h.get('content-type','').startswith('application/json') and json.loads(d) is not None, h.get('content-type'))
    b.close()
print('FAILED:', FAIL) if FAIL else print('ALL PASS')
