# 1.10.0 M1 UI contract (eve-serving #66 §11): PIM tool_call/tool_result copy, read cards, error card, KST display, saved briefing message
import json, os, re, urllib.request
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
KST = timezone(timedelta(hours=9)); Y = datetime.now(KST).year
WD = '월화수목금토일'
def wd(y, m, d): return WD[date(y, m, d).weekday()]
D28 = f'10/28 ({wd(Y, 10, 28)})'
put('/auth/on'); put('/persist/on'); put('/db/reset'); put('/fail/clear'); put('/pro/reset')
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "localStorage.setItem('eve.mem.introSeen','1')}")
    pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    def fresh():
        put('/pro/reset'); pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(1200)
        if pg.evaluate("document.getElementById('app').dataset.route") != 'chat': pg.evaluate("__app.newChat()"); pg.wait_for_timeout(400)
    def status(): return pg.evaluate("([...document.querySelectorAll('.msg.assistant .tline:not(.out) .tstat')].pop()||{}).textContent||''")
    def ask(text):
        fresh(); pg.fill('#input', text); pg.click('#sendBtn')

    # ---- KST formatter (contract §11.4), now fixed to 2026-10-28 KST
    F = lambda a, e, ad: pg.evaluate("([a,e,ad]) => EvePim.fmtRange(a, e, ad, Date.parse('2026-10-28T12:00:00+09:00'))", [a, e, ad])
    fresh()
    check('same day: 10/28 (수) 15:00–16:00', F('2026-10-28T15:00:00+09:00', '2026-10-28T16:00:00+09:00', False) == '10/28 (수) 15:00–16:00', F('2026-10-28T15:00:00+09:00', '2026-10-28T16:00:00+09:00', False))
    check('crossing midnight: 10/28 (수) 23:00 – 10/29 (목) 01:00', F('2026-10-28T23:00:00+09:00', '2026-10-29T01:00:00+09:00', False) == '10/28 (수) 23:00 – 10/29 (목) 01:00', F('2026-10-28T23:00:00+09:00', '2026-10-29T01:00:00+09:00', False))
    check('all-day single (end exclusive): 10/28 (수) 종일', F('2026-10-28T00:00:00+09:00', '2026-10-29T00:00:00+09:00', True) == '10/28 (수) 종일')
    check('all-day multi: end date inclusive (end − 1 day)', F('2026-10-30T00:00:00+09:00', '2026-11-02T00:00:00+09:00', True) == '10/30 (금) – 11/1 (일) 종일', F('2026-10-30T00:00:00+09:00', '2026-11-02T00:00:00+09:00', True))
    check('other year gets the year: 2027/1/5 (화) 09:00–10:00', F('2027-01-05T09:00:00+09:00', '2027-01-05T10:00:00+09:00', False) == '2027/1/5 (화) 09:00–10:00', F('2027-01-05T09:00:00+09:00', '2027-01-05T10:00:00+09:00', False))
    check('other offset converted to KST (00:30Z = 09:30 KST), no suffix', F('2026-10-28T00:30:00Z', '2026-10-28T01:00:00Z', False) == '10/28 (수) 09:30–10:00')
    check('24h clock, zero padded, midnight = 00:00 (not 24:00)', F('2026-10-29T00:05:00+09:00', '2026-10-29T00:50:00+09:00', False) == '10/29 (목) 00:05–00:50')
    check('no end → start only; garbage → as written, no throw', F('2026-10-28T09:00:00+09:00', None, False) == '10/28 (수) 09:00' and F('내일', None, False) == '내일')
    check('year rule is KST-based (Dec 31 23:30 KST = Dec 31 14:30Z)', pg.evaluate("EvePim.fmtDue('2026-12-31T23:30:00+09:00', Date.parse('2026-12-31T14:30:00Z'))") == '12/31 (목) 23:30')
    check('due formatter: 10/28 (수) 18:00', pg.evaluate("EvePim.fmtDue('2026-10-28T18:00:00+09:00', Date.parse('2026-10-28T12:00:00+09:00'))") == '10/28 (수) 18:00')

    # ---- read: calendar_list_events
    ask('pimcal 오늘 일정'); pg.wait_for_timeout(350)
    check('call status: 일정 확인 중… (never the web-search copy)', status() == '일정 확인 중…', status())
    pg.wait_for_timeout(1300)
    c = pg.locator('.pim-card[data-kind=calendar_events]')
    check('calendar card shown after tool_result', c.count() == 1, c.count())
    rows = c.locator('.pc-row').evaluate_all("rs => rs.map(r => [r.querySelector('.pc-ti').textContent, r.querySelector('.pc-meta')?.textContent || ''])")
    check('5 items, header 일정 5건', len(rows) == 5 and '일정 5건' in c.locator('.bc-head').inner_text(), rows)
    check('timed event: time · calendar', rows[0][1] == f'{D28} 09:30–10:00 · 회사', rows[0])
    check('all-day event: 종일', rows[1][1] == f'{D28} 종일 · 개인', rows[1])
    check('crossing midnight', rows[2][1] == f'{D28} 23:00 – 10/29 ({wd(Y, 10, 29)}) 01:00 · 회사', rows[2])
    check('multi-day all-day, end inclusive', rows[3][1] == f'10/30 ({wd(Y, 10, 30)}) – 11/1 ({wd(Y, 11, 1)}) 종일 · 개인', rows[3])
    check('other year shows the year', rows[4][1] == f'{Y + 1}/1/5 ({wd(Y + 1, 1, 5)}) 09:00–10:00 · 개인', rows[4])
    check('untrusted title is text only (no <img>, no alert)', rows[0][0].startswith('팀 스탠드업 <img') and c.locator('img').count() == 0 and pg.locator('.pim-card img').count() == 0, rows[0])
    check('range label in header', f'{D28} – 11/2' in c.locator('.pc-sub').inner_text() or '10/28' in c.locator('.pc-sub').inner_text(), c.locator('.pc-sub').inner_text())
    check('card sits in the stack under the message (.cc-stack), status gone after the answer', pg.locator('.cc-stack .pim-card').count() == 1 and status() == '', status())
    pg.wait_for_timeout(500)
    pg.reload(); pg.wait_for_timeout(1200)
    if pg.evaluate("document.getElementById('app').dataset.route") != 'chat': pg.evaluate("document.querySelector('#convList li.row .row-main').click()"); pg.wait_for_timeout(800)
    check('card is stream-only: gone after reload, answer text stays', pg.locator('.pim-card').count() == 0 and '확인했어요' in pg.locator('.msg.assistant').last.inner_text())

    ask('pimcal0 비어 있음'); pg.wait_for_timeout(2300)
    check('empty items → 일정이 없어요', pg.locator('.pim-card[data-kind=calendar_events] .bc-none').inner_text() == '일정이 없어요' and pg.locator('.pc-row').count() == 0)

    # ---- read: reminders_list, truncated, done, no due, fold at 10
    ask('pimrem 리마인더'); pg.wait_for_timeout(350)
    check('call status: 리마인더 확인 중…', status() == '리마인더 확인 중…', status())
    pg.wait_for_timeout(1700)
    c = pg.locator('.pim-card[data-kind=reminders]')
    rows = c.locator('.pc-row').evaluate_all("rs => rs.map(r => [r.querySelector('.pc-ti').textContent, r.querySelector('.pc-meta').textContent, r.classList.contains('is-done'), r.hidden])")
    check('reminders card, 12 items, first 10 visible, "2건 더 보기"', len(rows) == 12 and sum(1 for r in rows if not r[3]) == 10 and c.locator('.pc-more').inner_text() == '2건 더 보기', (len(rows), c.locator('.pc-more').count()))
    check('due formatted KST 24h; null due → 기한 없음; list shown', rows[1][1] == f'{D28} 18:00 · 장보기' and rows[0][1] == '기한 없음 · 장보기', rows[:2])
    check('done item marked 완료', rows[2][2] is True and c.locator('.pc-done').count() == 1)
    check('truncated=true → note', '일부만 보여요' in c.locator('.pc-trunc').inner_text())
    c.locator('.pc-more').click(); check('더 보기 reveals the rest', c.locator('.pc-row:not([hidden])').count() == 12 and c.locator('.pc-more').count() == 0)

    # ---- errors
    ask('pimerr 캘린더'); pg.wait_for_timeout(1800)
    e = pg.locator('.pim-card.pim-err')
    check('error card: permission_denied fixed copy', e.count() == 1 and e.inner_text().strip() == '캘린더·리마인더 접근 권한이 없어요. 서버에서 권한을 허용해야 해요' and e.get_attribute('role') == 'status', e.inner_text() if e.count() else None)
    ask('pimerrto 리마인더'); pg.wait_for_timeout(350 + 0)
    check('before the result: 리마인더 확인 중…', status() == '리마인더 확인 중…', status())
    pg.wait_for_timeout(900)
    check('after a failed read: 확인하지 못한 채로 답변 작성 중…', status() == '확인하지 못한 채로 답변 작성 중…', status())
    pg.wait_for_timeout(1200)
    check('timeout fixed copy', pg.locator('.pim-err').inner_text().strip() == '응답이 늦어 확인하지 못했어요')
    ask('pimerrunk 코드'); pg.wait_for_timeout(2000)
    check('unknown code → invalid copy (요청 내용이 올바르지 않아요)', pg.locator('.pim-err').inner_text().strip() == '요청 내용이 올바르지 않아요' and pg.locator('.pim-err').get_attribute('data-code') == 'brand_new_code')
    ask('pimkind 새 종류'); pg.wait_for_timeout(1900)
    check('unknown kind → no card, answer shown', pg.locator('.pim-card').count() == 0 and '확인했어요' in pg.locator('.msg.assistant').last.inner_text())
    ask('pimv2 높은 버전'); pg.wait_for_timeout(1900)
    check('card v=2 → no card, status text only (answer shown)', pg.locator('.pim-card').count() == 0 and '확인했어요' in pg.locator('.msg.assistant').last.inner_text())
    ask('pimwritedeny 추가'); pg.wait_for_timeout(350)
    check('write status: 확인 카드를 준비하는 중…', status() == '확인 카드를 준비하는 중…', status())
    pg.wait_for_timeout(1900)
    check('write denied → error card (Q14 code → invalid copy), no confirm card', pg.locator('.pim-err').count() == 1 and pg.locator('.confirm-card').count() == 0 and pg.locator('.pim-err').inner_text().strip() == '요청 내용이 올바르지 않아요', pg.locator('.pim-err').inner_text() if pg.locator('.pim-err').count() else None)

    # ---- web search copy untouched
    ask('ws 질문'); pg.wait_for_timeout(500)
    check('web tools keep the web copy', '웹에서 찾고 있어요' in status() or status() == '', status())

    # ---- every error code copy
    copy = pg.evaluate("(['pim_unavailable','permission_denied','scope_denied','kill_switch','timeout','invalid_arguments','not_found','writes_disabled','secret_detected','__proto__','constructor'].map(c => [c, EvePim.errText(c)]))")
    check('all 8 fixed copies, unknown keys → invalid', dict((k, v) for k, v in copy if k != '__proto__') == {'pim_unavailable': '캘린더·리마인더에 연결할 수 없어요', 'permission_denied': '캘린더·리마인더 접근 권한이 없어요. 서버에서 권한을 허용해야 해요', 'scope_denied': '이 작업은 할 수 있는 권한이 없어요',
        'kill_switch': '지금은 이 기능을 쓸 수 없어요', 'timeout': '응답이 늦어 확인하지 못했어요', 'invalid_arguments': '요청 내용이 올바르지 않아요', 'not_found': '대상을 찾을 수 없어요', 'writes_disabled': '지금은 쓰기가 꺼져 있어요',
        'secret_detected': '요청 내용이 올바르지 않아요', 'constructor': '요청 내용이 올바르지 않아요'} and [k for k, v in copy].count('__proto__') == 1 and dict(copy)['__proto__'] == '요청 내용이 올바르지 않아요', copy)

    # ---- saved briefing message (§11.3)
    BR = {'schema': 1, 'status': 'partial', 'date': f'{Y}-10-28', 'tz': 'Asia/Seoul', 'generated_at': f'{Y}-10-28T07:30:02+09:00', 'text_source': 'model', 'sections': [
        {'kind': 'events', 'status': 'ok', 'count': 14, 'truncated': True, 'items': [{'title': f'일정 {i} <b>x</b>', 'start': f'{Y}-10-28T{9 + i:02d}:00:00+09:00', 'end': f'{Y}-10-28T{10 + i:02d}:00:00+09:00', 'all_day': False, 'calendar': '회사'} for i in range(10)]},
        {'kind': 'reminders', 'status': 'error', 'error_code': 'timeout', 'count': 0, 'truncated': False, 'items': []},
        {'kind': 'weather', 'status': 'ok', 'count': 1, 'truncated': False, 'items': [{'title': '비'}]}]}
    def seeded(br, text='오늘은 일정 14건이에요.'):
        put('/pro/reset'); sd = put('/pro/seed', {'title': '브리핑', 'proactive': [text], 'job_name': '아침 브리핑', 'template_kind': 'briefing'})
        put('/pro/set', {'msgPatch': {sd['msgs'][0]: {'briefing': br}}})
        pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(1200)
        pg.evaluate("[...document.querySelectorAll('#convList li.row .row-main')].find(r => r.textContent.includes('브리핑'))?.click()"); pg.wait_for_timeout(900)
    seeded(BR)
    bc = pg.locator('.msg.proactive .pim-brief')
    check('saved briefing card under the summary text', bc.count() == 1 and bc.get_attribute('data-status') == 'partial' and '오늘은 일정 14건이에요.' in pg.locator('.msg.proactive .bubble').inner_text())
    secs = bc.locator('.pc-sec')
    check('unknown section kind skipped (only events + reminders)', secs.count() == 2 and secs.evaluate_all("s => s.map(x => x.dataset.kind)") == ['events', 'reminders'])
    check('events: 10 items shown, 외 4건 = count − items.length', secs.nth(0).locator('.pc-row').count() == 10 and secs.nth(0).locator('.pc-trunc').inner_text() == '외 4건' and '14건' in secs.nth(0).locator('.bc-h').inner_text())
    check('failed section shows 확인 불가 (+ fixed reason)', '확인 불가' in secs.nth(1).locator('.bc-h').inner_text() and secs.nth(1).locator('.pc-why').inner_text() == '응답이 늦어 확인하지 못했어요' and secs.nth(1).locator('.pc-row').count() == 0)
    check('item time KST 24h; title is text only', secs.nth(0).locator('.pc-meta').first.inner_text() == f'{D28} 09:00–10:00 · 회사' and bc.locator('b').count() == 0)
    check('header shows the briefing date', D28 in bc.locator('.pc-sub').inner_text(), bc.locator('.pc-sub').inner_text())
    seeded(dict(BR, schema=2))
    check('schema 2 → content only (no card)', pg.locator('.pim-brief').count() == 0 and pg.locator('.msg.proactive .bubble').count() == 1)
    seeded(None)
    check('briefing null → plain proactive message', pg.locator('.pim-brief').count() == 0 and pg.locator('.msg.proactive').count() == 1)
    seeded({'schema': 1, 'status': 'unavailable', 'date': f'{Y}-10-28', 'tz': 'Asia/Seoul', 'generated_at': f'{Y}-10-28T07:30:02+09:00', 'text_source': 'fixed', 'sections': []}, '지금은 확인할 수 없어요.')
    check('unavailable with sections:[] → content only', pg.locator('.pim-brief').count() == 0 and '확인할 수 없어요' in pg.locator('.msg.proactive .bubble').inner_text())
    seeded({'schema': 1, 'status': 'ok', 'date': f'{Y}-10-28', 'tz': 'Asia/Seoul', 'generated_at': '', 'text_source': 'template', 'sections': [
        {'kind': 'events', 'status': 'ok', 'count': 0, 'truncated': False, 'items': []},
        {'kind': 'reminders', 'status': 'ok', 'count': 2, 'truncated': False, 'items': [{'title': '세금 납부', 'due': f'{Y}-10-27T09:00:00+09:00', 'list': '개인', 'overdue': True}, {'title': '약 먹기', 'due': None, 'list': '', 'overdue': False}]}]})
    bc = pg.locator('.pim-brief')
    check('ok briefing: empty events + reminders w/ overdue and no-due', bc.locator('.pc-sec').nth(0).locator('.bc-none').inner_text() == '일정이 없어요' and bc.locator('.pc-late').count() == 1 and bc.locator('.pc-row').nth(1).locator('.pc-meta').inner_text() == '기한 없음' and bc.get_attribute('data-source') == 'template')
    seeded({'schema': 1, 'status': 'weird', 'sections': 'nope'})
    check('malformed briefing is ignored safely', pg.locator('.pim-brief').count() == 0 and pg.locator('.msg.proactive').count() == 1)

    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
