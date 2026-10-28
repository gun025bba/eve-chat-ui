# 1.10.0 briefing card from POST /v1/briefing/preview (eve-serving #77): {status, text, sections:[{name, code?, count}]}
import json, os, urllib.request
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
BASE = {'proactive': {'enabled': False, 'quiet_hours': {'start': '22:00', 'end': '08:00'}, 'memory_read': False}, 'memory': {'enabled': False}}
WITH = dict(BASE, briefing={'enabled': True, 'time': '07:30', 'tz': 'Asia/Seoul', 'skip_if_empty': True, 'delivery': 'in_app', 'retention_days': 7})
TEXT = '오늘 2026-10-27(화) 브리핑\n일정 2건\n- 09:30 팀 스탠드업\n- 종일 출장\n리마인더 2건\n- (기한 지남) 10/25 세금 납부\n- 시간 없음 우유 사기\n- 목록이 길어 일부만 보여요'
OK = {'status': 'ok', 'text': TEXT, 'sections': [{'name': 'events', 'count': 2}, {'name': 'reminders', 'count': 2}]}
errs = []
def hexrgb(c):
    import re
    m = re.findall(r'[\d.]+', c); return [float(x) for x in m[:3]], (float(m[3]) if len(m) > 3 else 1.0)
def lum(rgb):
    f = lambda v: (v / 255 / 12.92) if v / 255 <= .03928 else (((v / 255) + .055) / 1.055) ** 2.4
    return .2126 * f(rgb[0]) + .7152 * f(rgb[1]) + .0722 * f(rgb[2])
def contrast(fg, bg):
    (r, a) = hexrgb(fg); (br, _) = hexrgb(bg); m = [r[i] * a + br[i] * (1 - a) for i in range(3)]
    l1, l2 = lum(m), lum(br); return (max(l1, l2) + .05) / (min(l1, l2) + .05)
