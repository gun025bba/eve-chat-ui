# 1.1.2/1.1.3 stream resume (ui-api-contract §3.8, eve-serving PR #22) e2e against mock.py
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
    pg.goto(BASE+'#/'); pg.wait_for_timeout(700); pg.evaluate("__app.newChat()"); pg.wait_for_timeout(300)
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
    check('error event → failed note + friendly error', '응답이 늦어 답변을 끝내지 못했어요' in t and '응답이 늦어' in e and '모델 서버' not in t+e and 'partial' in t, [t, e])
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
    def reload_thread(tid):
        pg.goto(BASE+'#/'); pg.wait_for_timeout(400); pg.evaluate("localStorage.clear()"); pg.reload(); pg.wait_for_timeout(1500)
        pg.click(f'#convList li.row[data-id="{tid}"]'); pg.wait_for_timeout(1200)
    def nres(): return len(db()['state'].get('resumes', []))
    # 8) stop with a mid → POST .../cancel (CSRF header, no body) → 중지됨; server row failed/cancelled
    newchat(pg); pg.fill('#input','detachslow 중지'); pg.click('#sendBtn'); pg.wait_for_timeout(1200)
    pg.click('#sendBtn'); pg.wait_for_timeout(1500)
    st=db()['state']; cn=st.get('cancels', []); mut=[x for x in st.get('mut', []) if x['p'].endswith('/cancel')]
    dmid=pg.evaluate("[...document.querySelectorAll('.msg.assistant')].pop().dataset.mid")
    check('stop → cancel POST with CSRF header, no body', cn and cn[-1]['mid']==dmid and cn[-1]['len']==0 and mut and mut[-1]['ok'], [cn[-1:], mut[-1:]])
    check('stop → 중지됨, no error', '답변을 멈췄어요' in last_asst(pg).inner_text() and pg.locator('.msg.error').count()==0)
    sm=[m for m in db()['messages'] if m['id']==dmid][0]; check('server row failed/cancelled', sm['status']=='failed' and sm.get('error_code')=='cancelled', sm.get('status'))
    tid=pg.evaluate('__app.state().currentId'); reload_thread(tid)
    check('reloaded cancelled row → 중지됨', '답변을 멈췄어요' in last_asst(pg).inner_text(), last_asst(pg).inner_text())
    # 9) legacy client_disconnected → 중지됨; no_subscriber / too_large / unknown → texts
    for code, want in [('client_disconnected', '답변을 멈췄어요'), ('no_subscriber', '앱을 오래 닫아 두어'), ('too_large', '너무 길어져'), ('weird_code', '답변을 끝내지 못했어요')]:
        req('PUT','/pro/set',{'msgPatch':{dmid:{'status':'failed','error_code':code}}}); reload_thread(tid)
        check(f'failed {code} → {want}', want in last_asst(pg).inner_text(), last_asst(pg).inner_text())
    # 10) pre-admission 429 too_many_generations + Retry-After: friendly text, retry disabled until it passes
    newchat(pg); pg.fill('#input','busy429 하나 더'); pg.click('#sendBtn'); pg.wait_for_timeout(700)
    e=pg.inner_text('.msg.error'); btn=pg.locator('.msg.error .btn.retry')
    check('429 too_many_generations text + Retry-After', '이미 답변 2개를 만들고 있어요' in e and '2초 뒤' in e, e)
    check('retry disabled during Retry-After', btn.is_disabled()); pg.wait_for_timeout(2000); check('retry enabled after', btn.is_enabled())
    # 11) 409 generation_in_progress on regenerate
    newchat(pg); pg.fill('#input','regen409 x'); pg.click('#sendBtn'); pg.wait_for_timeout(2500)
    last_asst(pg).locator('.actions .r').click(); pg.wait_for_timeout(800)
    check('409 generation_in_progress text', pg.locator('.msg.error').count()==1 and '이미 다시 만드는 중' in pg.inner_text('.msg.error'))
    # 12) stream error event with retry_after
    newchat(pg); pg.fill('#input','detacherrra x'); pg.click('#sendBtn'); pg.wait_for_timeout(2000)
    check('error event retry_after shown', '2초 뒤' in pg.inner_text('.msg.error'), pg.inner_text('.msg.error'))
    # 13) resume starts with eve.snapshot (log overflow) then live events: snapshot replaces, never appended
    req('PUT','/pro/set',{'snapLive':True})
    newchat(pg); pg.fill('#input','detachcut 스냅+라이브'); pg.click('#sendBtn'); pg.wait_for_timeout(300)
    pg.evaluate(HIDE); pg.wait_for_timeout(1500); pg.evaluate(SHOW); pg.wait_for_timeout(4500)
    t=last_asst(pg).inner_text(); check('snapshot replaces content (no duplicates)', all(t.count(f'A{k} ')+t.count(f'A{k}\n')+ (1 if t.rstrip().endswith(f'A{k}') else 0) >= 1 for k in range(10)) and t.count('A0')==1 and t.count('A1')==1, t)
    req('PUT','/pro/set',{'snapLive':False})
    # 14) server write-timeout cuts + 429 too_many_subscribers on resume → automatic reconnects
    req('PUT','/pro/set',{'resumeCut':2,'subs429':1}); r0=nres()
    newchat(pg); pg.fill('#input','detachcut 재연결'); pg.click('#sendBtn'); pg.wait_for_timeout(300)
    pg.evaluate(HIDE); pg.wait_for_timeout(1500); pg.evaluate(SHOW); pg.wait_for_timeout(8000)
    t=last_asst(pg).inner_text(); check('auto-reconnect after cuts/429 → complete', 'A9' in t and t.count('A0')==1 and pg.locator('.msg.error').count()==0 and nres()-r0>=4, [t, nres()-r0])
    # 15) old failed row from the server → failure text + visible '다시 시도' that regenerates the same message_id
    req('PUT','/pro/set',{'msgPatch':{dmid:{'status':'incomplete','error_code':None,'metadata':{'incomplete':True,'reason':'upstream_error'},'content':''}}}); reload_thread(tid)
    note=last_asst(pg).locator('.msg-note.failed'); rb=note.locator('button.retry')
    check('old failed row → text + 다시 시도 visible', note.count()==1 and '문제가 생겨 답변을 끝내지 못했어요' in note.inner_text() and rb.is_visible() and '다시 시도' in rb.inner_text(), last_asst(pg).inner_text())
    rb.click(); pg.wait_for_timeout(7000)
    check('다시 시도 → same message_id regenerated', db()['state'].get('lastBody',{}).get('replace_message_id')==dmid and 'A9' in last_asst(pg).inner_text(), db()['state'].get('lastBody'))
    # 16) empty completed reply → no silent empty bubble (let the slow regen finish first)
    pg.wait_for_timeout(8000)
    req('PUT','/pro/set',{'msgPatch':{dmid:{'status':'complete','error_code':None,'metadata':None,'content':''}}}); reload_thread(tid)
    check('empty reply → 답변을 받지 못했어요 + 다시 시도', '답변을 받지 못했어요' in last_asst(pg).inner_text() and last_asst(pg).locator('button.retry').is_visible(), last_asst(pg).inner_text())
    # 17) thread ends with a user turn and no assistant → retry affordance
    req('PUT','/pro/set',{'dropMsgs':[dmid]}); reload_thread(tid)
    e=pg.locator('.msg.error'); check('user turn without reply → error + 다시 시도', e.count()==1 and '답변을 받지 못했어요' in e.inner_text() and e.locator('button.retry').is_visible(), pg.inner_text('#chatView')[-200:])
    e.locator('button.retry').click(); pg.wait_for_timeout(7000)
    check('retry → reply generated', pg.locator('.msg.assistant').count()>=1 and pg.locator('.msg.error').count()==0, pg.inner_text('#chatView')[-200:])
    # 18) 1.1.4 copy: stopped note is normal style with retry; no codes / HTTP numbers / infra names on screen
    txt=pg.inner_text('body'); check('no codes or infra names on screen', not any(x in txt for x in ['모델 서버','서버가 다시','429','503','rate_limited','queue_full']), txt[-300:])
    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
