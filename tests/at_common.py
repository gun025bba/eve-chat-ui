# AUTO-TOOLS-SPEC §13 shared helpers: mock scripts (PRO['atScript']), a page factory, the checks
from playwright.sync_api import sync_playwright
import urllib.request, json, os, re
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
def put(path, body=None):
    r = urllib.request.Request(B + path, method='PUT', data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(r))
def db(): return json.load(urllib.request.urlopen(B + '/__db'))
FAIL = []
def check(name, ok, info=''):
    print(('PASS ' if ok else 'FAIL ') + name + (' ' + str(info) if info and not ok else ''))
    if not ok: FAIL.append(name)
def done():
    print('FAILED:', FAIL) if FAIL else print('ALL PASS')
SYS = {'proactive_available': True, 'tools_available': True, 'memory_read_only': False, 'memory_available': True}
def server(auto=None, tools_auto=None):
    """a clean mock: server mode, persistence on; auto = system.auto_select_available (None → field absent)"""
    put('/auth/on'); put('/reset'); put('/db/reset'); put('/pro/reset'); put('/persist/on'); put('/webdisabled/off')
    s = dict(SYS); 
    if auto is not None: s['auto_select_available'] = auto
    put('/pro/set', {'system': s, 'toolsAuto': tools_auto})
def src(n, dom='example.com', title=None, **kw): return dict({'n': n, 'title': title or f'출처 {n}', 'url': f'https://{dom}/p{n}', 'domain': dom, 'fetched': False}, **kw)
def call(id='t1', tool='web_search', q='카카오 오늘 소식', by='model', url=None, rnd=1, **kw):
    a = {'url': url} if url is not None else {'query': q}
    o = {'object': 'chat.completion.tool_call', 'id': id, 'tool': tool, 'args': a, 'round': rnd}
    if by: o['selected_by'] = by
    return dict(o, **kw)
def result(id='t1', tool='web_search', status='ok', sources=None, **kw): return dict({'object': 'chat.completion.tool_result', 'id': id, 'tool': tool, 'status': status, 'sources': sources or []}, **kw)
def S(ev, d=0, **kw): return dict({'d': d, 'ev': ev}, **kw)
def T(text, d=0): return {'d': d, 'text': text}
def script(items, sources=None): put('/pro/set', {'atScript': items, 'atSources': sources or []})
def launch(b, scheme='dark', init='', reduced=False, w=390, mobile=False):
    ctx = b.new_context(viewport={'width': w, 'height': 844}, **({'device_scale_factor': 2, 'is_mobile': True, 'has_touch': True} if mobile else {}), color_scheme=scheme, reduced_motion='reduce' if reduced else 'no-preference', locale='ko-KR', timezone_id='Asia/Seoul')
    ctx.add_init_script("localStorage.setItem('eve.mem.introSeen','1');" + init)
    pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.errs = errs
    pg.goto(B + '/ui/'); pg.wait_for_timeout(900)
    pg.evaluate("location.hash='#/c/new'"); pg.wait_for_timeout(300)
    if pg.is_visible('#tInput'): pg.evaluate("__app.newChat()"); pg.wait_for_timeout(400)
    return ctx, pg
def fresh_chat(pg):
    pg.evaluate("__app.newChat()"); pg.wait_for_timeout(300)
def send(pg, text='atscript 질문'):
    if not text.startswith('atscript'): text = text + '\u2063'   # invisible marker the mock keys on (a plain question text stays readable in screenshots)
    pg.fill('#input', text); pg.click('#sendBtn')
def tstat(pg): return pg.evaluate("(()=>{const e=[...document.querySelectorAll('.msg.assistant .tstat')].pop();return e?{r1:(e.querySelector('.t1 span.on')||{}).textContent||'',r2:e.querySelector('.row2').hidden?'':((e.querySelector('.t2 span.on')||{}).textContent||''),n:document.querySelectorAll('.tstat').length}:null})()")
def wait_tstat(pg, text, ms=7000):
    try: pg.wait_for_function("t=>{const e=[...document.querySelectorAll('.msg.assistant .tstat')].pop();return !!e&&[...e.querySelectorAll('.tw span.on')].some(s=>s.textContent.includes(t))}", arg=text, timeout=ms); return True
    except Exception: return False
def settle(pg, ms=9000):
    try: pg.wait_for_function("()=>!document.querySelector('#sendBtn.stop')&&!document.querySelector('.msg.assistant .tline')&&!![...document.querySelectorAll('.msg.assistant')].pop()?.querySelector('.actions')", timeout=ms); pg.wait_for_timeout(350); return True
    except Exception: return False
