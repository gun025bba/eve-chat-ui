"""v15: streaming must not re-render completed blocks or re-trigger animations per token."""
from playwright.sync_api import sync_playwright
import urllib.request, json
B = 'http://127.0.0.1:'+__import__('os').environ.get('EVE_PORT','8765')+''
def put(path):
    return json.load(urllib.request.urlopen(urllib.request.Request(B + path, method='PUT')))
FAIL = []
def check(name, ok, info=''):
    print(('PASS ' if ok else 'FAIL ') + name + (' ' + str(info) if info and not ok else ''))
    if not ok: FAIL.append(name)
with sync_playwright() as p:
    b = p.chromium.launch(); put('/auth/on'); put('/reset'); put('/db/reset'); put('/persist/on'); put('/csp/off')
    pg = b.new_page(viewport={'width': 390, 'height': 844}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(B + '/ui/'); pg.wait_for_timeout(800)
    pg.evaluate("location.hash='#/c/new'"); pg.wait_for_timeout(300)
    if pg.is_visible('#tInput'): pg.evaluate("__app.newChat()"); pg.wait_for_timeout(400)
    pg.evaluate("""(()=>{window.__st={removedStable:0,anim:0,msgAnim:0,scrollJumps:0};
      const box=document.querySelector('#messages');
      new MutationObserver(ms=>{for(const m of ms){if(m.target.classList&&m.target.classList.contains('stable'))window.__st.removedStable+=m.removedNodes.length;}}).observe(box,{childList:true,subtree:true});
      box.addEventListener('animationstart',e=>{if(e.target.closest('.md')){(window.__st.names=window.__st.names||[]).push(e.animationName+(e.pseudoElement||'')); if(!e.pseudoElement)window.__st.anim++;} if(e.target.classList.contains('msg'))window.__st.msgAnim++;});})()""")
    pg.fill('#input', 'long stream'); pg.click('#sendBtn'); pg.wait_for_timeout(1200)
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
    check('no page errors', not errs, errs)
    b.close()
print('FAILED:', FAIL) if FAIL else print('ALL PASS')