with sync_playwright() as p:
    b = p.chromium.launch()
    def newpage(scheme='dark', w=390):
        ctx = b.new_context(viewport={'width': w, 'height': 844}, color_scheme=scheme)
        ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "localStorage.setItem('eve.mem.introSeen','1')}")
        pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); return ctx, pg
    def setup(pg, settings=WITH, **kw):
        put('/auth/on'); put('/persist/on'); put('/db/reset'); put('/fail/clear'); put('/pro/reset'); put('/pro/set', dict(settings=settings, **kw))
        pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(1200)
        pg.click('#openSettings'); pg.wait_for_timeout(700)
    def run(pg, wait=700): pg.click('#briefRun'); pg.wait_for_timeout(wait)
    def prev(): return [x for x in pro()['bodies'] if x['p'] == '/v1/briefing/preview']
    card = lambda pg: pg.locator('#briefOut .brief-card')

    ctx, pg = newpage()
    # ---- gate: the row exists only when GET /v1/settings has `briefing`
    setup(pg, BASE)
    check('settings without briefing → section hidden', pg.is_hidden('#briefSection'))
    ctx.close(); ctx, pg = newpage()
    setup(pg)
    check('settings with briefing → section visible, nothing fetched yet', pg.is_visible('#briefSection') and len(prev()) == 0 and pg.locator('#briefOut .brief-card').count() == 0)
    check('FIELDS.briefing endpoint is same-origin only (POST, interactive)', pg.evaluate("EveProactiveAPI.ENDPOINTS.briefingPreview.method + EveProactiveAPI.ENDPOINTS.briefingPreview.path()") == 'POST/v1/briefing/preview')

    # ---- loading state + double press
    put('/pro/set', {'briefingDelay': 1.2}); pg.click('#briefRun'); pg.click('#briefRun', force=True); pg.wait_for_timeout(300)
    check('loading: card busy, button disabled + aria-busy', card(pg).get_attribute('data-state') == 'loading' and card(pg).get_attribute('aria-busy') == 'true' and pg.is_disabled('#briefRun') and pg.get_attribute('#briefRun', 'aria-busy') == 'true')
    pg.wait_for_timeout(1500)
    check('double press → one request', len(prev()) == 1, len(prev()))
    c = card(pg)
    check('200 ok → ok card', c.get_attribute('data-state') == 'ok' and c.get_attribute('data-status') == 'ok' and pg.is_enabled('#briefRun'))
    check('POST with empty JSON body', prev()[0]['m'] == 'POST' and prev()[0]['b'] == {})
    check('head: 아침 브리핑 + 미리보기 tag', c.locator('.bc-title').inner_text() == '아침 브리핑' and c.locator('.bc-tag').inner_text() == '미리보기')
    check('date line', c.locator('.bc-date').inner_text() == '오늘 2026-10-27(화) 브리핑')
    check('section headings with counts', c.evaluate("e => [...e.querySelectorAll('.bc-h')].map(h => h.textContent)") == ['일정2건', '리마인더1건'], c.evaluate("e => [...e.querySelectorAll('.bc-h')].map(h => h.textContent)"))
    its = c.evaluate("e => [...e.querySelectorAll('.bc-list li')].map(l => [...l.children].map(s => s.textContent).join('|') || l.textContent)")
    check('items: time | title split (HH:MM, 종일, (기한 지남) M/D)', its[:3] == ['09:30|팀 스탠드업', '종일|출장', '(기한 지남) 10/25|세금 납부'], its)
    check('section chips from sections[]', c.evaluate("e => [...e.querySelectorAll('.bc-sec')].map(s => s.textContent)") == ['일정2건', '리마인더1건'])
    check('no retry button on ok', c.locator('.bc-retry').count() == 0)
    check('no horizontal overflow at 390', pg.evaluate("(() => { const e = document.querySelector('.brief-card'); return e.scrollWidth <= e.clientWidth })()"))

    # ---- text safety + odd shapes
    def show(body, st=200, wait=600):
        put('/pro/set', {'briefing': [st, body], 'briefingDelay': 0}); run(pg, wait); return card(pg)
    c = show({'status': 'ok', 'text': '오늘 X 브리핑\n일정 1건\n- 09:00 <img src=x onerror=window.__pwn=1> 회의\n새로운 형식의 줄\n**굵게** <b>x</b>', 'sections': [{'name': 'events', 'count': 1}]})
    check('model text is rendered as text only (no img/b elements, no script)', c.locator('img, b').count() == 0 and pg.evaluate('window.__pwn') is None and '<img src=x' in c.inner_text())
    check('unknown line shapes → plain paragraphs', c.locator('.bc-p').count() == 2, c.locator('.bc-p').count())
    c = show({'status': 'ok', 'text': '오늘 X 브리핑\n일정 12건\n- 09:00 회의\n- 목록이 길어 일부만 보여요', 'sections': [{'name': 'events', 'count': 12}]})
    check('truncation line kept, muted', c.locator('.bc-trunc').count() == 1 and c.locator('.bc-trunc').inner_text() == '목록이 길어 일부만 보여요')
    c = show({'status': 'ok', 'text': '오늘 일정과 리마인더가 없어요.', 'sections': [{'name': 'events', 'count': 0}, {'name': 'reminders', 'count': 0}]})
    check('fixed phrase (nothing today) shown', c.get_attribute('data-state') == 'ok' and '오늘 일정과 리마인더가 없어요.' in c.inner_text() and c.locator('.bc-sec').count() == 2)
    c = show({'status': 'ok', 'text': '일정 연동이 꺼져 있어요.', 'sections': None})
    check('fixed phrase (pim off) + sections null → no chips, no crash', c.get_attribute('data-state') == 'ok' and '일정 연동이 꺼져 있어요.' in c.inner_text() and c.locator('.bc-secs').count() == 0)
    c = show({'status': 'ok', 'text': '오늘 X 브리핑\n일정: 확인하지 못했어요\n리마인더 1건\n- 시간 없음 우유', 'sections': [{'name': 'events', 'code': 'pim_unavailable', 'count': 0}, {'name': 'reminders', 'count': 1}]})
    check('failed section: heading note + chip with reason + marker', c.locator('.bc-note').inner_text() == '확인하지 못했어요' and c.locator('.bc-sec.bc-bad').count() == 1 and '연결하지 못했어요' in c.locator('.bc-bad').inner_text() and c.locator('.bc-bad').get_attribute('data-code') == 'pim_unavailable')
    for code, frag in [('permission_denied', '접근이 허용되지 않았어요'), ('kill_switch', '꺼져 있어요'), ('timeout', '응답이 늦어요'), ('brand_new_code', '확인하지 못했어요')]:
        c = show({'status': 'ok', 'text': '오늘 X 브리핑\n일정: 확인하지 못했어요', 'sections': [{'name': 'events', 'code': code, 'count': 0}]})
        check('section code ' + code, frag in c.locator('.bc-bad').inner_text(), c.locator('.bc-bad').inner_text())
    # unknown section names / bad counts
    c = show({'status': 'ok', 'text': '오늘 X 브리핑', 'sections': [{'name': 'weather', 'count': 3}, {'name': '', 'count': 1}, {'name': 'events'}, {'name': '__proto__', 'count': -1}, {'name': 'constructor', 'count': 'x'}, None, 7, {'name': 'reminders', 'count': 1.9}]})
    chips = c.evaluate("e => [...e.querySelectorAll('.bc-sec')].map(s => s.textContent)")
    check('unknown/odd sections degrade: raw name, 항목 for empty, no count when invalid, floor(1.9), junk entries dropped', chips == ['weather3건', '항목1건', '일정', '__proto__', 'constructor', '리마인더1건'], chips)
    check('(sections of the wrong type) → no chips', show({'status': 'ok', 'text': '오늘 X', 'sections': 'nope'}).locator('.bc-secs').count() == 0)
    # unknown status
    c = show({'status': 'brand_new_status', 'text': '오늘 X 브리핑\n일정 1건\n- 09:00 회의', 'sections': []})
    check('unknown status with text → text shown', c.get_attribute('data-state') == 'ok' and c.get_attribute('data-status') == 'brand_new_status' and '회의' in c.inner_text())
    c = show({'status': 'brand_new_status', 'sections': []})
    check('unknown status without text → generic error + 다시 시도, raw status not shown', c.get_attribute('data-state') == 'error' and 'brand_new_status' not in c.inner_text() and c.locator('.bc-retry').count() == 1)
    c = show({'status': 'ok', 'text': '', 'sections': []})
    check('ok with empty text → empty state', c.get_attribute('data-state') == 'empty')
    c = show({'status': 5, 'text': 7, 'sections': 3})
    check('wrong types everywhere → error state, no crash', c.get_attribute('data-state') == 'error')
    c = show('plain string')
    check('non-object 200 → error state', c.get_attribute('data-state') == 'error')
    c = show({'status': 'skipped_off', 'sections': []})
    check('skipped_off → 브리핑이 꺼져 있어요, no retry', c.get_attribute('data-state') == 'empty' and '브리핑이 꺼져 있어요' in c.inner_text() and c.locator('.bc-retry').count() == 0)
    c = show({'status': 'skipped_empty', 'sections': []})
    check('skipped_empty → 오늘은 보여 드릴 내용이 없어요', '오늘은 보여 드릴 내용이 없어요' in c.inner_text())

    # ---- 502: {status, sections}, no text
    c = show({'status': 'error', 'sections': [{'name': 'events', 'code': 'timeout', 'count': 0}, {'name': 'reminders', 'count': 0}]}, 502)
    check('502 → error card: message + section reasons + 다시 시도', c.get_attribute('data-state') == 'error' and '브리핑을 만들지 못했어요' in c.inner_text() and c.locator('.bc-bad').count() == 1 and c.locator('.bc-retry').count() == 1 and c.locator('.bc-text').count() == 0, c.inner_text())
    check('502 message is an alert for screen readers', c.locator('.bc-msg').get_attribute('role') == 'alert')
    put('/pro/set', {'briefing': [200, OK]}); n = len(prev()); c.locator('.bc-retry').click(); pg.wait_for_timeout(700)
    check('다시 시도 → new request → ok card', len(prev()) == n + 1 and card(pg).get_attribute('data-state') == 'ok')
    c = show({'status': 'error'}, 502)
    check('502 without sections → still the error card', c.get_attribute('data-state') == 'error' and c.locator('.bc-secs').count() == 0)
    c = show({'detail': 'Bad Gateway'}, 502)
    check('502 with an unrelated body → generic error + retry', c.get_attribute('data-state') == 'error' and c.locator('.bc-retry').count() == 1)
    c = show({'status': 'skipped_off', 'sections': []}, 502)
    check('502 with a known non-error status → that status copy', '브리핑이 꺼져 있어요' in c.inner_text())
    c = show({'error_code': 'invalid'}, 500)
    check('500 → generic error + retry', c.get_attribute('data-state') == 'error' and c.locator('.bc-retry').count() == 1)
    c = show({'error_code': 'scope_denied'}, 403)
    check('403 scope_denied → 권한 copy, no retry', '권한이 없어요' in c.inner_text() and c.locator('.bc-retry').count() == 0)
    put('/pro/set', {'briefingDrop': True}); run(pg, 800)
    c = card(pg)
    check('network drop → 연결이 끊겼어요 + retry', c.get_attribute('data-state') == 'error' and '연결이 끊겼어요' in c.inner_text() and c.locator('.bc-retry').count() == 1, c.inner_text())
    put('/pro/set', {'briefingDrop': False})
    c = show({'error_code': 'not_found'}, 404)
    check('404 (briefing switched off) → off copy, section hides, no retry', '지금은 이 기능을 쓸 수 없어요' in c.inner_text() and c.locator('.bc-retry').count() == 0 and pg.is_hidden('#briefSection'))

    # ---- reopening settings clears a stale result
    setup(pg); put('/pro/set', {'briefing': [200, OK]}); run(pg)
    check('result shown', card(pg).count() == 1)
    pg.keyboard.press('Escape'); pg.reload(); pg.wait_for_timeout(1000); pg.click('#openSettings'); pg.wait_for_timeout(700)
    check('after reopening settings the old card is gone', card(pg).count() == 0)

    # ---- FIELDS.briefing mapping
    out = pg.evaluate("""[null, {}, {status: 5}, {status: 'ok', text: 'x', sections: [{name: 'events', code: 'timeout', count: 2}]}, {sections: [null, 3, {count: NaN}]}].map(v => EveProactiveAPI.FIELDS.briefing(v))""")
    check('FIELDS.briefing: null/{}/wrong types normalise', out[0] == {'status': '', 'text': '', 'sections': []} and out[1] == out[0] and out[2]['status'] == '' and out[4]['sections'] == [{'name': '', 'code': None, 'count': None}], out)
    check('FIELDS.briefing: full shape', out[3] == {'status': 'ok', 'text': 'x', 'sections': [{'name': 'events', 'code': 'timeout', 'count': 2}]}, out[3])
    ctx.close()

    # ---- narrow viewport, long unbroken title
    ctx, pg = newpage('dark', 320); setup(pg)
    c = show({'status': 'ok', 'text': '오늘 X 브리핑\n일정 1건\n- 09:00 ' + 'ㅁ' * 80 + '\n- 10:00 ' + 'a' * 120, 'sections': [{'name': 'a' * 90, 'count': 1}]})
    check('320px: long titles wrap, no overflow', pg.evaluate("(() => { const e = document.querySelector('.brief-card'); return e.scrollWidth <= e.clientWidth && document.documentElement.scrollWidth <= innerWidth })()"))
    ctx.close()

    # ---- contrast (WCAG AA 4.5:1) + motion, dark and light
    for scheme, card_bg, chip_bg, tag_bg in [('light', 'rgb(255,255,255)', 'rgb(242,242,247)', 'rgb(229,229,234)'), ('dark', 'rgb(44,44,46)', 'rgb(28,28,30)', 'rgb(44,44,46)')]:
        ctx, pg = newpage(scheme); setup(pg); put('/pro/set', {'briefing': [200, OK]}); run(pg)
        col = lambda sel: pg.evaluate("s => getComputedStyle(document.querySelector(s)).color", sel)
        pairs = [('.bc-title', card_bg), ('.bc-ti', card_bg), ('.bc-t', card_bg), ('.bc-n', card_bg), ('.bc-date', card_bg), ('.bc-trunc', card_bg), ('.bc-sn', chip_bg), ('.bc-sv', chip_bg), ('.bc-tag', tag_bg)]
        low = [(s, round(contrast(col(s), bg), 2)) for s, bg in pairs if contrast(col(s), bg) < 4.5]
        check(f'{scheme}: all brief text ≥ 4.5:1', not low, low)
        check(f'{scheme}: no transitions/animations on the card', pg.evaluate("[...document.querySelectorAll('.brief-card, .brief-card *')].every(e => { const s = getComputedStyle(e); return (s.transitionDuration === '0s' || s.transitionProperty === 'none') && s.animationName === 'none' })"))
        pg.screenshot(path=f'/tmp/bc_{scheme}.png'); ctx.close()
    b.close()
check('no page errors', not errs, errs)
print(f'{sum(R)}/{len(R)}'); raise SystemExit(0 if all(R) else 1)
