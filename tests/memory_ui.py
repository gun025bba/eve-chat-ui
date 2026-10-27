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
SYS = {'proactive_available': True, 'tools_available': True, 'memory_read_only': False, 'memory_available': True}
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
    check('version 1.5.0', pg.evaluate('__app.version') == '1.5.0')
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

    # 3) list: order pinned → live task → updated desc, text only; spec strings
    open_list()
    t = [rows().nth(i).locator('.mem-text').inner_text() for i in range(rows().count())]
    check('list order', t[:3] == ['이름은 건영', '다음 주 발표 준비 중', '<img src=x onerror=alert(1)> 고양이 이름은 나비'] and len(t) == 4, t)
    check('text rendered as text (no injected img)', pg.locator('#memList img').count() == 0)
    check('meta: 고정됨 · 프로필 / 대화에서', '고정됨' in rows().nth(0).inner_text() and '대화에서' in rows().nth(3).inner_text() and '만료' in rows().nth(1).inner_text())
    check('off footer string', pg.text_content('#sMemNote') == '꺼져 있어요. 저장된 메모리는 남아 있지만 대화에 쓰지 않아요')

    # 4) single delete: no confirm, toast '삭제됨 · 되돌리기' 2.8s, DELETE after it closes; undo cancels
    r2 = rows().nth(3); rid = r2.get_attribute('data-id'); r2.locator('.mem-del').click(); pg.wait_for_timeout(300)
    tb = pg.evaluate("(()=>{const t=document.getElementById('memToast').getBoundingClientRect(),d=document.getElementById('settings').getBoundingClientRect();return [Math.round(d.bottom-t.bottom), Math.round(t.top)]})()")
    check('undo toast pinned near sheet bottom (short list)', 0 <= tb[0] <= 60, tb)
    check('no confirm sheet, row hidden, toast + 되돌리기 + first-time backup note', pg.locator('.mem-confirm').count() == 0 and rows().count() == 3 and '삭제됨' in pg.text_content('#memToastText') and '백업에는 최대 7일 남아요' in pg.text_content('#memToastText') and pg.text_content('#memToastAct') == '되돌리기' and not pro()['memDeletes'])
    pg.click('#memToastAct'); pg.wait_for_timeout(3200)
    check('되돌리기 → row back, no DELETE', rows().count() == 4 and not pro()['memDeletes'])
    pg.locator(f'#memList li[data-id="{rid}"] .mem-del').click(); pg.wait_for_timeout(300)
    check('backup note only the first time', '백업에는' not in pg.text_content('#memToastText'))
    check('DELETE not sent while toast open', not pro()['memDeletes']); pg.wait_for_timeout(3000)
    d = pro()['memDeletes']
    check('DELETE /v1/memory/items/{id} after toast, X-Eve-Request', len(d) == 1 and d[0]['id'] == rid and d[0]['xer'] == '1', d)
    check('count 3', rows().count() == 3 and pg.text_content('#memCount') == '3개' and len(pro()['memItems']) == 3)

    # 5) pagehide commits a pending delete at once
    r = rows().nth(2); rid2 = r.get_attribute('data-id'); r.locator('.mem-del').click(); pg.wait_for_timeout(200)
    pg.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'))"); pg.wait_for_timeout(500)
    check('pagehide → DELETE immediately', [x['id'] for x in pro()['memDeletes']][-1:] == [rid2])

    # 6) add + edit (POST/PATCH strict bodies), error codes
    pg.click('#memAdd'); pg.select_option('#memKind', 'fact'); pg.fill('#memText', '강아지 이름은 콩이'); pg.click('#memFormSave'); pg.wait_for_timeout(700)
    w = pro()['memWrites'][-1]
    check('add → POST {kind,text} + row', w['method'] == 'POST' and w['body'] == {'kind': 'fact', 'text': '강아지 이름은 콩이'} and '강아지 이름은 콩이' in pg.inner_text('#memList') and pg.is_hidden('#memForm'), w)
    for txt, want in [('my password is hunter2', '비밀번호·키·카드번호처럼 보이는 내용은 저장할 수 없어요'), ('x' * 300 + 'y', '300자까지 쓸 수 있어요')]:
        pg.click('#memAdd'); pg.evaluate("t=>{const e=document.getElementById('memText');e.removeAttribute('maxlength');e.value=t}", txt); pg.click('#memFormSave'); pg.wait_for_timeout(600)
        check('add error text: ' + want[:12], want in pg.text_content('#memFormErr'), pg.text_content('#memFormErr'))
    put('/pro/set', {'memCap': 1}); pg.fill('#memText', '하나 더'); pg.click('#memFormSave'); pg.wait_for_timeout(600)
    check('cap_exceeded text', '메모리가 가득 찼어요' in pg.text_content('#memFormErr'))
    put('/pro/set', {'memCap': 200, 'memMode': 'e500'}); pg.click('#memFormSave'); pg.wait_for_timeout(600)
    check('500 legacy {error:{code:internal_error}} → text + 다시 시도', '저장하지 못했어요. 잠시 후 다시 시도해 주세요' in pg.text_content('#memFormErr') and pg.locator('#memFormErr button').inner_text() == '다시 시도')
    put('/pro/set', {'memMode': None}); pg.click('#memFormErr button'); pg.wait_for_timeout(700)
    check('다시 시도 → saved', '하나 더' in pg.inner_text('#memList') and pg.is_hidden('#memForm'))
    r = pg.locator('#memList li', has_text='강아지 이름은 콩이'); r.locator('.mem-edit').click(); pg.fill('#memText', '강아지 이름은 콩순이'); pg.click('#memFormSave'); pg.wait_for_timeout(700)
    w = pro()['memWrites'][-1]
    check('edit → PATCH {text, if_updated_at}', w['method'] == 'PATCH' and set(w['body']) == {'text', 'if_updated_at'} and '콩순이' in pg.inner_text('#memList'), w)

    # 7) 503 legacy memory_read_only on a write → banner + re-read settings; toggle stays usable
    put('/pro/set', {'memMode': 'ro'}); nset = len([x for x in pro()['bodies'] if x['p'] == '/v1/settings' and x['m'] == 'GET'])
    rows().nth(0).locator('.mem-del').click(); pg.wait_for_timeout(3400)
    check('503 memory_read_only → banner + sub-line, writes disabled, toggle usable', pg.is_visible('#memBanner') and '저장된 메모리는 그대로 있고, 곧 다시 쓸 수 있어요' in pg.text_content('#memBanner') and pg.is_disabled('#memAdd') and pg.is_disabled('#memWipe') and pg.locator('#memList .mem-del:not([disabled])').count() == 0 and not pg.is_disabled('#sMemory'))
    check('settings re-read', len([x for x in pro()['bodies'] if x['p'] == '/v1/settings' and x['m'] == 'GET']) > nset)

    # 8) system.memory_read_only is ignored (read-only only from a 503)
    put('/pro/set', {'memMode': None, 'system': dict(SYS, memory_read_only=True)}); settings(); open_list()
    check('system.memory_read_only ignored: writes enabled', rows().count() > 0 and pg.is_hidden('#memBanner') and not pg.is_disabled('#memAdd') and not pg.is_disabled('#memWipe'))
    put('/pro/set', {'system': SYS})

    # 9) system.memory_available=false (server kill switch) → toggle disabled + footer, list closed; missing memory key → off
    put('/pro/set', {'memMode': 'availOff'}); n0 = len(memGets()); settings()
    check('memory_available=false → toggle disabled + footer', pg.is_visible('#memSection') and pg.is_disabled('#sMemory') and not pg.is_checked('#sMemory') and pg.text_content('#sMemNote') == '지금은 메모리 기능을 쓸 수 없어요')
    open_list()
    check('memory_available=false → read-only banner on memory screen, writes disabled, export allowed', pg.is_visible('#memBanner') and pg.is_disabled('#memAdd') and pg.is_disabled('#memWipe') and pg.is_visible('#memExport') and not pg.is_disabled('#memExport'))
    put('/pro/set', {'memMode': None, 'system': {k: v for k, v in SYS.items() if k != 'memory_available'}}); settings()
    check('memory_available missing → treated as true', not pg.is_disabled('#sMemory'))
    put('/pro/set', {'system': SYS})
    put('/pro/set', {'memMode': None, 'memNoKey': True}); settings()
    check('missing memory key → toggle off + off footer', not pg.is_checked('#sMemory') and not pg.is_disabled('#sMemory') and pg.text_content('#sMemNote').startswith('꺼져 있어요'))
    put('/pro/set', {'memNoKey': False})

    # 10) {"detail":"Not Found"} on /v1/memory* → section hidden (not an error); on PATCH too
    put('/pro/set', {'memMode': 'gone'}); settings()
    check('detail 404 on list → section hidden, no error', pg.is_hidden('#memSection'))
    put('/pro/set', {'memMode': None}); settings(); open_list()
    put('/pro/set', {'memMode': 'e429'}); rows().nth(0).locator('.mem-edit').click(); pg.fill('#memText', '바뀐 내용'); pg.click('#memFormSave'); pg.wait_for_timeout(600)
    check('PATCH 429 {error:{code:rate_limited}} → busy text + 다시 시도', '지금 요청이 많아요. 잠시 후 다시 시도해 주세요' in pg.text_content('#memFormErr') and pg.locator('#memFormErr button').count() == 1)
    put('/pro/set', {'memMode': 'gone'}); pg.click('#memFormSave'); pg.wait_for_timeout(600)
    check('PATCH detail 404 → section hidden', pg.is_hidden('#memSection'))
    put('/pro/set', {'memMode': None})

    # 10b) 44pt targets, accent +, export row
    settings(); open_list()
    sz = pg.evaluate("['#memAdd','#memWipe','#memExport','.mem-edit','.mem-del'].map(q=>{const r=document.querySelector(q).getBoundingClientRect();return [q,Math.round(r.height),Math.round(r.width)]})")
    check('all memory buttons ≥ 44pt high (and + ≥ 44 wide)', all(h_ >= 44 for _, h_, _w in sz) and sz[0][2] >= 44, sz)
    check('+ uses --accent', pg.evaluate("getComputedStyle(document.querySelector('#memAdd')).color === getComputedStyle(document.querySelector('.mem-edit')).color"))
    check('count line N / 200 + export group before wipe group', pg.text_content('#memTotal').endswith('/ 200') and pg.evaluate("document.getElementById('memExportGroup').compareDocumentPosition(document.getElementById('memWipe')) & 4"))
    with pg.expect_download() as dl: pg.click('#memExport')
    import re as _re
    check('export → eve-memory-YYYY-MM-DD.json download', _re.fullmatch(r'eve-memory-\d{4}-\d{2}-\d{2}\.json', dl.value.suggested_filename) is not None and pro()['bodies'][-1]['p'] == '/v1/memory/export', dl.value.suggested_filename)
    put('/pro/set', {'memMode': 'drop'}); pg.click('#memExport'); pg.wait_for_timeout(600)
    check('export failure → 내보내지 못했어요', '내보내지 못했어요' in pg.text_content('#memToastText') and pg.text_content('#memExport') == '메모리 내보내기')
    put('/pro/set', {'memMode': None})

    # 11) list load: network failure → error + 다시 시도; empty state; 모두 지우기 sheet
    put('/pro/set', {'memMode': None}); settings(); put('/pro/set', {'memMode': 'drop'}); open_list()
    check('load error → 메모리를 불러오지 못했어요 + 다시 시도', pg.is_visible('#memRetry') and pg.text_content('#memState') == '메모리를 불러오지 못했어요')
    put('/pro/set', {'memMode': None}); pg.click('#memRetry'); pg.wait_for_timeout(700)
    check('retry → list shown', rows().count() > 0 and pg.is_hidden('#memRetry'))
    pg.click('#memWipe'); pg.wait_for_timeout(200)
    check('모두 지우기 sheet text', pg.is_visible('#memWipeSheet') and '모든 메모리를 지울까요? 백업 사본도 복구할 수 없게 돼요.' in pg.text_content('#memWipeSheet') and 'danger' in pg.get_attribute('#memWipeYes', 'class'))
    pg.click('#memWipeNo'); check('취소 → nothing', pg.is_hidden('#memWipeSheet') and pro()['memItems'], [pg.is_hidden('#memWipeSheet'), len(pro()['memItems'])])
    pg.click('#memWipe'); pg.click('#memWipeYes'); pg.wait_for_timeout(700)
    w = pro()['memWrites'][-1]
    check('DELETE /v1/memory → empty state', w['method'] == 'DELETE' and w['path'] == '/v1/memory' and not pro()['memItems'] and pg.is_hidden('#memExport') and '아직 기억한 게 없어요' in pg.text_content('#memState') and "대화 중에 '기억해'라고 하거나 + 로 직접 추가할 수 있어요" in pg.text_content('#memState'))

    # 12) in-chat remember card: same §C path — 저장 verb, reissue → approve on press, SSE token ignored
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
    # 13) card approve errors: 500/503 legacy bodies, unknown code → invalid
    for st_, code, kind, want in [(500, 'internal_error', 'legacy', '저장하지 못했어요. 잠시 후 다시 시도해 주세요'), (503, 'memory_read_only', 'legacy', '지금은 메모리를 바꿀 수 없어요'), (422, 'weird_new_code', 'ec', '요청 내용이 올바르지 않아 진행하지 않았어요'), (403, 'kill_switch', 'ec', '지금은 이 기능을 쓸 수 없어요'), (403, 'scope_denied', 'reissue', '이 작업은 할 수 있는 권한이 없어요')]:
        put('/pro/reset'); home(); pg.click('#newChat'); pg.wait_for_timeout(300)
        put('/pro/set', {'actCode': {'reissue': [st_, code]}} if kind == 'reissue' else {'approveLegacy' if kind == 'legacy' else 'approveCode': [st_, code]})
        pg.fill('#input', 'confirmremember 커피'); pg.click('#sendBtn'); pg.wait_for_timeout(1800)
        c = pg.locator('.confirm-card[data-aid="01JACT0000000000000000000M"]').last; c.locator('.cc-primary').click(); pg.wait_for_timeout(900)
        check(f'card {st_} {code} → text', want in c.inner_text(), c.inner_text())
        if code == 'internal_error': check('500 → 다시 시도 offered', '다시 시도' in c.inner_text())
    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
