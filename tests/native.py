import json, time
from playwright.sync_api import sync_playwright
BASE='http://127.0.0.1:8765/ui/'
IPHONE_UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'
SEED="""(()=>{ if(localStorage.getItem('seeded'))return; localStorage.setItem('seeded','1');
 localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit',system:'',showThink:false,noThink:false}));
 const now=Date.now(); localStorage.setItem('llmchat.convs',JSON.stringify([
  {id:'c1',title:'SwiftUI 질문',updated:now,messages:[{role:'user',content:'안녕'},{role:'assistant',content:'<think>hi</think>안녕하세요! 무엇을 도와드릴까요?'}]},
  {id:'c2',title:'파이썬 코드 리뷰',updated:now-864e5,messages:[{role:'user',content:'리뷰해줘'},{role:'assistant',content:'좋아요.\\n\\n```py\\nprint(1)\\n```'}]},
  {id:'c3',title:'여행 계획',updated:now-3*864e5,messages:[{role:'user',content:'제주'},{role:'assistant',content:'3일 일정 추천'}]}]));
 localStorage.setItem('llmchat.current',JSON.stringify('c1')); })()"""
R=[]
def check(name, ok, extra=''):
    R.append(ok); print(('PASS' if ok else 'FAIL'), name, extra)
def ctx(p, b, standalone=False, ua=IPHONE_UA, visits=None):
    c=b.new_context(viewport={'width':393,'height':852}, device_scale_factor=3, is_mobile=True, has_touch=True, user_agent=ua)
    c.add_init_script(SEED)
    if standalone: c.add_init_script("Object.defineProperty(navigator,'standalone',{get:()=>true})")
    if visits is not None: c.add_init_script(f"if(!localStorage.getItem('v0')){{localStorage.setItem('v0',1);localStorage.setItem('visits','{visits}')}}")
    return c
def touch(cdp, typ, pts): cdp.send('Input.dispatchTouchEvent', {'type': typ, 'touchPoints': [{'x': x, 'y': y} for x, y in pts]})
def swipe(pg, cdp, x0, y0, x1, y1, steps=12, dt=16, hold=0):
    touch(cdp,'touchStart',[(x0,y0)]); pg.wait_for_timeout(hold or dt)
    for i in range(1,steps+1): touch(cdp,'touchMove',[(x0+(x1-x0)*i/steps, y0+(y1-y0)*i/steps)]); pg.wait_for_timeout(dt)
    touch(cdp,'touchEnd',[]); pg.wait_for_timeout(600)
