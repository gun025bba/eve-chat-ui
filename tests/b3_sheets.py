# 1.10.0 B3 시트 (DIRECTION-B-SPEC §5–§7): 확인 대기 sheet (≥2) / direct jump (1), 오늘 일정 sheet, 기억 cell → #memoryView
import re
from playwright.sync_api import sync_playwright
from b3_common import *
R = []; errs = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
pro = lambda: put('/__pro')
sheet = lambda pg: pg.locator('#stripSheet:not([hidden])')
def two_pending():
    rich(); memory(3)
    seed_act(act(1, title='치과 예약 · 내일 10시', exp=60 * 24 * 3, created=isoz(-90)), title='치과 예약')
    seed_act(act(2, title='장보기 알림 <img src=x onerror=window.__x=1>', verb='remind', exp=5, created=isoz(-30)), title='장보기')
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---- 1) one pending → straight to its thread (no sheet)
    reset(); rich(); memory(3); seed_act(act(1, title='치과 예약 · 내일 10시', exp=60 * 24 * 3))
    ctx, pg = newpg(b, errs); goto_today(pg); pg.locator('.stc[data-k=pend]').click(); pg.wait_for_timeout(1500)
    check('1 pending: tap goes to that thread, no sheet', rt(pg) == 'chat' and pg.evaluate('location.hash').startswith('#/t/') and sheet(pg).count() == 0, (rt(pg), pg.evaluate('location.hash')))
    check('… the confirmation card is on screen (read-only strip, approval stays in the thread)', pg.locator('.confirm-card').count() >= 1 and pg.locator('.confirm-card').first.is_visible())
    ctx.close()

    # ---- 2) ≥2 pending → medium sheet "확인 대기 N건"
    reset(); two_pending(); ctx, pg = newpg(b, errs, dsf=1); goto_today(pg)
    n0 = len(pro()['bodies']); pg.locator('.stc[data-k=pend]').click(); pg.wait_for_timeout(700)
    sh = sheet(pg)
    check('2 pending: the sheet opens (role=dialog, titled "확인 대기 2건")', sh.count() == 1 and sh.get_attribute('role') == 'dialog' and pg.text_content('#ssTitle') == '확인 대기 2건', pg.text_content('#ssTitle'))
    rows = pg.locator('#ssList .ss-row')
    check('two rows, oldest first, ≥56 tall, each a button with a chevron-right', rows.count() == 2 and all(rows.nth(i).evaluate("e => e.tagName === 'BUTTON' && e.getBoundingClientRect().height >= 56 && !!e.querySelector('svg use[href=\"#i-chevron-right\"]')") for i in range(2)), rows.count())
    tx = [rows.nth(i).inner_text().replace('\n', ' | ') for i in range(2)]
    check('row = title + "verb 라벨 · 곧 만료" (곧 만료 only for the one expiring in 5 min)', tx[0].startswith('치과 예약 · 내일 10시 |') and '곧 만료' not in tx[0] and '곧 만료' in tx[1] and '알림' in tx[1], tx)
    check('titles go in as text (no markup injected)', pg.locator('#stripSheet img').count() == 0 and pg.evaluate('window.__x') is None and '<img' in tx[1])
    check('read-only: no approve/reject buttons, no token anywhere in the sheet', pg.locator('#stripSheet button').count() == 2 and not re.search(r'token|승인|거절', pg.inner_html('#stripSheet'), re.I))
    check('no new request was made by opening the sheet', len([x for x in pro()['bodies'][n0:] if x['m'] != 'GET']) == 0)
    sw = pg.evaluate("(() => { const s = document.getElementById('stripSheet'), r = s.getBoundingClientRect(); return [r.left, innerWidth - r.right, r.bottom - innerHeight, getComputedStyle(s).backdropFilter, s.scrollWidth <= s.clientWidth] })()")
    check('sheet is a bottom sheet at full width, no blur, no horizontal overflow', abs(sw[0]) < 1 and abs(sw[1]) < 1 and sw[3] in ('none', '') and sw[4], sw)
    check('focus moves into the sheet (title)', pg.evaluate("document.activeElement.id") == 'ssTitle')
    pg.keyboard.press('Escape'); pg.wait_for_timeout(600)
    check('Esc closes it and focus returns to the 확인 대기 cell', sheet(pg).count() == 0 and pg.evaluate("document.activeElement && document.activeElement.dataset.k") == 'pend', pg.evaluate("document.activeElement && document.activeElement.outerHTML.slice(0,80)"))
    pg.locator('.stc[data-k=pend]').click(); pg.wait_for_timeout(700); pg.mouse.click(195, 60); pg.wait_for_timeout(600)
    check('tapping the scrim closes it', sheet(pg).count() == 0 and rt(pg) == 'today')
    pg.locator('.stc[data-k=pend]').click(); pg.wait_for_timeout(700)
    pg.locator('#ssList .ss-row').nth(1).click(); pg.wait_for_timeout(1500)
    tid = [a for a in pro()['actions'].values() if a['action_id'].endswith('2')][0]['thread_id']
    check('row tap closes the sheet and opens that thread at its card', sheet(pg).count() == 0 and rt(pg) == 'chat' and pg.evaluate('location.hash') == '#/t/' + tid and pg.locator('.confirm-card').first.is_visible(), (rt(pg), pg.evaluate('location.hash'), tid))
    ctx.close()

    # ---- 3) 오늘 일정 sheet
    def sched():
        rich(); memory(3); seed_act()
        brief_thread([ev('팀 스탠드업', 0, 5, 20, '회사'), ev('종일 행사 <b>x</b>', 0, 0, 60, '회사', all_day=True), ev('아주 긴 제목의 일정입니다 ' * 6, 23, 0, 30, '가족'), ev('늦은 통화', 23, 40, 15, '')], h=7, m=42)
    reset(); sched(); ctx, pg = newpg(b, errs); goto_today(pg); pg.locator('.stc[data-k=sch]').click(); pg.wait_for_timeout(700)
    check('schedule sheet: title "오늘 일정", subtitle "오늘 아침 기준 · 07:42" (message time, KST)', pg.text_content('#ssTitle') == '오늘 일정' and pg.text_content('#ssSub') == '오늘 아침 기준 · 07:42', (pg.text_content('#ssTitle'), pg.text_content('#ssSub')))
    ev_ = pg.locator('#ssList .ss-ev'); tms = [ev_.nth(i).locator('.ss-tm').inner_text() for i in range(ev_.count())]
    check('rows in source order with HH:mm–HH:mm / 종일', ev_.count() == 4 and tms == ['00:05–00:25', '종일', '23:00–23:30', '23:40–23:55'], tms)
    check('past events are lowered to --sub (the over one, not the upcoming)', pg.evaluate("[...document.querySelectorAll('#ssList .ss-ev')].map(e => e.classList.contains('past'))") == [True, False, False, False])
    check('all-day is never "past"; title clamps to 2 lines', pg.evaluate("(() => { const t = document.querySelectorAll('#ssList .ss-ev')[2].querySelector('.ss-t'); return getComputedStyle(t).webkitLineClamp === '2' && t.getBoundingClientRect().height <= 44 })()"))
    check('calendar name shown 13/18 --sub; absent calendar → no empty line', ev_.nth(0).locator('.ss-m').inner_text() == '회사' and ev_.nth(3).locator('.ss-m').count() == 0)
    check('external titles are text only (the <b> stays literal)', pg.locator('#ssList b').count() == 0 and '<b>x</b>' in pg.inner_text('#ssList'))
    check('read-only: no buttons/links in rows, no footer when not truncated', pg.locator('#ssList button, #ssList a').count() == 0 and pg.is_hidden('#ssFoot'))
    pg.keyboard.press('Escape'); pg.wait_for_timeout(500); ctx.close()
    reset(); rich(); memory(3); seed_act(); brief_thread([ev('a', 23, 0), ev('b', 23, 20)], count=12, truncated=True)
    ctx, pg = newpg(b, errs); goto_today(pg); pg.locator('.stc[data-k=sch]').click(); pg.wait_for_timeout(700)
    check('truncated: footer "더 있을 수 있어요" shown', pg.is_visible('#ssFoot') and pg.text_content('#ssFoot').strip() == '더 있을 수 있어요')
    ctx.close()

    # ---- 4) 기억 cell → settings sheet at #memoryView, and the strip follows what changed there
    reset(); rich(); memory(5); seed_act(act(1, title='A')); ctx, pg = newpg(b, errs); goto_today(pg)
    pg.locator('.stc[data-k=mem]').click(); pg.wait_for_timeout(1500)
    check('기억 tap: settings sheet is open with #memoryView expanded and the 5 items listed', pg.evaluate("document.getElementById('settings').open") and pg.is_visible('#memoryView') and pg.locator('#memList li.mem-row').count() == 5, pg.locator('#memList li.mem-row').count())
    check('… memOpen is expanded (back = collapse the list in settings)', pg.get_attribute('#memOpen', 'aria-expanded') == 'true')
    put('/pro/set', {'memItems': mem_items(2)})
    pg.click('#saveSettings'); pg.wait_for_timeout(1500)
    check('closing settings returns to Today and the strip count follows (5 → 2)', rt(pg) == 'today' and strip(pg)['cells'][0]['n'] == '2', strip(pg))
    ctx.close()
    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
