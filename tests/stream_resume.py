# 1.1.2 stream resume (ui-api-contract §3.8, eve-serving PR #22) e2e against mock.py
import json, urllib.request
from playwright.sync_api import sync_playwright
M='http://127.0.0.1:'+__import__('os').environ.get('EVE_PORT','8765'); BASE=M+'/ui/'
def req(method, path, body=None):
    r=urllib.request.Request(M+path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(r) as f: t=f.read(); return json.loads(t) if t else None
db=lambda: req('GET','/__db')
R=[]
def check(name, ok, extra=''): R.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, extra)
SETTINGS="localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit',system:'',showThink:false,noThink:false}));"
HIDE="Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>'hidden'});document.dispatchEvent(new Event('visibilitychange'))"
SHOW="Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>'visible'});document.dispatchEvent(new Event('visibilitychange'))"
req('PUT','/auth/on'); req('PUT','/persist/on'); req('PUT','/db/reset'); req('PUT','/fail/clear'); req('PUT','/pro/set',{'snapOnly':False})
errs=[]
def newchat(pg):
    pg.goto(BASE+'#/'); pg.wait_for_timeout(700); pg.click('#newChat'); pg.wait_for_timeout(300)
def last_asst(pg): return pg.locator('.msg.assistant').last
with sync_playwright() as p:
    b=p.chromium.launch(); c=b.new_context(viewport={'width':393,'height':852}, is_mobile=True, has_touch=True)
    c.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);"+SETTINGS+"}")
    pg=c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(BASE+'#/'); pg.wait_for_timeout(1200)
    # 1) disconnect while hidden → '답변 불러오는 중', no error → visible → resume with Last-Event-ID
    newchat(pg); pg.fill('#input','detachcut 안녕'); pg.click('#sendBtn'); pg.wait_for_timeout(300)
    pg.evaluate(HIDE); pg.wait_for_timeout(1500)
    check('hidden + cut: no error shown', pg.locator('.msg.error').count()==0)
    check('hidden + cut: 답변 불러오는 중', '답변 불러오는 중' in last_asst(pg).inner_text(), last_asst(pg).inner_text())
    pg.evaluate(SHOW); pg.wait_for_timeout(4500)
    t=last_asst(pg).inner_text()
    check('resumed reply complete', all(f'A{k}' in t for k in range(10)) and t.count('A0')==1, t)
    rs=db()['state'].get('resumes',[]); check('resume used Last-Event-ID > 0', rs and int(rs[-1]['lei'] or 0)>0, rs[-1:])
    mid=rs[-1]['mid']; dmid=pg.evaluate("[...document.querySelectorAll('.msg.assistant')].pop().dataset.mid")
    check('message id from eve.meta kept', dmid==mid, [dmid, mid])
    check('note removed after completion', last_asst(pg).locator('.msg-note').count()==0 and pg.locator('.msg.error').count()==0)
    # 2) regenerate reuses the same message_id (also cut → resume)
    n0=pg.locator('.msg.assistant').count(); last_asst(pg).locator('.actions .r').click(); pg.wait_for_timeout(5500)
    rs=db()['state'].get('resumes',[]); t=last_asst(pg).inner_text()
    check('regenerate: same message_id resumed', rs[-1]['mid']==mid and pg.evaluate("[...document.querySelectorAll('.msg.assistant')].pop().dataset.mid")==mid, rs[-1])
    check('regenerate: one reply, complete', pg.locator('.msg.assistant').count()==n0 and 'A9' in t, t)
    # 3) snapshot (relay buffer gone / gateway restarted)
    req('PUT','/pro/set',{'snapOnly':True})
    newchat(pg); pg.fill('#input','detachcut 스냅샷'); pg.click('#sendBtn'); pg.wait_for_timeout(300)
    pg.evaluate(HIDE); pg.wait_for_timeout(1500); pg.evaluate(SHOW); pg.wait_for_timeout(5000)
    t=last_asst(pg).inner_text(); check('eve.snapshot rendered', 'A9' in t and pg.locator('.msg.error').count()==0, t)
    req('PUT','/pro/set',{'snapOnly':False})
    # 4) error event inside a 200 stream → failed message with friendly text
    newchat(pg); pg.fill('#input','detacherr 오류'); pg.click('#sendBtn'); pg.wait_for_timeout(2000)
    t=last_asst(pg).inner_text(); e=pg.inner_text('.msg.error') if pg.locator('.msg.error').count() else ''
    check('error event → failed note + friendly error', '모델 서버 응답이 늦어' in t and '모델 서버 응답이 늦어' in e and 'partial' in t, [t, e])
    # failed row loaded from server shows the same text; unknown code → generic
    tid=pg.evaluate('__app.state().currentId'); pg.goto(BASE+'#/'); pg.wait_for_timeout(600)
    pg.evaluate("localStorage.clear()"); pg.goto(BASE+'#/c/'+tid); pg.wait_for_timeout(1500)
    # 5) old server (no eve.meta): cut while hidden → reload thread on visible, no error
    newchat(pg); pg.fill('#input','oldcut 옛 서버'); pg.click('#sendBtn'); pg.wait_for_timeout(200)
    pg.evaluate(HIDE); pg.wait_for_timeout(1500); pg.evaluate(SHOW); pg.wait_for_timeout(2000)
    check('old server: thread reloaded, reply shown, no error', 'old server full reply' in pg.inner_text('#chatView') and pg.locator('.msg.error').count()==0, pg.inner_text('#chatView')[-200:])
    # 6) old server, foreground clean close: legacy behaviour (partial kept, no reload loop)
    newchat(pg); pg.fill('#input','oldcut 보이는 중'); pg.click('#sendBtn'); pg.wait_for_timeout(2000)
    check('old server, foreground cut → partial kept as before', 'old' in last_asst(pg).inner_text())
    # 7) resume endpoint unavailable → poll messages GET (partial content while generating) until complete
    req('PUT','/pro/set',{'resume404':True})
    newchat(pg); pg.fill('#input','detachcut 폴링'); pg.click('#sendBtn'); pg.wait_for_timeout(300)
    pg.evaluate(HIDE); pg.wait_for_timeout(1500); pg.evaluate(SHOW); pg.wait_for_timeout(1200)
    mid_t=last_asst(pg).inner_text(); check('polling: partial shown with 답변 불러오는 중', '답변 불러오는 중' in mid_t, mid_t)
    pg.wait_for_timeout(9000)
    t=last_asst(pg).inner_text(); check('polling: reply completes, no error', 'A9' in t and '답변 불러오는 중' not in t and pg.locator('.msg.error').count()==0, t)
    req('PUT','/pro/set',{'resume404':False})
    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
