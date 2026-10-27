# Part B memory UI (flag 'eve.flag.memory', off by default) e2e against mock.py
import json, urllib.request
from playwright.sync_api import sync_playwright
M = 'http://127.0.0.1:' + __import__('os').environ.get('EVE_PORT', '8765'); B = M
def req(method, path, body=None):
    r = urllib.request.Request(M + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(r) as f: t = f.read(); return json.loads(t) if t else None
put = lambda p, body=None: req('PUT', p, body)
pro = lambda: req('PUT', '/__pro')
R = []
def check(name, ok, extra=''): R.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, extra)
SETTINGS = "localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit',system:'',showThink:false,noThink:false}));"
SYS = {'proactive_available': True, 'tools_available': True, 'memory_read_only': False}
put('/auth/on'); put('/persist/on'); put('/db/reset'); put('/fail/clear'); put('/pro/reset')
errs = []
memGets = lambda: [x for x in pro()['bodies'] if x['p'] == '/v1/memory' and x['m'] == 'GET']
patches = lambda: [x['b'] for x in pro()['bodies'] if x['p'] == '/v1/settings' and x['m'] == 'PATCH']
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "}")
    pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    def home():
        pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(1300)
        if pg.evaluate("document.getElementById('app').dataset.route") == 'chat': pg.evaluate('history.back()'); pg.wait_for_timeout(400)
    def settings(): home(); pg.click('#openSettings'); pg.wait_for_timeout(900)
    def open_list(): pg.click('#memOpen'); pg.wait_for_timeout(700)
    rows = lambda: pg.locator('#memList li.mem-row')

    # 1) flag OFF (default): nothing visible, no memory request
    settings()
    check('version 1.2.0', pg.evaluate('__app.version') == '1.2.0')
    check('flag off: memory section hidden', pg.is_hidden('#memSection') and pg.evaluate("localStorage.getItem('eve.flag.memory')") is None)
    check('flag off: no GET /v1/memory', not memGets())

    # 2) flag ON
    pg.evaluate("localStorage.setItem('eve.flag.memory','1')"); settings()
    check('flag on: section visible, toggle reflects memory.enabled=false', pg.is_visible('#memSection') and not pg.is_checked('#sMemory') and not pg.is_disabled('#sMemory') and '꺼져 있어요' in pg.text_content('#sMemNote'))
    check('count shown', pg.text_content('#memCount') == '4개', pg.text_content('#memCount'))
    pg.click('label:has(#sMemory)'); pg.wait_for_timeout(600)
    check('toggle → PATCH {memory:{enabled:true}} only', patches()[-1:] == [{'memory': {'enabled': True}}] and pg.is_checked('#sMemory'), patches())
    check('note on', '저장할 때는 항상 먼저 물어봐요' in pg.text_content('#sMemNote'))
    pg.click('label:has(#sMemory)'); pg.wait_for_timeout(600)
    check('toggle off → PATCH false', patches()[-1] == {'memory': {'enabled': False}})

    # 3) list: order pinned → live task → updated desc, text only
    open_list()
    t = [rows().nth(i).locator('.mem-text').inner_text() for i in range(rows().count())]
    check('list order', t[:3] == ['이름은 건영', '다음 주 발표 준비 중', '<img src=x onerror=alert(1)> 고양이 이름은 나비'] and len(t) == 4, t)
    check('text rendered as text (no injected img)', pg.locator('#memList img').count() == 0)
    check('meta: 고정됨 · 프로필 / 대화에서', '고정됨' in rows().nth(0).inner_text() and '대화에서' in rows().nth(3).inner_text() and '만료' in rows().nth(1).inner_text())

    # 4) delete behind a confirm step; CSRF header + JSON
    r2 = rows().nth(3); r2.locator('.mem-del').click(); pg.wait_for_timeout(300)
    check('confirm shown, no DELETE yet', r2.locator('.mem-confirm').count() == 1 and not pro()['memDeletes'])
    r2.locator('.mem-confirm .btn:not(.danger)').click(); pg.wait_for_timeout(200)
    check('취소 → nothing deleted', r2.locator('.mem-confirm').count() == 0 and not pro()['memDeletes'] and rows().count() == 4)
    r2.locator('.mem-del').click(); r2.locator('.mem-confirm .btn.danger').click(); pg.wait_for_timeout(700)
    d = pro()['memDeletes']
    check('DELETE /v1/memory/items/{id} with X-Eve-Request + JSON', len(d) == 1 and d[0]['id'] == '01JMEM00000000000000000002' and d[0]['xer'] == '1' and (d[0]['ct'] or '').startswith('application/json'), d)
    check('row removed, count 3', rows().count() == 3 and pg.text_content('#memCount') == '3개' and len(pro()['memItems']) == 3)

    # 5) 404 → already gone
    put('/pro/set', {'memItems': [i for i in pro()['memItems'] if i['id'] != '01JMEM00000000000000000004']})
    r = pg.locator('#memList li[data-id="01JMEM00000000000000000004"]'); r.locator('.mem-del').click(); r.locator('.mem-confirm .btn.danger').click(); pg.wait_for_timeout(700)
    check('404 → row removed + 이미 지워진 항목', r.count() == 0 and '이미 지워진 항목이에요' in pg.text_content('#toast'))

    # 6) network failure on delete → row stays, retry toast
    put('/pro/set', {'memDelDrop': True})
    r = rows().nth(0); r.locator('.mem-del').click(); r.locator('.mem-confirm .btn.danger').click(); pg.wait_for_timeout(900)
    check('network failure → row kept + toast', rows().count() == 2 and '지우지 못했어요' in pg.text_content('#toast') and not r.locator('.mem-confirm .btn.danger').is_disabled())

    # 7) 503 memory_read_only on delete → read-only state
    put('/pro/set', {'memDelRO': True})
    r.locator('.mem-confirm .btn.danger').click(); pg.wait_for_timeout(700)
    check('503 memory_read_only → banner + toggle/deletes disabled', pg.is_visible('#memBanner') and pg.is_disabled('#sMemory') and pg.locator('#memList .mem-del:not([disabled])').count() == 0 and rows().count() == 2)
    put('/pro/set', {'memDelRO': False})

    # 8) system.memory_read_only from settings
    put('/pro/set', {'system': dict(SYS, memory_read_only=True)}); settings(); open_list()
    check('read_only: toggle disabled + explanation', pg.is_disabled('#sMemory') and '바꿀 수 없어요' in pg.text_content('#sMemNote') and pg.is_visible('#memBanner') and pg.locator('#memList .mem-del:not([disabled])').count() == 0)
    put('/pro/set', {'system': SYS, 'memMode': 'ro', 'settings': {'proactive': {'enabled': False, 'quiet_hours': {'start': '22:00', 'end': '08:00'}, 'memory_read': False}, 'memory': {'enabled': True}}}); settings()
    pg.click('label:has(#sMemory)'); pg.wait_for_timeout(600)
    check('PATCH 503 memory_read_only → rollback + disabled', pg.is_checked('#sMemory') and pg.is_disabled('#sMemory') and '설정을 저장하지 못했어요' in pg.text_content('#toast'))

    # 9) kill switch: system.memory_available=false, and /v1/memory 404 without the key
    put('/pro/set', {'memMode': 'off', 'system': dict(SYS, memory_available=False)}); settings()
    check('kill switch (system): toggle disabled + explanation, list closed', pg.is_disabled('#sMemory') and not pg.is_checked('#sMemory') and '쓸 수 없어요' in pg.text_content('#sMemNote') and pg.is_disabled('#memOpen') and not memGets()[-1:] == ['x'])
    put('/pro/set', {'memMode': 'off', 'system': SYS}); settings()
    check('kill switch (404 on /v1/memory) → disabled + explanation', pg.is_disabled('#sMemory') and '쓸 수 없어요' in pg.text_content('#sMemNote'))
    put('/pro/supported/off'); settings()
    check('settings 404 → unavailable', pg.is_disabled('#sMemory') and '쓸 수 없어요' in pg.text_content('#sMemNote'))
    put('/pro/supported/on')

    # 10) network failure loading the list → message + 다시 시도
    put('/pro/set', {'memMode': None}); settings(); put('/pro/set', {'memMode': 'drop'}); open_list()
    check('network failure → 다시 시도', pg.is_visible('#memRetry') and '불러오지 못했어요' in pg.text_content('#memState'))
    put('/pro/set', {'memMode': None}); pg.click('#memRetry'); pg.wait_for_timeout(700)
    check('retry → list shown', rows().count() == 2 and pg.is_hidden('#memRetry'))

    # 11) in-chat remember card: same §C path — 저장 verb, reissue → approve on press, SSE token ignored
    put('/pro/set', {'sseToken': True}); home(); pg.click('#newChat'); pg.wait_for_timeout(400); issued = pro()['issued']; n0 = len(pro()['bodies'])
    pg.fill('#input', 'confirmremember 커피'); pg.click('#sendBtn'); pg.wait_for_timeout(2000)
    c = pg.locator('.confirm-card[data-aid="01JACT0000000000000000000M"]')
    check('remember card: variant + 저장 verb + normalized text', c.count() == 1 and c.get_attribute('data-variant') == 'remember' and c.locator('.cc-primary').inner_text().strip() == '저장' and '커피는 디카페인' in c.inner_text())
    check('no reissue before press', pro()['issued'] == issued)
    c.locator('.cc-primary').click(); pg.wait_for_timeout(800)
    seq = [x for x in pro()['bodies'][n0:] if '0000000000000000000M/' in x['p']]
    check('press → reissue then approve with fresh token (SSE token ignored)', [x['p'].rsplit('/', 1)[1] for x in seq] == ['reissue', 'approve'] and seq[1]['b']['confirm_token'] != 'ssetok-must-be-ignored' and seq[1]['b']['payload_hash'] == 'sha256:mem' and c.get_attribute('data-state') == 'confirmed', seq)
    check('no tokens stored', not any(t in (pg.evaluate("JSON.stringify(localStorage)") or '') for t in ['confirm_token', 'ssetok', '"tok']))
    put('/pro/set', {'sseToken': False})
    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
