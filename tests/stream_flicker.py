"""v15: streaming must not re-render completed blocks or re-trigger animations per token."""
from playwright.sync_api import sync_playwright
import urllib.request, json, os
from assets_common import full_csp, watch_csp
B = 'http://127.0.0.1:'+__import__('os').environ.get('EVE_PORT','8765')+''
def put(path, body=None):
    request = urllib.request.Request(B + path, method='PUT', data=None if body is None else json.dumps(body).encode(), headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(request))
FAIL = []
def check(name, ok, info=''):
    print(('PASS ' if ok else 'FAIL ') + name + (' ' + str(info) if info and not ok else ''))
    if not ok: FAIL.append(name)
with full_csp(), sync_playwright() as p:
    engine = p.webkit if os.environ.get('EVE_ENGINE') == 'webkit' else p.chromium
    b = engine.launch(); put('/auth/on'); put('/reset'); put('/db/reset'); put('/persist/on')
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, service_workers='block'); watch_csp(ctx)
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(B + '/ui/'); pg.bring_to_front(); pg.wait_for_timeout(800)
    pg.evaluate("location.hash='#/c/new'"); pg.wait_for_timeout(300)
    if pg.is_visible('#tInput'): pg.evaluate("__app.newChat()"); pg.wait_for_timeout(400)
    pg.evaluate("""(()=>{window.__st={removedStable:0,anim:0,msgAnim:0,scrollJumps:0};
      const box=document.querySelector('#messages');
      new MutationObserver(ms=>{for(const m of ms){if(m.target.classList&&m.target.classList.contains('stable'))window.__st.removedStable+=m.removedNodes.length;}}).observe(box,{childList:true,subtree:true});
      box.addEventListener('animationstart',e=>{if(e.target.closest('.md')){(window.__st.names=window.__st.names||[]).push(e.animationName+(e.pseudoElement||'')); if(!e.pseudoElement)window.__st.anim++;} if(e.target.classList.contains('msg'))window.__st.msgAnim++;});})()""")
    pg.fill('#input', 'long stream'); pg.click('#sendBtn')
    pg.wait_for_function("() => document.querySelectorAll('.md.cursor .stable > *').length >= 1")
    # mid-stream: blocks appended, not replaced
    mid = pg.evaluate("document.querySelectorAll('.md.cursor .stable > *').length")
    pg.wait_for_timeout(2500)
    st = pg.evaluate("window.__st")
    check('completed blocks accumulated during stream', mid >= 1, mid)
    check('completed blocks never removed/re-created while streaming', st['removedStable'] == 0, st)
    check('no animations re-triggered inside answer', st['anim'] == 0, st)
    check('message entry animation ran at most twice (user+assistant)', st['msgAnim'] <= 2, st)
    check('final answer rendered', 'Para 7' in pg.locator('.msg.assistant .md').last.inner_text())
    # scroll: user scrolls up mid-stream -> no forced jump back
    pg.fill('#input', 'slow scroll'); pg.click('#sendBtn'); pg.wait_for_timeout(2500)
    pg.evaluate("document.querySelector('#messages').scrollTop = 0"); pg.wait_for_timeout(150)
    pg.evaluate("document.querySelector('#messages').dispatchEvent(new Event('scroll'))"); pg.wait_for_timeout(1500)
    top = pg.evaluate("document.querySelector('#messages').scrollTop")
    check('no auto-scroll when user is not pinned to bottom', top < 50, top)
    pg.click('#sendBtn'); pg.wait_for_timeout(500)
    # Explicitly exercise monotonic appends followed by a shorter eve.snapshot.
    put('/pro/set', {'atScript':[
        {'d':.1,'text':'첫 문단\n\n두 번째\n\n초안'},
        {'d':.8,'text':' 꼬리\n\n셋째'},
        {'d':.8,'name':'eve.snapshot','ev':{'content':'짧은 교체','status':'generating'}},
        {'d':.8,'text':' 끝\n\n마지막'}, {'d':.8,'text':''},
    ]})
    pg.evaluate('__app.newChat()'); pg.wait_for_timeout(300)
    pg.fill('#input', 'atscript block replacement'); pg.click('#sendBtn')
    pg.wait_for_function("() => document.querySelectorAll('.md.cursor .stable > p').length === 2")
    pg.evaluate("window.__firstBlock = document.querySelector('.md.cursor .stable > p'); window.__streamBody = document.querySelector('.md.cursor')")
    pg.wait_for_function("() => document.querySelectorAll('.md.cursor .stable > p').length === 3")
    check('appending another completed block preserves the first DOM node', pg.evaluate("window.__firstBlock === document.querySelector('.md.cursor .stable > p')"))
    pg.wait_for_function("() => document.querySelector('.md.cursor .tail')?.textContent === '짧은 교체'")
    check('shorter snapshot clears previous stable blocks in the same body', pg.evaluate("document.querySelector('.md.cursor') === window.__streamBody && !window.__firstBlock.isConnected && document.querySelector('.md.cursor .stable').children.length === 0"))
    pg.wait_for_function("() => document.querySelector('.md.cursor .stable')?.textContent === '짧은 교체 끝'")
    check('blocks continue correctly after a shrinking snapshot', pg.evaluate("document.querySelectorAll('.md.cursor .stable > p').length === 1 && document.querySelector('.md.cursor .tail').textContent === '마지막'"))
    pg.wait_for_function("() => !document.querySelector('#sendBtn').classList.contains('stop')")
    check('final render contains only replacement text', pg.locator('.msg.assistant .md').last.inner_text() == '짧은 교체 끝\n\n마지막')
    check('no full CSP violations', not pg.evaluate('window.__csp || []'))
    check('no page errors', not errs, errs)
    b.close()
print('FAILED:', FAIL) if FAIL else print('ALL PASS')
