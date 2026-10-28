# 1.10.0 M1: calendar_add_event / reminders_add / reminders_complete confirm cards on the one shared PIM card (eve-serving #66 §11.4)
import json, os, urllib.request
from datetime import date, datetime, timedelta, timezone
from playwright.sync_api import sync_playwright
M = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765'); B = M
def req(method, path, body=None):
    r = urllib.request.Request(M + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(r) as f: t = f.read(); return json.loads(t) if t else None
put = lambda p, body=None: req('PUT', p, body)
R = []
def check(name, ok, extra=''): R.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)
SETTINGS = "localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit',system:'',showThink:false,noThink:false}));"
Y = datetime.now(timezone(timedelta(hours=9))).year
WD28 = '월화수목금토일'[date(Y, 10, 28).weekday()]
PFX = '01JBX0000000000000000000'
put('/auth/on'); put('/persist/on'); put('/db/reset'); put('/fail/clear'); put('/pro/reset')
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "localStorage.setItem('eve.mem.introSeen','1')}")
    pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    def status(): return pg.evaluate("([...document.querySelectorAll('.msg.assistant .ws-status')].pop()||{}).textContent||''")
    def ask(text, aid, wait=2300):
        put('/pro/reset'); pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(1200)
        if pg.evaluate("document.getElementById('app').dataset.route") != 'chat': pg.evaluate("__app.newChat()"); pg.wait_for_timeout(400)
        pg.fill('#input', text); pg.click('#sendBtn'); pg.wait_for_timeout(350)
        st = status(); pg.wait_for_timeout(wait)
        return pg.locator(f'.confirm-card[data-aid="{PFX}{aid}"]'), st
    rows = lambda c: c.evaluate("e => [...e.querySelectorAll('.cc-view dt')].map(t => [t.dataset.k, t.textContent, t.nextElementSibling.textContent])")

    c, st = ask('pimadd 치과 일정', 'C1')
    check('prep status while the write is proposed', st == '확인 카드를 준비하는 중…', st)
    check('shared card, tool variant, title = 일정 추가, one stack, no read/error card', c.count() == 1 and c.get_attribute('data-variant') == 'tool' and c.locator('.cc-title').inner_text() == '일정 추가' and pg.locator('.pim-card').count() == 0 and pg.locator('.cc-stack').count() == 1, c.count())
    r = rows(c)
    check('rows: 제목 · 시간 · 캘린더 · 장소 (메모 null → no row)', [x[1] for x in r] == ['제목', '시간', '캘린더', '장소'], r)
    check('시간 = server `display` as given', r[1][2] == f'10/28 ({WD28}) 15:00–16:00', r[1])
    check('캘린더 = server `calendar` name; 장소 text', r[2][2] == '개인' and r[3][2] == '역삼동 치과', r)
    txt = c.locator('.cc-view').inner_text()
    check('id/start/end/all_day/calendar_id/verb never shown', all(w not in txt for w in ['cal_1', 'T15:00', 'all_day', 'verb', '+09:00']) and all(x[0] not in ('start', 'end', 'all_day', 'calendar_id', 'verb', 'id') for x in r), txt)
    check('primary 추가 (accent, not danger)', c.locator('.cc-primary').inner_text() == '추가' and 'cc-danger' not in c.locator('.cc-primary').get_attribute('class'))
    c.locator('.cc-primary').click(); pg.wait_for_timeout(900)
    check('confirmed 추가했어요', c.get_attribute('data-state') == 'confirmed' and '추가했어요' in c.inner_text(), c.inner_text())
    c.screenshot(path='/tmp/pc_event_done.png')

    c, st = ask('pimaddall 가족 모임', 'C2')
    r = rows(c)
    check('all-day multi-day: display as given; 메모 row, no 장소 row', [x[1] for x in r] == ['제목', '시간', '캘린더', '메모'] and r[1][2] == '10/30 (금) – 11/1 (일) 종일' and r[3][2] == '케이크 챙기기', r)
    c, st = ask('pimaddnull 기본', 'C3')
    r = rows(c)
    check('calendar_id null → 기본 캘린더', r[2][1] == '캘린더' and r[2][2] == '기본 캘린더', r)

    c, st = ask('pimremadd 우유', 'A1')
    r = rows(c)
    check('reminders_add: rows 제목 · 시간 · 목록; list null → 기본 목록; display as given', [x[1] for x in r] == ['제목', '시간', '목록'] and r[1][2] == f'10/28 ({WD28}) 18:00' and r[2][2] == '기본 목록', r)
    check('reminders_add card title/verb', c.locator('.cc-title').inner_text() == '리마인더 추가' and c.locator('.cc-primary').inner_text() == '추가')
    c, st = ask('pimremdone 완료', 'D1')
    r = rows(c); txt = c.inner_text()
    check('reminders_complete: id hidden, rows 제목 · 시간 · 목록, verb update → 변경 (not danger)', [x[1] for x in r] == ['제목', '시간', '목록'] and 'rem_b1' not in txt and c.locator('.cc-primary').inner_text() == '변경' and 'cc-danger' not in c.locator('.cc-primary').get_attribute('class'), (r, txt))
    check('list name shown', r[2][2] == '장보기')

    # ---- display wins over the raw fields; method tolerated and hidden; no due → 기한 없음; unknown extra key stays visible
    put('/pro/reset')
    sd = put('/pro/seed', {'title': '일정', 'actions': [
        {'action_id': PFX + 'S1', 'tool': 'calendar_add_event', 'tool_version': '1', 'summary': '일정 추가', 'scopes': ['calendar.write'], 'payload_hash': 'sha256:s1', 'expires_at': (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime('%Y-%m-%dT%H:%M:%SZ'),
         'provenance': {'actor': 'user'}, 'tainted': False, 'payload_view': {'verb': 'add', 'method': 'calendar.add_event', 'title': '<i>회의</i>', 'start': '2026-10-28T09:00:00+09:00', 'end': '2026-10-28T10:00:00+09:00', 'all_day': False,
          'display': '서버가 만든 표시', 'location': None, 'notes': None, 'calendar_id': None, 'calendar': '기본 캘린더', 'zzz': '새 필드'}, '_text': '추가할까요?'},
        {'action_id': PFX + 'S2', 'tool': 'reminders_add', 'tool_version': '1', 'summary': '리마인더 추가', 'scopes': ['reminders.write'], 'payload_hash': 'sha256:s2', 'expires_at': (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime('%Y-%m-%dT%H:%M:%SZ'),
         'provenance': {'actor': 'user'}, 'tainted': False, 'payload_view': {'verb': 'add', 'title': '산책', 'due': None, 'display': None, 'list': '개인'}, '_text': '추가할까요?'},
        {'action_id': PFX + 'S3', 'tool': 'calendar_add_event', 'tool_version': '1', 'summary': '일정 추가', 'scopes': ['calendar.write'], 'payload_hash': 'sha256:s3', 'expires_at': (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime('%Y-%m-%dT%H:%M:%SZ'),
         'provenance': {'actor': 'user'}, 'tainted': False, 'payload_view': {'verb': 'add', 'title': '디스플레이 없음', 'start': '2027-01-05T09:00:00+09:00', 'end': '2027-01-05T10:00:00+09:00', 'all_day': False, 'display': None, 'location': None, 'notes': None, 'calendar_id': 'cal_9', 'calendar': None}, '_text': '추가할까요?'}]})
    pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(1200)
    pg.evaluate("[...document.querySelectorAll('#convList li.row .row-main')].find(r => r.textContent.includes('일정'))?.click()"); pg.wait_for_timeout(1200)
    c1 = pg.locator(f'.confirm-card[data-aid="{PFX}S1"]'); r = rows(c1)
    check('restored card: display shown as given (not recomputed), method hidden, title is text', r[1][2] == '서버가 만든 표시' and c1.locator('.cc-view i').count() == 0 and 'calendar.add_event' not in c1.inner_text() and r[0][2] == '<i>회의</i>', r)
    check('unknown extra key stays visible (never silently dropped)', any(x[0] == 'zzz' and x[2] == '새 필드' for x in r), r)
    r = rows(pg.locator(f'.confirm-card[data-aid="{PFX}S2"]'))
    check('due null / display null → 시간 기한 없음; list as given', r[1][1:] == ['시간', '기한 없음'] and r[2][2] == '개인', r)
    r = rows(pg.locator(f'.confirm-card[data-aid="{PFX}S3"]'))
    check('display null → KST fallback from start/end (other year shows year); calendar name null + id → 선택한 캘린더', r[1][2] == '2027/1/5 (화) 09:00–10:00' and r[2][2] == '선택한 캘린더', r)
    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