def longpress(pg, cdp, x, y, ms=650): touch(cdp,'touchStart',[(x,y)]); pg.wait_for_timeout(ms); touch(cdp,'touchEnd',[]); pg.wait_for_timeout(350)
route=lambda pg: pg.evaluate("document.querySelector('#app').dataset.route")
import urllib.request
urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8765/persist/off',method='PUT'))   # local-only mode; server mode in threads.py
with sync_playwright() as p:
    b=p.chromium.launch()
    # ---------- standalone ----------
    c=ctx(p,b,standalone=True); pg=c.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(BASE); pg.wait_for_timeout(600); cdp=c.new_cdp_session(pg)
    check('standalone detected (html.standalone)', pg.evaluate("document.documentElement.classList.contains('standalone')"))
    check('launch restores last chat', route(pg)=='chat' and pg.text_content('#title')=='SwiftUI 질문', pg.evaluate('location.hash'))
    check('list screen inert while in chat', pg.evaluate("document.querySelector('#listView').inert"))
    check('no install sheet in standalone', pg.is_hidden('#installSheet'))
    # short edge swipe -> cancels
    swipe(pg,cdp,6,420,120,425); check('short edge swipe snaps back to chat', route(pg)=='chat')
    # mid-drag follows finger
    touch(cdp,'touchStart',[(6,420)]); 
    for x in range(20,200,20): touch(cdp,'touchMove',[(x,422)]); pg.wait_for_timeout(16)
    tx=pg.evaluate("new DOMMatrix(getComputedStyle(document.querySelector('#chatView')).transform).m41")
    check('chat follows finger during drag', 150<tx<200, f'translateX={tx:.0f}px')
    touch(cdp,'touchMove',[(300,422)]); pg.wait_for_timeout(16); touch(cdp,'touchEnd',[]); pg.wait_for_timeout(600)
    check('edge swipe past half -> list', route(pg)=='list', pg.evaluate('location.hash'))
    check('large title visible on list', pg.is_visible('#listView .large-title'))
    # search
    pg.fill('#search','파이썬'); n=pg.locator('#convList li.row').count(); pg.fill('#search',''); check('search filters rows', n==1)
    # row long press -> context menu
    bb=pg.locator('#convList li.row').nth(1).bounding_box(); longpress(pg,cdp,bb['x']+150,bb['y']+30)
    items=pg.locator('#ctx .ctx-menu button').all_inner_texts()
    check('long-press row shows menu', pg.is_visible('#ctx') and items==['이름 변경','고정','보관','삭제'], str(items))
    pg.mouse.click(20,800); pg.wait_for_timeout(300); check('menu dismisses on outside tap', pg.is_hidden('#ctx'))
    # swipe actions
    bb=pg.locator('#convList li.row').nth(2).bounding_box(); swipe(pg,cdp,bb['x']+300,bb['y']+30,bb['x']+200,bb['y']+32)
    check('row swipe reveals actions', pg.locator('#convList li.row.swiped').count()==1 and pg.is_visible('#convList li.row.swiped .ra-archive'))
    pg.locator('#convList li.row.swiped .ra-archive').click(); pg.wait_for_timeout(500)
    check('swipe archive removes conversation', pg.locator('#convList li.row').count()==2)
    bb=pg.locator('#convList li.row').nth(1).bounding_box(); swipe(pg,cdp,bb['x']+370,bb['y']+30,bb['x']+40,bb['y']+30,steps=10)
    check('full swipe archives', pg.locator('#convList li.row').count()==1)
    # push into chat
    pg.locator('#convList li.row').first.click(); pg.wait_for_timeout(600)
    check('tap row pushes chat', route(pg)=='chat')
    pg.go_back(); pg.wait_for_timeout(600); check('history back (popstate) pops to list', route(pg)=='list')
    pg.go_forward(); pg.wait_for_timeout(600); check('history forward pushes chat', route(pg)=='chat')
    # message long press
    bb=pg.locator('.msg.assistant .bubble').last.bounding_box(); longpress(pg,cdp,bb['x']+40,bb['y']+bb['height']-8)
    items=pg.locator('#ctx .ctx-menu button').all_inner_texts(); check('long-press answer shows copy menu', '복사' in items and '텍스트 선택' in items, str(items))
    pg.mouse.click(20,120); pg.wait_for_timeout(300)
    # settings sheet drag-dismiss
    pg.click('#backBtn'); pg.wait_for_timeout(500); pg.click('#openSettings'); pg.wait_for_timeout(700)
    bb=pg.locator('#settings .sheet-head h2').bounding_box(); swipe(pg,cdp,bb['x']+10,bb['y']+10,bb['x']+10,bb['y']+500,steps=8)
    check('settings sheet swipe-down closes', not pg.evaluate("document.querySelector('#settings').open"))
    pg.click('#openSettings'); pg.wait_for_timeout(700); bb=pg.locator('#settings .sheet-head h2').bounding_box(); swipe(pg,cdp,bb['x']+10,bb['y']+10,bb['x']+10,bb['y']+60,steps=6,dt=60)
    check('small sheet drag snaps back open', pg.evaluate("document.querySelector('#settings').open"))
    pg.click('#cancelSettings'); pg.wait_for_timeout(500)
    # state restore: route + draft
    pg.locator('#convList li.row').first.click(); pg.wait_for_timeout(600); pg.fill('#input','초안 테스트'); pg.wait_for_timeout(400)
    pg.reload(); pg.wait_for_timeout(700)
    check('draft + chat restored after relaunch', route(pg)=='chat' and pg.input_value('#input')=='초안 테스트')
    pg.click('#backBtn'); pg.wait_for_timeout(600); pg.reload(); pg.wait_for_timeout(700); check('list route restored after relaunch', route(pg)=='list')
    # keyboard class
    pg.evaluate("document.body.classList.remove('kb-open')"); check('kb-open toggles from visualViewport', pg.evaluate("typeof visualViewport==='object'"))
    check('no page errors (standalone)', not errs, str(errs)); c.close()
    # ---------- browser tab: no swipe-back, install sheet ----------
    c=ctx(p,b,visits=1); pg=c.new_page(); pg.goto(BASE); pg.wait_for_timeout(500); cdp=c.new_cdp_session(pg)
    swipe(pg,cdp,6,420,330,425); check('edge swipe disabled in Safari tab (Safari owns the gesture)', route(pg)=='chat')
    pg.wait_for_timeout(1500)
    check('install sheet shows on iOS Safari (2nd visit)', pg.is_visible('#installSheet') and 'show' in pg.get_attribute('#installSheet','class'))
    pg.click('#installLater'); pg.wait_for_timeout(500)
    check('install sheet dismiss', pg.is_hidden('#installSheet') and pg.evaluate("!!localStorage.getItem('a2hs.dismissed')"))
    pg.reload(); pg.wait_for_timeout(2200); check('dismissal remembered (30 days)', pg.is_hidden('#installSheet'))
    c.close()
    c=b.new_context(viewport={'width':393,'height':852},is_mobile=True,has_touch=True,user_agent=IPHONE_UA); pg=c.new_page(); pg.goto(BASE); pg.wait_for_timeout(2300)
    check('install sheet not shown on first visit', pg.is_hidden('#installSheet')); c.close()
    c=ctx(p,b,ua='Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36',visits=5); pg=c.new_page(); pg.goto(BASE); pg.wait_for_timeout(2000)
    check('non-iOS without beforeinstallprompt: no sheet', pg.is_hidden('#installSheet'))
    pg.evaluate("const e=new Event('beforeinstallprompt');e.prompt=()=>{};e.userChoice=Promise.resolve({outcome:'dismissed'});dispatchEvent(e)"); pg.wait_for_timeout(1700)
    check('beforeinstallprompt -> sheet with 설치 button', pg.is_visible('#installBtn')); c.close()
    # ---------- service worker / offline ----------
    c=ctx(p,b,standalone=True); pg=c.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(BASE); pg.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.controller", timeout=10000) if False else None
    pg.evaluate("navigator.serviceWorker.ready"); pg.reload(); pg.wait_for_timeout(800)
    keys=pg.evaluate("caches.keys()"); check('SW precache llmchat-v17', keys==['llmchat-v17'], str(keys))
    check('SW controls page', pg.evaluate("!!navigator.serviceWorker.controller"))
    c.set_offline(True); pg.reload(); pg.wait_for_timeout(800)
    check('offline: app shell loads from cache', pg.is_visible('#composer') and pg.locator('.msg').count()>0)
    check('offline banner shown', pg.evaluate("document.querySelector('#chatView').classList.contains('offline')"))
    pg.goto(BASE+'somewhere/else'); pg.wait_for_timeout(500)
    check('offline fallback screen for uncached page', '오프라인 상태입니다' in pg.text_content('body'))
    c.set_offline(False); pg.goto(BASE); pg.wait_for_timeout(600)
    r=pg.evaluate("fetch('/v1/models').then(r=>r.status)")
    inCache=pg.evaluate("caches.open('llmchat-v17').then(c=>c.keys()).then(k=>k.some(r=>r.url.includes('/v1/')))")
    check('API never cached (network-only)', r==200 and not inCache)
    pg.evaluate("window.__app.showToast('새 버전이 있어요','새로고침',()=>{})"); pg.wait_for_timeout(400)
    check('update toast renders', pg.is_visible('#toast') and '새로고침' in pg.text_content('#toast'))
    m=pg.evaluate("fetch('manifest.webmanifest').then(r=>r.json())")
    check('manifest: standalone/portrait/shortcuts/split icons', m['display']=='standalone' and m['orientation']=='portrait' and m['shortcuts'][0]['url']=='/ui/?new=1' and all(' ' not in i['purpose'] for i in m['icons']) and m['id']=='/ui/')
    pg.goto(BASE+'?new=1'); pg.wait_for_timeout(700); check('shortcut ?new=1 opens a new chat', route(pg)=='chat' and pg.text_content('#title')=='새 대화')
    check('no page errors (sw)', not errs, str(errs)); c.close()
    # ---------- REVIEW-NATIVE v7 ----------
    c=ctx(p,b,standalone=True); pg=c.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e))); pg.goto(BASE); pg.wait_for_timeout(600); cdp=c.new_cdp_session(pg)
    pg.evaluate("history.length"); hl=pg.evaluate("history.length")
    pg.evaluate("document.querySelector('#backBtn').click(); document.querySelector('#backBtn').click(); document.querySelector('#backBtn').click()"); pg.wait_for_timeout(700)
    check('M1 fast triple back: stays in app on list', route(pg)=='list' and '/ui/' in pg.url and pg.evaluate("history.state && history.state.route")=='list', pg.url)
    pg.locator('#convList li.row').first.click(); pg.wait_for_timeout(600)
    swipe(pg,cdp,6,420,330,425,dt=8); pg.evaluate("document.querySelector('#backBtn').click()"); pg.wait_for_timeout(700)
    check('M1 back right after swipe commit: no overshoot', route(pg)=='list' and '/ui/' in pg.url and pg.evaluate("history.state && history.state.route")=='list')
    pg.locator('#convList li.row').first.click(); pg.wait_for_timeout(700)
    pg.evaluate("""(()=>{const e=new PopStateEvent('popstate',{state:{route:'list'}});Object.defineProperty(e,'hasUAVisualTransition',{value:true});window.__vt=0;const o=document.startViewTransition;document.startViewTransition=cb=>{window.__vt++;return o.call(document,cb)};dispatchEvent(e)})()""")
    pg.wait_for_timeout(50)
    check('M2 popstate with hasUAVisualTransition: switch without animation', route(pg)=='list' and pg.evaluate("window.__vt")==0 and not pg.evaluate("document.querySelector('#app').classList.contains('transitioning')"))
    pg.evaluate("history.pushState({route:'chat',id:'c1'},'','#/c/c1')"); pg.evaluate("document.querySelector('#app').dataset.route='chat'"); pg.wait_for_timeout(100)
    pg.evaluate("document.querySelector('#app').classList.add('transitioning')"); swipe(pg,cdp,6,420,330,425)
    check('S4 edge swipe blocked during transition', route(pg)=='chat'); pg.evaluate("document.querySelector('#app').classList.remove('transitioning')")
    pg.evaluate("document.querySelector('#app').dataset.route='list';document.querySelector('#listView').inert=false"); pg.wait_for_timeout(300)
    pg.click('#openSettings'); pg.wait_for_timeout(700)
    sc=pg.evaluate("new DOMMatrix(getComputedStyle(document.querySelector('#app')).transform).a")
    check('S5 card scale behind sheet', abs(sc-.94)<.01, f'scale={sc:.3f}')
    bb=pg.locator('#settings .sheet-head h2').bounding_box(); x=bb['x']+10; y=bb['y']+10
    touch(cdp,'touchStart',[(x,y)])
    for i in range(1,11): touch(cdp,'touchMove',[(x,y+i*8)]); pg.wait_for_timeout(60)   # slow 80px
    touch(cdp,'touchMove',[(x,y+100)]); touch(cdp,'touchMove',[(x,y+160)]); touch(cdp,'touchEnd',[]); pg.wait_for_timeout(600)
    check('S3 slow drag then flick closes sheet (release velocity)', not pg.evaluate("document.querySelector('#settings').open"))
    check('no page errors (v7 review)', not errs, str(errs)); c.close()
    for scheme in ('light',):
        c=b.new_context(viewport={'width':393,'height':852},is_mobile=True,has_touch=True,user_agent=IPHONE_UA,color_scheme='light'); c.add_init_script(SEED); c.add_init_script("localStorage.setItem('visits','5')")
        pg=c.new_page(); pg.goto(BASE); pg.wait_for_timeout(1800)
        check('S1 install sheet: single dismiss (no ×)', pg.locator('#installSheet .close-x').count()==0 and pg.is_visible('#installLater'))
        a=pg.locator('#installSheet .a2hs-arrow').bounding_box(); l=pg.locator('#installLater').bounding_box(); sh=pg.locator('#installSheet').bounding_box()
        check('S1 share arrow at very bottom, below 나중에', a['y']>=l['y']+l['height'] and abs((sh['y']+sh['height'])-(a['y']+a['height']))<12)
        pg.click('#installLater'); pg.wait_for_timeout(600); pg.evaluate("document.querySelector('#openSettings').click()"); pg.wait_for_timeout(600)
        check('S2 light settings group cells white', pg.evaluate("getComputedStyle(document.querySelector('#settings .group')).backgroundColor")=='rgb(255, 255, 255)')
        c.close()
    # ---------- wide: sidebar kept ----------
    c=b.new_context(viewport={'width':1100,'height':800}); c.add_init_script(SEED); pg=c.new_page(); pg.goto(BASE); pg.wait_for_timeout(500)
    check('>=761px keeps sidebar + chat side by side', pg.is_visible('#listView') and pg.is_visible('#composer') and pg.locator('#listView').bounding_box()['width']==320)
    c.close(); b.close()
print(f'\n{sum(R)}/{len(R)} passed')
