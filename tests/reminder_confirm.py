# 1.10.0 reminder confirm card on the shared .confirm-card (eve-serving #78: reminders_add / reminders_complete):
# exact Confirmation fields, labelled rows, approve flow, and the approve error outcomes (scope_denied, outcome_unknown, writes_disabled, not_found)
import json, os, urllib.request
from datetime import datetime
from playwright.sync_api import sync_playwright
M = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765'); B = M
def req(method, path, body=None):
    r = urllib.request.Request(M + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(r) as f: t = f.read(); return json.loads(t) if t else None
put = lambda p, body=None: req('PUT', p, body)
pro = lambda: req('PUT', '/__pro')
R = []
def check(name, ok, extra=''): R.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)
SETTINGS = "localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit',system:'',showThink:false,noThink:false}));"
ID = {'r': '01JACT0000000000000000000R', 'z': '01JACT0000000000000000000Z', 'c': '01JACT0000000000000000000C'}
YEAR = datetime.now().year
put('/auth/on'); put('/persist/on'); put('/db/reset'); put('/fail/clear'); put('/pro/reset')
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "localStorage.setItem('eve.mem.introSeen','1')}")
    pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    def card(i): return pg.locator(f'.confirm-card[data-aid="{i}"]')
    def ask(text, aid):
        put('/pro/reset'); pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(1200)
        if pg.evaluate("document.getElementById('app').dataset.route") != 'chat': pg.click('#newChat'); pg.wait_for_timeout(400)
        pg.fill('#input', text); pg.click('#sendBtn'); pg.wait_for_timeout(1800)
        return card(aid)
    def calls(aid):
        bs = pro()['bodies']; return [x for x in bs if x['p'] == f'/v1/actions/{aid}/reissue'], [x for x in bs if x['p'] == f'/v1/actions/{aid}/approve'], [x for x in bs if x['p'] == f'/v1/actions/{aid}' and x['m'] == 'GET']
    def press(c, wait=900): c.locator('.cc-primary').click(); pg.wait_for_timeout(wait)
    def settled_text(c): return c.locator('.cc-result').inner_text()
    def no_buttons(c): return c.locator('.cc-actions').is_hidden()

    # ---- reminders_add: exact #78 Confirmation, rendered by the shared card
    c = ask('confirmreminder 엄마께 전화', ID['r'])
    check('card on the shared component, tool variant', c.count() == 1 and c.get_attribute('data-variant') == 'tool' and c.get_attribute('data-state') == 'pending')
    check('title = summary "리마인더 추가"', c.locator('.cc-title').inner_text() == '리마인더 추가', c.locator('.cc-title').inner_text())
    rows = c.evaluate("e => [...e.querySelectorAll('.cc-view dt')].map(t => [t.dataset.k, t.textContent, t.nextElementSibling.textContent])")
    check('rows in order: 제목 / 시간 / 목록 (no method, no verb row)', [r[1] for r in rows] == ['제목', '시간', '목록'] and [r[0] for r in rows] == ['title', 'when', 'list'], rows)
    yr = '' if YEAR == 2026 else '2026/'
    check('title shown verbatim as text (no HTML)', rows[0][2] == '엄마께 전화 <b>드리기</b>' and c.locator('.cc-view b').count() == 0, rows)
    check('due (no display sent) → KST 24h fallback: 10/28 (수) 18:00', rows[1][2] == yr + '10/28 (수) 18:00', rows[1])
    check('no raw RFC3339 / method / verb in the rows', '2026-10-28T' not in c.locator('.cc-view').inner_text() and 'reminders.add' not in c.inner_text())
    check('list row', rows[2][2] == '개인')
    check('primary 추가, accent (write scope is not danger)', c.locator('.cc-primary').inner_text() == '추가' and 'cc-danger' not in c.locator('.cc-primary').get_attribute('class'))
    check('secondary 취소', c.locator('.cc-secondary').inner_text() == '취소')
    check('no token was fetched on render', not calls(ID['r'])[0])
    press(c)
    ri, ap, ge = calls(ID['r'])
    check('press → one reissue then one approve {confirm_token, payload_hash}', len(ri) == 1 and len(ap) == 1 and set(ap[0]['b']) == {'confirm_token', 'payload_hash'} and ap[0]['b']['payload_hash'] == 'sha256:rem', [ri, ap])
    check('confirmed: 추가했어요', c.get_attribute('data-state') == 'confirmed' and '추가했어요' in c.inner_text(), c.inner_text())

    # ---- optional fields absent: only the rows that are there
    c = ask('confirmreminder0 우유', ID['z'])
    rows = c.evaluate("e => [...e.querySelectorAll('.cc-view dt')].map(t => t.textContent)")
    check('no due; list absent → 제목 + 기본 목록 (no 시간 row)', rows == ['제목', '목록'] and c.locator('.cc-view dd').nth(1).inner_text() == '기본 목록', rows)

    # ---- reminders_complete: verb update, no due
    c = ask('confirmcomplete 세금', ID['c'])
    rows = c.evaluate("e => [...e.querySelectorAll('.cc-view dt')].map(t => [t.textContent, t.nextElementSibling.textContent])")
    check('complete: title 리마인더 완료 처리, rows 제목/목록', c.locator('.cc-title').inner_text() == '리마인더 완료 처리' and rows == [['제목', '세금 납부'], ['목록', '개인']], [c.locator('.cc-title').inner_text(), rows])
    check('complete: payload_view.verb update → 변경 (design verb mapping), not danger', c.locator('.cc-primary').inner_text() == '변경' and 'cc-danger' not in c.locator('.cc-primary').get_attribute('class'))
    press(c)
    check('complete: confirmed 변경했어요', c.get_attribute('data-state') == 'confirmed' and '변경했어요' in c.inner_text(), c.inner_text())
    c.screenshot(path='/tmp/rc_done.png')

    # ---- approve outcomes
    def case(name, setup, aid=ID['r'], wait=900):
        c = ask('confirmreminder 엄마께', aid); put('/pro/set', setup); press(c, wait); return c
    c = case('scope_denied', {'actCode': {'approve': [403, 'scope_denied']}})
    ri, ap, ge = calls(ID['r'])
    check('403 scope_denied → denied, 권한 copy, no buttons, no retry, approve sent once', c.get_attribute('data-state') == 'denied' and '할 수 있는 권한' in settled_text(c) and no_buttons(c) and len(ap) == 1, [c.get_attribute('data-state'), settled_text(c)])
    c = case('kill_switch', {'approveCode': [403, 'kill_switch']})
    check('403 kill_switch (the wire form of writes_disabled) → denied "지금은 이 기능을 쓸 수 없어요", no retry', c.get_attribute('data-state') == 'denied' and '이 기능을 쓸 수 없어요' in settled_text(c) and no_buttons(c), settled_text(c))
    c = case('writes_disabled', {'approveCode': [403, 'writes_disabled']})
    check('writes_disabled code → denied, own copy, no retry', c.get_attribute('data-state') == 'denied' and '쓰기가 꺼져' in settled_text(c) and no_buttons(c), settled_text(c))
    c = case('item_gone', {'approveCode': [409, 'item_gone']})
    check('409 item_gone (wire form of not_found on complete) → denied, 지워진 항목', c.get_attribute('data-state') == 'denied' and '지워진' in settled_text(c) and no_buttons(c), settled_text(c))
    c = case('not_found', {'approveCode': [404, 'not_found']})
    check('404 not_found → denied 대상을 찾을 수 없어요, no retry', c.get_attribute('data-state') == 'denied' and '대상을 찾을 수 없어요' in settled_text(c) and no_buttons(c), settled_text(c))
    c = case('502 not_found', {'approveRaw': [502, {'status': 'error', 'action_id': ID['r'], 'error_code': 'not_found', 'outcome_unknown': False}]})
    check('502 outcome_unknown:false + not_found → denied, no retry', c.get_attribute('data-state') == 'denied' and no_buttons(c), [c.get_attribute('data-state'), settled_text(c)])

    # outcome_unknown: the card is consumed; no retry, no re-approve, no recheck
    c = case('outcome_unknown', {'approveRaw': [502, {'status': 'error', 'action_id': ID['r'], 'error_code': 'timeout', 'outcome_unknown': True}]}, wait=3500)
    ri, ap, ge = calls(ID['r'])
    t = settled_text(c)
    check('502 outcome_unknown → error state, 미리 알림 앱에서 확인 copy', c.get_attribute('data-state') == 'error' and '확인하지 못했어요' in t and '미리 알림' in t, [c.get_attribute('data-state'), t])
    check('outcome_unknown: no buttons at all (no 다시 시도, no 취소)', no_buttons(c) and c.locator('.cc-again').is_hidden() and c.locator('button:visible').count() == 0, c.inner_html()[:400])
    check('outcome_unknown: exactly one reissue + one approve, no recheck GET /v1/actions/{id}', len(ri) == 1 and len(ap) == 1 and len(ge) == 0, [len(ri), len(ap), len(ge)])
    pg.wait_for_timeout(2500); ri, ap, ge = calls(ID['r'])
    check('outcome_unknown: still nothing re-sent after 2.5s', len(ri) == 1 and len(ap) == 1 and len(ge) == 0, [len(ri), len(ap), len(ge)])
    c = case('bare 502', {'approveRaw': [502, {}]}, wait=1500)
    ri, ap, ge = calls(ID['r'])
    check('bare 502 without body (proxy) → treated as unknown: no retry, no recheck', c.get_attribute('data-state') == 'error' and no_buttons(c) and len(ap) == 1 and len(ge) == 0, [c.get_attribute('data-state'), len(ap), len(ge)])
    c = case('504 bare', {'approveRaw': [504, {}]}, wait=1500)
    check('bare 504 → same', c.get_attribute('data-state') == 'error' and no_buttons(c), c.get_attribute('data-state'))

    # outcome_unknown:false (card released server-side): retry is allowed and works
    c = case('released', {'approveRaw': [502, {'status': 'error', 'action_id': ID['r'], 'error_code': 'permission_denied', 'outcome_unknown': False}]})
    check('502 outcome_unknown:false + permission_denied → error with 다시 시도, permission copy', c.get_attribute('data-state') == 'error' and '접근이 허용되지 않았어요' in settled_text(c) and c.locator('.cc-primary').inner_text() == '다시 시도' and c.locator('.cc-secondary').is_hidden(), [settled_text(c), c.locator('.cc-primary').inner_text()])
    press(c)
    ri, ap, ge = calls(ID['r'])
    check('retry → fresh reissue + approve, then confirmed', len(ri) == 2 and len(ap) == 2 and ap[0]['b']['confirm_token'] != ap[1]['b']['confirm_token'] and c.get_attribute('data-state') == 'confirmed', [len(ri), len(ap), c.get_attribute('data-state')])
    for code, frag in [('pim_unavailable', '연결하지 못했어요'), ('timeout', '응답이 늦어서'), ('weird_new_code', '실행하지 못했어요')]:
        c = case(code, {'approveRaw': [502, {'status': 'error', 'action_id': ID['r'], 'error_code': code, 'outcome_unknown': False}]})
        check(f'outcome_unknown:false + {code} → generic/known copy, retry offered', c.get_attribute('data-state') == 'error' and frag in settled_text(c) and c.locator('.cc-primary').inner_text() == '다시 시도', settled_text(c))

    b.close()
check('no page errors', not errs, errs)
print(f'{sum(R)}/{len(R)}'); raise SystemExit(0 if all(R) else 1)
