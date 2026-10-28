# Server-persisted threads (v10) e2e against mock.py
import json, urllib.request
from playwright.sync_api import sync_playwright
M='http://127.0.0.1:'+__import__('os').environ.get('EVE_PORT','8765')+''; BASE=M+'/ui/'
def req(method, path, body=None):
    r=urllib.request.Request(M+path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(r) as f: t=f.read(); return json.loads(t) if t else None
db=lambda: req('GET','/__db')
R=[]
def check(name, ok, extra=''): R.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, extra)
SETTINGS="localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit',system:'',showThink:false,noThink:false}));"
req('PUT','/auth/on'); req('PUT','/persist/on'); req('PUT','/db/reset'); req('PUT','/fail/clear')
req('PUT','/seed',{'threads':[{'title':f'서버 대화 {i}','messages':[['user',f'질문 {i} 바나나' if i==3 else f'질문 {i}'],['assistant',f'답변 {i}']]} for i in range(45)]})
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch()
    c=b.new_context(viewport={'width':393,'height':852}, is_mobile=True, has_touch=True)
    c.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);"+SETTINGS+"}")
    pg=c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(BASE+'#/'); pg.wait_for_timeout(1500)
    st=pg.evaluate('__app.state()'); check('server mode', st['mode']=='server', str(st))
    n0=pg.locator('#convList li.row').count(); check('first page loaded', 0<n0<45, str(n0))
    for _ in range(6): pg.evaluate("document.querySelector('#convList').closest('.scroll, main, section, #listView').querySelectorAll('*').forEach(e=>{if(e.scrollHeight>e.clientHeight)e.scrollTop=e.scrollHeight})"); pg.wait_for_timeout(500)
    n1=pg.locator('#convList li.row').count(); check('infinite scroll loads all', n1==45, str(n1))
    # search
    pg.fill('#search','바나나'); pg.wait_for_timeout(900)
    marks=pg.locator('#convList mark').count(); check('server search highlights <mark>', marks>=1, str(marks))
    pg.locator('#convList li').filter(has=pg.locator('mark')).first.click(); pg.wait_for_timeout(1200)
    check('search hit opens thread', pg.evaluate("document.querySelector('#app').dataset.route")=='chat' and '바나나' in pg.inner_text('#chatView'))
    pg.goto(BASE+'#/'); pg.wait_for_timeout(800); pg.fill('#search',''); pg.wait_for_timeout(500)
    # new thread send
    pg.click('#newChat'); pg.wait_for_timeout(500); pg.fill('#input','hello server'); pg.click('#sendBtn'); pg.wait_for_timeout(4000)
    d=db(); th=[t for t in d['threads'] if t['title']!='' and not t['title'].startswith('서버 대화')]
    check('send creates server thread', len(d['threads'])==46, str(len(d['threads'])))
    cid=pg.evaluate('__app.state().currentId'); check('tmp id adopted', cid and not cid.startswith('tmp-'), cid)
    check('hash uses server id', cid in pg.evaluate('location.hash'))
    msgs=[m for m in d['messages'] if m['thread_id']==cid]; check('user+assistant persisted', len(msgs)==2, str([m['role'] for m in msgs]))
    # feedback
    up=pg.locator('.msg.assistant .fb.up').last; check('feedback buttons shown', up.count()==1)
    order=pg.evaluate("[...[...document.querySelectorAll('.msg.assistant')].pop().querySelectorAll('.actions > *')].map(e=>e.className)")
    check('action bar order copy,regen,up,down', [o.split()[0] for o in order if o][:4]==['c','r','fb','fb'], str(order))
    up.click(); pg.wait_for_timeout(700)
    am=[m for m in db()['messages'] if m['thread_id']==cid and m['role']=='assistant'][0]
    check('thumbs up saved', (am.get('feedback') or {}).get('rating')=='up', str(am.get('feedback')))
    check('aria-pressed up', up.get_attribute('aria-pressed')=='true')
    pg.locator('.msg.assistant .fb.down').last.click(); pg.wait_for_timeout(500)
    check('down opens inline reason panel', pg.locator('.msg.assistant .fbp').last.is_visible())
    pg.locator('.msg.assistant .fbp .fbchip').first.click(); pg.locator('.msg.assistant .fbp-done').last.click(); pg.wait_for_timeout(700)
    am=[m for m in db()['messages'] if m['thread_id']==cid and m['role']=='assistant'][0]
    check('down with reason', (am.get('feedback') or {}).get('rating')=='down' and am['feedback'].get('reasons')==['wrong_info'], str(am.get('feedback')))
    # rollback on 400
    req('PUT','/fail/400?feedback'); pg.locator('.msg.assistant .fb.up').last.click(); pg.wait_for_timeout(900)
    check('feedback rollback on 4xx', pg.locator('.msg.assistant .fb.down').last.get_attribute('aria-pressed')=='true')
    req('PUT','/fail/clear')
    # regenerate replaces
    pg.locator('.msg.assistant button.r').last.click(); pg.wait_for_timeout(4000)
    msgs=[m for m in db()['messages'] if m['thread_id']==cid]
    check('regenerate replaces (no new user msg)', len(msgs)==2 and not msgs[1].get('feedback'), str(len(msgs)))
    # archive with undo then commit
    pg.goto(BASE+'#/'); pg.wait_for_timeout(1200)
    pg.evaluate("document.querySelector('#convList li.row').scrollIntoView()")
    pg.locator('#convList li.row').first.dispatch_event('contextmenu'); pg.wait_for_timeout(400)
    if pg.is_visible('#ctx'):
        pg.locator('#ctx [role=menuitem]', has_text='보관').click(); pg.wait_for_timeout(300)
        check('undo toast shown', pg.is_visible('#toast') and '되돌리기' in pg.inner_text('#toast'))
        check('not committed before toast ends', not any(t.get('archived') for t in db()['threads']))
        pg.wait_for_timeout(3500)
        check('archive committed after toast', sum(1 for t in db()['threads'] if t.get('archived'))==1)
        pg.click('#archivedRow'); pg.wait_for_timeout(1200)
        check('archive screen lists it', pg.locator('#archList li').count()==1, str(pg.locator('#archList li').count()))
        pg.locator('#archList li').first.click(); pg.wait_for_timeout(1000); pg.click('#archRestore'); pg.wait_for_timeout(1000)
        check('restore', not any(t.get('archived') for t in db()['threads']))
    else: check('context menu opens', False)
    # outbox: network failure queued then flushed
    pg.goto(BASE+'#/c/'+cid); pg.reload(); pg.wait_for_timeout(2000)
    req('PUT','/fail/503?feedback'); pg.locator('.msg.assistant .fb.up').last.click(); pg.wait_for_timeout(800)
    check('5xx queued in outbox', pg.evaluate('__app.state().outbox')==1)
    req('PUT','/fail/clear'); pg.wait_for_timeout(3500)
    check('outbox flushed', pg.evaluate('__app.state().outbox')==0)
    # 503 persistence_disabled fallback
    req('PUT','/persist/off')
    c2=b.new_context(viewport={'width':393,'height':852}); c2.add_init_script(SETTINGS); q=c2.new_page(); q.goto(BASE+'#/'); q.wait_for_timeout(1500)
    check('503 -> local mode', q.evaluate('__app.state().mode')=='local')
    check('local-mode notice', '이 기기에만' in q.inner_text('#syncStatus'), q.inner_text('#syncStatus'))
    q.click('#newChat'); q.wait_for_timeout(500); q.fill('#input','local only'); q.click('#sendBtn'); q.wait_for_timeout(3500)
    check('local mode chat works (no thread_id sent)', 'Hello' in q.inner_text('#chatView') and 'thread_id' not in db()['state'].get('lastBody',{}))
    q.close(); c2.close()
    # persistence switched off mid-session in server mode: reply still arrives, notice shown
    pg.fill('#input','mid off'); pg.click('#sendBtn'); pg.wait_for_timeout(3500)
    check('503 on chat -> retried without persistence', pg.locator('.msg.assistant').count()>=2 and 'Hello' in pg.locator('.msg.assistant').last.inner_text())
    req('PUT','/persist/on')
    # migration
    c3=b.new_context(viewport={'width':393,'height':852})
    c3.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);"+SETTINGS+"localStorage.setItem('llmchat.convs',JSON.stringify(["+",".join(f"{{id:'L{i}',title:'{'importfail ' if i==2 else ''}로컬 {i}',updated:Date.now()-{i}*1e5,messages:[{{role:'user',content:'u{i}'}},{{role:'assistant',content:'a{i}'}}]}}" for i in range(7))+"]))}")
    m=c3.new_page(); m.on('pageerror', lambda e: errs.append(str(e))); m.goto(BASE+'#/'); m.wait_for_timeout(2000)
    check('migration sheet offered', m.is_visible('#migrateSheet'))
    m.click('#migGo'); m.wait_for_timeout(4000)
    check('partial failure view', m.get_attribute('#migrateSheet','data-view')=='partial' and m.locator('#migFailList li').count()==1)
    req('PUT','/importfix'); m.click('#migRetry'); m.wait_for_timeout(3000)
    check('retry -> done', m.get_attribute('#migrateSheet','data-view')=='done')
    imp=[t for t in db()['threads'] if t.get('client_id','').startswith('local:')]; check('7 imported', len(imp)==7, str(len(imp)))
    check('backup kept', m.evaluate("!!localStorage.getItem('llmchat.convs.bak')"))
    sw=pg.evaluate("fetch('/ui/sw.js').then(r=>r.text()).then(t=>t.includes('llmchat-1.10.0'))"); check('sw 1.10.0', sw)
    check('no page errors', not errs, str(errs[:3]))
    b.close()
print('RESULT:', 'ALL PASS' if all(R) else f'{R.count(False)} FAIL')
