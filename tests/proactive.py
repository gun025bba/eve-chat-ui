# 선톡 P1 (v1.1.0) e2e against mock.py: unread, read-on-view, confirm card, settings, push
import json, urllib.request
from playwright.sync_api import sync_playwright
M = 'http://127.0.0.1:'+__import__('os').environ.get('EVE_PORT','8765')+''; B = M
def req(method, path, body=None):
    r = urllib.request.Request(M + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(r) as f: t = f.read(); return json.loads(t) if t else None
put = lambda p, body=None: req('PUT', p, body)
pro = lambda: req('PUT', '/__pro')
R = []
def check(name, ok, extra=''): R.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, extra)
SETTINGS = "localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit',system:'',showThink:false,noThink:false}));"
PUSH_STUB = """
window.__unsubs=0;window.__pushEndpoint='https://web.push.apple.com/QabcDEF';
Object.defineProperty(window,'Notification',{value:{permission:'default',requestPermission:async()=>'granted'},configurable:true});
const mkSub=()=>({endpoint:window.__pushEndpoint,toJSON(){return{endpoint:this.endpoint,keys:{p256dh:'P256',auth:'AUTH'}}},unsubscribe:async()=>{window.__unsubs++;window.__cur=null;sessionStorage.removeItem('__sub');return true}});
const pm={getSubscription:async()=>window.__cur||(sessionStorage.getItem('__sub')?(window.__cur=mkSub()):null),subscribe:async(o)=>{window.__subOpts={uvo:o.userVisibleOnly,keyLen:new Uint8Array(o.applicationServerKey).length};sessionStorage.setItem('__sub','1');return window.__cur=mkSub()}};
window.PushManager=function(){};
if(navigator.serviceWorker){const r=navigator.serviceWorker;Object.defineProperty(r,'ready',{get:()=>Promise.resolve({pushManager:pm,active:{}}),configurable:true});}
"""
put('/auth/on'); put('/persist/on'); put('/db/reset'); put('/fail/clear'); put('/pro/reset')
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "}")
    pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    csp = []; pg.on('console', lambda m: csp.append(m.text) if 'Content Security Policy' in m.text else None)
    def home():
        pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(1300)
        if pg.evaluate("document.getElementById('app').dataset.route") == 'chat': pg.evaluate('history.back()'); pg.wait_for_timeout(400)
    def to_log():
        if pg.evaluate("document.getElementById('app').dataset.route") == 'today': pg.click('#openLog'); pg.wait_for_timeout(500)
    def to_today():
        if pg.evaluate("document.getElementById('app').dataset.route") != 'today': pg.evaluate("location.hash='#/'"); pg.wait_for_timeout(600)
    def open_thread(tid):
        to_log()
        pg.locator(f'#convList li.row[data-id="{tid}"] .row-main, #convList li.row[data-id="{tid}"]').first.click(); pg.wait_for_timeout(1300)
    patches = lambda: [x['b'] for x in pro()['bodies'] if x['p'] == '/v1/settings' and x['m'] == 'PATCH']

    # --- unsupported server: hides itself
    put('/pro/supported/off'); home()
    check('version 1.10.2', pg.evaluate('window.__app && window.__app.version') == '1.10.2', [errs, pg.url, pg.content()[:300]])
    to_today(); pg.click('#openSettings'); pg.wait_for_timeout(600)
    check('unsupported: note + toggle off', '지금은 이 기능을 쓸 수 없어요' in pg.text_content('#sProNote') and pg.is_hidden('#proMore'))
    pg.click('#cancelSettings'); pg.wait_for_timeout(300); put('/pro/supported/on')

    # --- unread dot/pill/title, source line, read-on-view
    long = '오늘 일정은 두 개예요. ' * 80
    s1 = put('/pro/seed', {'title': '아침 브리핑', 'job_name': '아침 브리핑', 'template_kind': 'briefing', 'proactive': [long, '오후에 비가 와요.']})
    s0 = put('/pro/seed', {'title': '하나', 'proactive': ['하나뿐'], 'kind': 'digest'})
    home(); to_log()
    row = pg.locator(f'#convList li.row[data-id="{s1["thread"]}"]')
    check('server-created job thread is a normal row titled job_name', row.count() == 1 and '아침 브리핑' in row.inner_text())
    check('unread dot + pill 2', row.locator('.unread-dot').count() == 1 and row.locator('.unread-pill').inner_text() == '2', row.inner_html()[:200])
    r0 = pg.locator(f'#convList li.row[data-id="{s0["thread"]}"]')
    check('1 unread: dot, no pill', r0.locator('.unread-dot').count() == 1 and r0.locator('.unread-pill').count() == 0)
    check('aria-label count', '읽지 않은 메시지 2개' in (row.get_attribute('aria-label') or ''))
    check('title (3) Eve', pg.title() == '(3) Eve', pg.title())
    open_thread(s1['thread'])
    ol = pg.locator('.msg.proactive > .who')   # 1.10.0 B1: the origin line is replaced by the timeline who + time (DIRECTION-B §3)
    check('who "Eve · 아침 브리핑" + KST time on each event (no origin line)', ol.count() == 2 and ol.first.inner_text().strip() == 'Eve · 아침 브리핑' and pg.locator('.msg.proactive .origin-line').count() == 0 and pg.locator('.msg.proactive > .tm').count() == 2, ol.first.inner_text() if ol.count() else '')
    check('briefing icon = sun (template_kind)', ol.first.locator('svg.who-ic use').first.get_attribute('href') == '#i-sun-horizon')
    check('every proactive event carries the full who (no time-only continuation)', ol.nth(1).locator('.who-n').inner_text() == 'Eve · 아침 브리핑')
    check('job_name rendered as text', ol.first.locator('.who-n').inner_html() == 'Eve · 아침 브리핑')
    check('"새 메시지" divider before first unread', pg.locator('.unread-sep').count() == 1)
    pg.wait_for_timeout(1700)
    check('visible msg read after 1s; offscreen not', pro()['reads'] == [s1['msgs'][0]], pro()['reads'])
    check('read POST had Origin', all(o and o != 'null' for o in pro()['origins']))
    pg.locator('.msg.proactive').nth(1).scroll_into_view_if_needed(); pg.wait_for_timeout(1700)
    check('second read after scroll', sorted(pro()['reads']) == sorted(s1['msgs']), pro()['reads'])
    check('back badge = 1 (other thread)', pg.is_visible('#backBadge') and pg.inner_text('#backBadge') == '1', pg.evaluate("(e=>[e.hidden,e.textContent,getComputedStyle(e).display,JSON.stringify(e.getBoundingClientRect())])(document.getElementById('backBadge'))"))
    check('backBtn aria-label has unread count', '1개' in (pg.get_attribute('#backBtn','aria-label') or ''), pg.get_attribute('#backBtn','aria-label'))
    pg.evaluate('history.back()'); pg.wait_for_timeout(500)
    check('title (1) Eve', pg.title() == '(1) Eve', pg.title())
    open_thread(s0['thread'])
    check('digest label', 'Eve · 조용한 시간 동안 요약' == pg.locator('.msg.proactive > .who .who-n').first.inner_text())
    check('unknown template_kind → sparkle', pg.locator('.msg.proactive .who-ic use').first.get_attribute('href') == '#i-sparkle')
    pg.evaluate('history.back()'); pg.wait_for_timeout(400)

    # --- push tap: nid = message_id → open its thread, scrolled to it
    sN = put('/pro/seed', {'title': '알림 탭', 'proactive': ['x ' * 400, '이 메시지로 이동']})
    pg.goto(B + '/ui/?nid=' + sN['msgs'][1] + '#/'); pg.wait_for_timeout(2500)
    check('?nid opens its thread', pg.evaluate('__app.state().currentId') == sN['thread'], [sN, pg.url, pg.evaluate('__app.state()')])
    check('scrolled to that message', pg.evaluate(f"(e=>{{const r=e.getBoundingClientRect();return r.top<innerHeight&&r.bottom>0}})(document.querySelector('.msg[data-mid=\"{sN['msgs'][1]}\"]'))"))
    check('nid stripped from URL', 'nid=' not in pg.url)
    pg.evaluate('history.back()'); pg.wait_for_timeout(400)

    # --- several at once → POST /v1/threads/{id}/read
    s2 = put('/pro/seed', {'title': '짧은 둘', 'proactive': ['하나', '둘']})
    home(); open_thread(s2['thread']); pg.wait_for_timeout(1700)
    check('batch read → thread read once', pro().get('threadReads', []).count(s2['thread']) == 1 and not set(s2['msgs']) & set(pro()['reads']), [pro().get('threadReads'), pro()['reads']])
    pg.evaluate('history.back()'); pg.wait_for_timeout(300)

    # --- settings
    to_today(); pg.click('#openSettings'); pg.wait_for_timeout(700)
    check('toggle default off', not pg.is_checked('#sProactive') and pg.is_hidden('#proMore'))
    pg.click('label:has(#sProactive)'); pg.wait_for_timeout(500)
    check('toggle → PATCH {proactive:{enabled:true}}', patches() == [{'proactive': {'enabled': True}}], patches())
    check('quiet hours 오후 10:00 / 오전 8:00 + 한국 시간 기준', pg.text_content('#qStartVal') == '오후 10:00' and pg.text_content('#qEndVal') == '오전 8:00' and pg.is_visible('#qTz'))
    check('no daily-cap control', pg.locator('#settings input[type=number]').count() == 0)
    check('memory row hidden (memory.enabled false); push row hidden (not standalone)', pg.is_hidden('#proMemRow') and pg.is_hidden('#pushRow'))
    pg.click('#qStartRow'); pg.fill('#qStart', '08:00'); check('start==end error', pg.is_visible('#qErr'))
    pg.fill('#qStart', '23:00'); pg.click('#saveSettings'); pg.wait_for_timeout(600)
    check('완료 → PATCH quiet_hours only', patches()[-1] == {'proactive': {'quiet_hours': {'start': '23:00', 'end': '08:00'}}}, patches()[-1])
    check('system never PATCHed', all('system' not in b for b in patches()))
    put('/pro/set', {'failSettings': True})
    to_today(); pg.click('#openSettings'); pg.wait_for_timeout(600); pg.click('label:has(#sProactive)'); pg.wait_for_timeout(700)
    check('PATCH failure → rollback + toast', pg.is_checked('#sProactive') and '설정을 저장하지 못했어요' in pg.content())
    put('/pro/set', {'failSettings': False}); pg.click('#cancelSettings'); pg.wait_for_timeout(300)
    put('/pro/set', {'settings': {'proactive': {'enabled': True, 'quiet_hours': {'start': '22:00', 'end': '08:00'}, 'memory_read': False}, 'memory': {'enabled': True}}})
    to_today(); pg.click('#openSettings'); pg.wait_for_timeout(600)
    check('memory row shown when memory.enabled', pg.is_visible('#proMemRow'))
    pg.click('label:has(#sProMem)'); pg.wait_for_timeout(500)
    check('memory toggle → PATCH memory_read', patches()[-1] == {'proactive': {'memory_read': True}})
    pg.click('#cancelSettings'); pg.wait_for_timeout(300)
    put('/pro/set', {'system': {'proactive_available': False, 'tools_available': True, 'memory_read_only': False}})
    to_today(); pg.click('#openSettings'); pg.wait_for_timeout(600)
    check('system.proactive_available=false → toggle disabled + note', pg.is_disabled('#sProactive') and '지금은 이 기능을 쓸 수 없어요' in pg.text_content('#sProNote'))
    pg.click('#cancelSettings'); pg.wait_for_timeout(300)
    put('/pro/set', {'system': {'proactive_available': True, 'tools_available': True, 'memory_read_only': False}})

    # --- push (standalone)
    sctx = b.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    sctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "}" + PUSH_STUB + "Object.defineProperty(navigator,'standalone',{get:()=>true});")
    sp = sctx.new_page(); sp.on('pageerror', lambda e: errs.append(str(e)))
    sp.goto(B + '/ui/#/'); sp.wait_for_timeout(1500)
    if sp.evaluate("document.getElementById('app').dataset.route") == 'chat': sp.evaluate('history.back()'); sp.wait_for_timeout(400)
    sp.click('#openSettings'); sp.wait_for_timeout(700)
    check('pushRow right under 선톡 switch', sp.evaluate("document.getElementById('pushRow').previousElementSibling.contains(document.getElementById('sProactive'))"))
    check('standalone: push row visible, off', sp.is_visible('#pushRow') and not sp.is_checked('#sPush'))
    sp.click('label:has(#sPush)'); sp.wait_for_timeout(1500)
    check('subscribe POST', pro()['subs'] == [{'endpoint': 'https://web.push.apple.com/QabcDEF', 'keys': {'p256dh': 'P256', 'auth': 'AUTH'}, 'vapid_key_id': 'k1'}], pro()['subs'])
    check('userVisibleOnly + 65B key', sp.evaluate('window.__subOpts') == {'uvo': True, 'keyLen': 65}, sp.evaluate('window.__subOpts'))
    sp.click('label:has(#sPush)'); sp.wait_for_timeout(1000)
    check('push off → DELETE + unsubscribe', pro()['subs'] == [] and sp.evaluate('window.__unsubs') == 1)
    sp.click('label:has(#sPush)'); sp.wait_for_timeout(1500)
    put('/pro/set', {'kid': 'k2'}); sp.reload(); sp.wait_for_timeout(4500)
    subs = pro()['subs']; dels = [x for x in pro()['bodies'] if x['p'] == '/v1/push/subscriptions' and x['m'] == 'DELETE']
    check('key_id change → resubscribe with k2', len(subs) == 1 and subs[0]['vapid_key_id'] == 'k2' and len(dels) >= 1, [subs, len(dels)])
    sp.goto(B + '/ui/#/'); sp.wait_for_timeout(1200)
    if sp.evaluate("document.getElementById('app').dataset.route") == 'chat': sp.evaluate('history.back()'); sp.wait_for_timeout(400)
    sp.click('#openSettings'); sp.wait_for_timeout(700); sp.click('label:has(#sPush)'); sp.wait_for_timeout(1000)
    put('/pro/set', {'kid': 'k1'})
    for ep in ['https://fcm.googleapis.com/x', 'https://web.push.apple.com.evil.example/x', 'https://web.push.apple.com:8443/x']:
        sp.evaluate(f"window.__pushEndpoint='{ep}'"); sp.click('label:has(#sPush)'); sp.wait_for_timeout(1300)
        check('endpoint refused: ' + ep, pro()['subs'] == [] and not sp.is_checked('#sPush'))
    sctx.close()

    # --- confirm cards
    A = {'action_id': '01JACT00000000000000000001', 'tool': 'calendar_create_event', 'summary': '내일 07:30 일정 추가', 'payload_view': {'verb': 'add', '제목': '<img src=x onerror=alert(1)>', '시각': '07:30'}, 'scopes': ['calendar.write'],
         'payload_hash': 'sha256:h1', 'expires_at': '2099-01-01T00:00:00Z', 'tainted': True, 'provenance': {'actor': 'scheduler', 'job_id': '01JJOB0000000000000000000A', 'job_name': '메일 지켜보기'}}
    A2 = dict(A, action_id='01JACT00000000000000000002', tool='mail_send', scopes=['mail.send'], payload_view={'verb': 'send', '받는 사람': 'a'}, payload_hash='sha256:h2', tainted=False, provenance={'actor': 'user', 'job_id': None, 'job_name': None})
    A3 = {'action_id': '01JACT00000000000000000003', 'tool': 'proactive.propose_followup', 'summary': '치과 예약 다시 알려 드릴게요', 'scopes': ['proactive.write'], 'payload_hash': 'sha256:h3', 'expires_at': '2099-01-01T00:00:00Z',
          'payload_view': {'when': {'at': '2026-10-28T00:00:00Z'}, 'thread_id': 'x', 'display': '10월 28일 (수) 오전 9:00', 'template_id': 'followup.v1'}, 'provenance': {'actor': 'user'}}
    A4 = dict(A2, action_id='01JACT00000000000000000004', expires_at='2000-01-01T00:00:00Z', tool='memory.propose', scopes=['memory.write'], payload_view={'op': 'add', 'items': [{'text': '커피는 디카페인', 'kind': 'preference'}], 'ambiguous': False})
    FG = {'action_id': '01JACT00000000000000000005', 'tool': 'memory.propose', 'summary': '잊기', 'scopes': ['memory.delete'], 'payload_hash': 'sha256:h5', 'expires_at': '2099-01-01T00:00:00Z', 'provenance': {'actor': 'user'},
          'payload_view': {'op': 'delete', 'ambiguous': False, 'items': [{'id': 'm1', 'text': '아침 브리핑은 짧게', 'kind': 'preference', 'updated_at': '2020-03-02T00:00:00Z'}, {'id': 'm2', 'text': '주말 브리핑 안 받기', 'kind': 'preference'}]}}
    VU = dict(A, action_id='01JACT0000000000000000000U', payload_hash='sha256:vu', tainted=False, payload_view={'verb': 'update'})
    VD = dict(A, action_id='01JACT0000000000000000000D', payload_hash='sha256:vd', tainted=False, payload_view={'verb': 'delete'}, scopes=['calendar.write'])
    VX = dict(A, action_id='01JACT0000000000000000000X', payload_hash='sha256:vx', tainted=False, payload_view={'verb': 'frobnicate'}, tool='calendar_create_event')
    VP = [dict(A, action_id=f'01JACT000000000000000000P{n}', payload_hash=f'sha256:vp{n}', tainted=False, payload_view=({'verb': v} if v else {})) for n, v in enumerate(['constructor', '__proto__', 'toString', 'hasOwnProperty', None])]
    s3 = put('/pro/seed', {'title': '확인 카드', 'actions': [A, A2, A3, A4, FG, VU, VD, VX] + VP})
    home(); open_thread(s3['thread']); pg.wait_for_timeout(500)
    card = lambda i: pg.locator(f'.confirm-card[data-aid="{i}"]')
    c1 = card(A['action_id'])
    for k in ['A', 'A2', 'A3', 'A4', 'FG']: card(eval(k)['action_id']).scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    c1.scroll_into_view_if_needed(); pg.wait_for_timeout(500)
    check('tool card, taint + scheduler provenance', c1.get_attribute('data-variant') == 'tool' and c1.locator('.cc-taint').count() == 1 and '메일 지켜보기에서' in c1.locator('.cc-prov').inner_text())
    check('payload_view as text', pg.locator('.confirm-card img').count() == 0 and '<img' in c1.locator('dd').first.inner_text())
    check('no token fetched on render/viewport (§3.5.4)', pro()['issued'] == 0 and c1.get_attribute('data-state') == 'pending', [pro()['issued'], c1.get_attribute('data-state')])
    check('no token countdown', '초 뒤 만료' not in c1.inner_text())
    check('write scope = accent (no danger)', 'cc-danger' not in c1.locator('.cc-primary').get_attribute('class') and c1.locator('.cc-primary').inner_text() == '추가')
    c2 = card(A2['action_id'])
    check('send scope = danger 보내기', 'cc-danger' in c2.locator('.cc-primary').get_attribute('class') and c2.locator('.cc-primary').inner_text() == '보내기')
    for k, want in [(VU, '변경'), (VD, '삭제'), (VX, '실행')] + [(v, '실행') for v in VP]:
        ck = card(k['action_id']); ck.scroll_into_view_if_needed(); pg.wait_for_timeout(200)
        check('verb from payload_view.verb: ' + want, ck.locator('.cc-primary').inner_text() == want, ck.locator('.cc-primary').inner_text())
    check('delete verb with write scope stays accent (danger by scopes)', 'cc-danger' not in card(VD['action_id']).locator('.cc-primary').get_attribute('class'))
    check('forget keeps specific verb', 'N' not in card(FG['action_id']).locator('.cc-primary').inner_text() and '개 지우기' in card(FG['action_id']).locator('.cc-primary').inner_text())
    c3 = card(A3['action_id'])
    check('propose_followup → proactive variant, display as-is, accent', c3.get_attribute('data-variant') == 'proactive' and c3.locator('time.cc-when').inner_text() == '10월 28일 (수) 오전 9:00' and 'cc-danger' not in c3.locator('.cc-primary').get_attribute('class') and c3.locator('.cc-secondary').inner_text() == '괜찮아요')
    c1.locator('.cc-primary').click(); pg.wait_for_timeout(800)
    ap = [x for x in pro()['bodies'] if x['p'].endswith('01JACT00000000000000000001/approve')]
    seq = [x['p'].rsplit('/', 1)[-1] for x in pro()['bodies'] if '01JACT00000000000000000001/' in x['p']]
    check('press → reissue then approve', seq == ['reissue', 'approve'], seq)
    check('approve {confirm_token,payload_hash}', len(ap) == 1 and set(ap[0]['b']) == {'confirm_token', 'payload_hash'} and ap[0]['b']['payload_hash'] == 'sha256:h1')
    check('confirmed 추가했어요 (VERB_DONE[add])', c1.get_attribute('data-state') == 'confirmed' and '추가했어요' in c1.inner_text())
    check('tokens not persisted', 'tok1' not in pg.evaluate('JSON.stringify(localStorage)+JSON.stringify(sessionStorage)'))
    c2.locator('.cc-secondary').click(); pg.wait_for_timeout(600)
    check('reject → declined', c2.get_attribute('data-state') == 'declined')
    # forget
    fg = card(FG['action_id'])
    check('forget: danger "2개 지우기", rows checked', fg.locator('.cc-primary').inner_text() == '2개 지우기' and 'cc-danger' in fg.locator('.cc-primary').get_attribute('class') and fg.locator('input:checked').count() == 2)
    check('forget meta "kind · date" in <time>', fg.locator('.cc-item .cc-kind').first.inner_text() == 'preference · 2020년 3월 2일' and fg.locator('.cc-item time').first.get_attribute('datetime') == '2020-03-02T00:00:00Z', fg.locator('.cc-item .cc-kind').first.inner_text())
    fg.locator('input').nth(1).uncheck(); pg.wait_for_timeout(100)
    check('primary → 1개 지우기', fg.locator('.cc-primary').inner_text() == '1개 지우기')
    fg.locator('.cc-primary').click(); pg.wait_for_timeout(900)
    rv = [x for x in pro()['bodies'] if x['p'].startswith('/v1/proposals/')]
    check('partial → revise {item_ids:[m1]}', rv and rv[-1]['b'] == {'item_ids': ['m1']}, rv)
    nf = pg.locator('.confirm-card[data-variant=forget]')
    check('card replaced in place (new id, 1 item, pending)', nf.count() == 1 and nf.get_attribute('data-aid') != FG['action_id'] and nf.locator('.cc-item').count() == 1 and nf.get_attribute('data-state') == 'pending')
    nf.locator('.cc-primary').click(); pg.wait_for_timeout(800)
    check('all checked → approve directly, 1개 지웠어요', nf.get_attribute('data-state') == 'confirmed' and '1개 지웠어요' in nf.inner_text() and len([x for x in pro()['bodies'] if x['p'].startswith('/v1/proposals/')]) == 1)
    # expired remember → 다시 요청 (empty body)
    c4 = card(A4['action_id'])
    check('expired remember shows 다시 요청', c4.get_attribute('data-state') == 'expired' and c4.locator('.cc-again').is_visible())
    c4.locator('.cc-again').click(); pg.wait_for_timeout(800)
    rv = [x for x in pro()['bodies'] if x['p'].startswith('/v1/proposals/')]
    check('다시 요청 remember → revise empty body', rv[-1]['b'] == {} and rv[-1]['p'] == f'/v1/proposals/{A4["action_id"]}/revise')
    nr = pg.locator('.confirm-card[data-variant=remember]')
    check('remember replaced → pending', nr.count() == 1 and nr.get_attribute('data-state') == 'pending')

    # 410 hides 다시 요청
    A6 = dict(A4, action_id='01JACT00000000000000000006')
    s5 = put('/pro/seed', {'title': '만료', 'actions': [A6]}); put('/pro/set', {'revise410': True})
    home(); open_thread(s5['thread'])
    c6 = card(A6['action_id']); c6.locator('.cc-again').click(); pg.wait_for_timeout(700)
    check('410 → expired, 다시 요청 hidden', c6.get_attribute('data-state') == 'expired' and c6.locator('.cc-again').is_hidden())
    put('/pro/set', {'revise410': False})

    # error_code branching, ambiguous approve, tokenless revise
    E1 = dict(A2, action_id='01JACT00000000000000000007', payload_hash='sha256:e1', scopes=['calendar.write'], tool='calendar_create_event')
    E2 = dict(E1, action_id='01JACT00000000000000000008', payload_hash='sha256:e2')
    E3 = dict(E1, action_id='01JACT00000000000000000009', payload_hash='sha256:e3')
    FG2 = dict(FG, action_id='01JACT0000000000000000000A', payload_hash='sha256:f2')
    s6 = put('/pro/seed', {'title': '오류', 'actions': [E1, E2, E3, FG2]})
    home(); open_thread(s6['thread'])
    for k in [E1, E2, E3, FG2]: card(k['action_id']).scroll_into_view_if_needed(); pg.wait_for_timeout(400)
    put('/pro/set', {'approveCode': [409, 'conflict'], 'statusOf': {E1['action_id']: 'superseded'}}); card(E1['action_id']).locator('.cc-primary').click(); pg.wait_for_timeout(900)
    check('409 conflict, recheck inconclusive → 이미 처리된 요청이에요', card(E1['action_id']).get_attribute('data-state') == 'denied' and '이미 처리된 요청이에요' in card(E1['action_id']).inner_text() and card(E1['action_id']).locator('button:visible').count() == 0, card(E1['action_id']).inner_text())
    E1b = dict(E1, action_id='01JACT0000000000000000000B', payload_hash='sha256:e1b')
    s6b = put('/pro/seed', {'title': '충돌', 'actions': [E1b]}); home(); open_thread(s6b['thread']); cb = card(E1b['action_id']); cb.scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    put('/pro/set', {'approveCode': [409, 'conflict'], 'statusOf': {E1b['action_id']: 'executing'}}); cb.locator('.cc-primary').click(); pg.wait_for_timeout(1500)
    check('conflict → recheck; executing keeps polling', cb.get_attribute('data-state') == 'checking', cb.get_attribute('data-state'))
    put('/pro/set', {'statusOf': {E1b['action_id']: 'executed'}}); pg.wait_for_timeout(5000)
    check('conflict → recheck loads real result (confirmed)', cb.get_attribute('data-state') == 'confirmed', cb.get_attribute('data-state'))
    pg.evaluate('history.back()'); pg.wait_for_timeout(300); open_thread(s6['thread']); pg.wait_for_timeout(300)
    put('/pro/set', {'approveCode': [422, 'weird_new_code']}); card(E2['action_id']).locator('.cc-primary').click(); pg.wait_for_timeout(700)
    check('unknown code → invalid text', '요청 내용이 올바르지 않아 진행하지 않았어요' in card(E2['action_id']).inner_text())
    put('/pro/set', {'approveDrop': True, 'getDelay': 1.5}); c9 = card(E3['action_id']); c9.locator('.cc-primary').click(); pg.wait_for_timeout(300)
    check('lost approve response → checking, no blind retry', c9.get_attribute('data-state') == 'checking' and '결과를 확인하는 중이에요' in c9.inner_text(), c9.get_attribute('data-state'))
    pg.wait_for_timeout(4000); put('/pro/set', {'getDelay': 0})
    ap = [x for x in pro()['bodies'] if x['p'].endswith(E3['action_id'] + '/approve')]
    check('re-check via GET /v1/actions/{id} → confirmed, approve sent once', c9.get_attribute('data-state') == 'confirmed' and len(ap) == 1, [c9.get_attribute('data-state'), len(ap)])
    put('/pro/set', {'reviseNoToken': True}); f2 = card(FG2['action_id']); f2.locator('input').nth(1).uncheck(); f2.locator('.cc-primary').click(); pg.wait_for_timeout(1500)
    rv = [x for x in pro()['bodies'] if x['p'].startswith('/v1/proposals/' + FG2['action_id'])]
    nf2 = pg.locator('.confirm-card[data-variant=forget]').last
    check('revise body = {item_ids} only', rv and rv[-1]['b'] == {'item_ids': ['m1']})
    check('tokenless revise response → pending card', nf2.get_attribute('data-state') == 'pending' and nf2.get_attribute('data-aid') != FG2['action_id'], nf2.get_attribute('data-state'))
    put('/pro/set', {'reviseNoToken': False})
    pg.evaluate('history.back()'); pg.wait_for_timeout(300)

    # restore via GET /v1/actions
    RR = dict(A2, action_id='01JACT0000000000000000000R', payload_hash='sha256:r')
    s4 = put('/pro/seed', {'title': '복원', 'user': ['일정 잡아줘'], 'restore': [RR]})
    home(); open_thread(s4['thread']); pg.wait_for_timeout(500)
    check('restored card', card(RR['action_id']).count() == 1)
    pg.evaluate('history.back()'); pg.wait_for_timeout(300)

    # SSE confirmation + denied
    put('/pro/set', {'sseToken': True}); pg.evaluate("__app.newChat()"); pg.wait_for_timeout(400); issued = pro()['issued']
    pg.fill('#input', 'confirm 치과'); pg.click('#sendBtn'); pg.wait_for_timeout(2000)
    cs = card('01JACT0000000000000000000S')
    check('stream card pending', cs.count() == 1 and cs.get_attribute('data-state') == 'pending')
    cs.locator('.cc-primary').click(); pg.wait_for_timeout(700)
    aps = [x['b'] for x in pro()['bodies'] if x['p'].endswith('0000000000000000000S/approve')]
    check('SSE confirm_token ignored → reissue on press', pro()['issued'] == issued + 1 and aps and aps[0]['confirm_token'] != 'ssetok-must-be-ignored' and cs.get_attribute('data-state') == 'confirmed', [pro()['issued'] - issued, aps])
    put('/pro/set', {'sseToken': False})
    check('live region announces', '실행했어요' in (pg.text_content('#proLive') or ''))
    pg.fill('#input', 'confirmdeny 비번 기억해'); pg.click('#sendBtn'); pg.wait_for_timeout(2000)
    cd = card('01JACT0000000000000000000D')
    check('denied: one line, fixed text, no buttons', cd.get_attribute('data-state') == 'denied' and cd.inner_text().strip() == '비밀번호나 키처럼 보여서 진행하지 않았어요' and cd.locator('button').count() == 0, cd.inner_text() if cd.count() else '')

    # sign-out (401) clears stored confirm-card contents (security review Low 2)
    check('cards stored before sign-out', 'pendingActions' in (pg.evaluate("localStorage.getItem('llmchat.srvcache')") or ''))
    check('no tokens ever stored', not any(t in (pg.evaluate("JSON.stringify(localStorage)") or '') for t in ['confirm_token', 'ssetok', 'revtok', '"tok']))
    put('/auth/off'); pg.reload(); pg.wait_for_timeout(2000)
    check('after 401: no pendingActions in localStorage', 'pendingActions' not in (pg.evaluate("JSON.stringify(localStorage)") or ''))
    put('/auth/on'); pg.reload(); pg.wait_for_timeout(1500)
    pg.evaluate("(()=>{const k='llmchat.srvcache';let v=JSON.parse(localStorage.getItem(k)||'[]');if(!Array.isArray(v))v=[];if(!v.length)v.push({id:'t',messages:[]});v[0].messages=(v[0].messages||[]).concat([{id:'x',role:'assistant',content:'',pendingActions:[{action_id:'A'}]}]);localStorage.setItem(k,JSON.stringify(v));})()")
    check('seeded stored card', 'pendingActions' in (pg.evaluate("localStorage.getItem('llmchat.srvcache')") or ''))
    put('/whoamifalse/on'); pg.reload(); pg.wait_for_timeout(2000)
    check('whoami authenticated:false → stored cards cleared', 'pendingActions' not in (pg.evaluate("JSON.stringify(localStorage)") or ''))
    put('/whoamifalse/off')
    mut = req('PUT', '/__mut')
    check('every mutating API request had X-Eve-Request + Origin + JSON', mut and all(x['ok'] for x in mut), [x for x in mut if not x['ok']][:3])
    check('no CSP violations', not csp, csp)
    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
