# 1.10.0 B2 하루 (DIRECTION-B-SPEC §1 §9 §10): hash routes #/ #/log #/archive #/t/<id>, back-to-origin, back labels, deep links, ≥761px sidebar
from playwright.sync_api import sync_playwright
from b2_common import *
R = []; errs = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
hs = lambda pg: pg.evaluate('location.hash')
def newpg(b, w=390, h=844, **kw):
    ctx = new_ctx(b, w=w, h=h, **kw); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); return ctx, pg
with sync_playwright() as p:
    b = p.chromium.launch()
    reset(); ids = rich(); ids.update(older()); tid = ids['SwiftUI 질문']
    ctx, pg = newpg(b); pg.goto(B + '/ui/'); pg.wait_for_timeout(1200)
    check('/ui/ → Today, hash normalised to #/', rt(pg) == 'today' and hs(pg) in ('#/', ''))
    check('only the Today screen is interactive (others inert)', pg.evaluate("[todayView.inert,listView.inert,chatView.inert,archiveView.inert]") == [False, True, True, True])
    # Today → log → chat → back → back
    pg.click('#openLog'); pg.wait_for_timeout(600); check('Today → 기록: #/log', rt(pg) == 'list' and hs(pg) == '#/log' and pg.evaluate("[todayView.inert,listView.inert]") == [True, False])
    pg.locator('#convList li.row', has_text='SwiftUI 질문').first.click(); pg.wait_for_timeout(800)
    check('기록 → thread: #/t/<id>, back label 기록, data-from=list', rt(pg) == 'chat' and hs(pg) == '#/t/' + tid and pg.text_content('#backLbl') == '기록' and pg.evaluate("app.dataset.from") == 'list', [hs(pg), pg.text_content('#backLbl')])
    pg.click('#backBtn'); pg.wait_for_timeout(700); check('back → 기록', rt(pg) == 'list' and hs(pg) == '#/log')
    pg.click('#logBack'); pg.wait_for_timeout(700); check('기록 back → Today', rt(pg) == 'today' and hs(pg) in ('#/', ''))
    # Today → chat directly: back goes to Today, label 오늘
    pg.locator('#todayList .ev.conv .ev-hit').first.click(); pg.wait_for_timeout(800)
    check('Today → thread: back label 오늘, data-from=today', rt(pg) == 'chat' and pg.text_content('#backLbl') == '오늘' and pg.evaluate("app.dataset.from") == 'today')
    pg.go_back(); pg.wait_for_timeout(700); check('browser back from that thread → Today (not 기록)', rt(pg) == 'today')
    pg.go_forward(); pg.wait_for_timeout(700); check('browser forward → the thread', rt(pg) == 'chat' and hs(pg).startswith('#/t/'))
    pg.click('#backBtn'); pg.wait_for_timeout(700)
    # archive path
    pg.click('#openLog'); pg.wait_for_timeout(600); pg.click('#archivedRow'); pg.wait_for_timeout(800)
    check('기록 → 보관함: #/archive', rt(pg) == 'archive' and hs(pg) == '#/archive')
    pg.locator('#archList li.row').first.click(); pg.wait_for_timeout(900)
    check('보관함 → thread: back label 보관함', rt(pg) == 'chat' and pg.text_content('#backLbl') == '보관함' and pg.evaluate("app.dataset.from") == 'archive', pg.text_content('#backLbl'))
    pg.click('#backBtn'); pg.wait_for_timeout(700); check('back → 보관함', rt(pg) == 'archive')
    pg.click('#archBack'); pg.wait_for_timeout(700); check('보관함 back → 기록', rt(pg) == 'list'); ctx.close()
    # deep links at boot
    for h, want, name in [('#/log', 'list', '#/log'), ('#/archive', 'archive', '#/archive'), ('#/t/' + tid, 'chat', '#/t/<id>'), ('#/c/' + tid, 'chat', 'legacy #/c/<id>')]:
        ctx, pg = newpg(b); goto_today(pg, h, wait=1800)
        check(f'deep link {name} opens {want}', rt(pg) == want, [rt(pg), hs(pg)])
        if want != 'chat': pg.go_back(); pg.wait_for_timeout(600); check(f'{name}: back → ' + ('Today' if want == 'list' else '기록'), rt(pg) == ('today' if want == 'list' else 'list'), rt(pg))
        else:
            check(f'{name}: title is the thread', 'SwiftUI' in pg.text_content('#title')); pg.click('#backBtn'); pg.wait_for_timeout(700); check(f'{name}: back → Today (nothing to go back to)', rt(pg) == 'today', rt(pg))
        ctx.close()
    ctx, pg = newpg(b); goto_today(pg, '#/t/01JNOSUCHTHREAD0000000000X', wait=2200)
    check('unknown #/t/<id>: stays usable on Today with a toast, no blank screen', rt(pg) == 'today' and pg.is_visible('#tComposer'), [rt(pg), hs(pg)]); ctx.close()
    # a cold launch never restores the last route
    ctx, pg = newpg(b); goto_today(pg, '#/t/' + tid); pg.goto(B + '/ui/'); pg.wait_for_timeout(1200)
    check('cold start URL /ui/ after using a thread → Today (no boot route restore)', rt(pg) == 'today'); ctx.close()
    # ≥761px: sidebar = log, right pane = Today or chat
    ctx, pg = newpg(b, w=1100, h=800); goto_today(pg, '#/')
    bb = pg.locator('#listView').bounding_box(); tv = pg.locator('#todayView').bounding_box()
    check('wide: log sidebar 320px at the left, Today fills the right', pg.is_visible('#listView') and pg.is_visible('#todayView') and abs(bb['width'] - 320) < 1 and tv['x'] >= bb['x'] + bb['width'] - 1, [bb, tv])
    check('wide: #openLog / #logBack / Today settings button hidden; settings reachable from the sidebar nav', not pg.is_visible('#openLog') and not pg.is_visible('#logBack') and not pg.is_visible('#openSettings') and pg.is_visible('#openSettings3'))
    pg.locator('#convList li.row', has_text='SwiftUI 질문').first.click(); pg.wait_for_timeout(900)
    check('wide: row opens the chat on the right; sidebar stays; row is .active', pg.is_visible('#listView') and pg.is_visible('#chatView') and pg.is_visible('#composer') and not pg.is_visible('#todayView') and pg.locator('#convList li.row.active').count() == 1)
    check('wide: chat back button visible, label 오늘, returns to Today', pg.is_visible('#backBtn') and pg.text_content('#backLbl') == '오늘')
    pg.click('#backBtn'); pg.wait_for_timeout(700); check('wide: back → Today on the right, sidebar intact', rt(pg) == 'today' and pg.is_visible('#listView') and pg.is_visible('#tComposer'))
    pg.click('#openSettings3'); pg.wait_for_timeout(700); check('wide: sidebar settings opens the sheet', pg.evaluate("document.querySelector('#settings').open")); pg.click('#cancelSettings'); pg.wait_for_timeout(400)
    pg.click('#archivedRow'); pg.wait_for_timeout(800); check('wide: 보관함 replaces the sidebar content (route archive)', rt(pg) == 'archive' and pg.is_visible('#archiveView')); ctx.close()
    # 760 stays a single stack
    ctx, pg = newpg(b, w=760, h=800); goto_today(pg, '#/')
    check('760px: still the phone stack (log not beside Today)', not pg.is_visible('#listView') and pg.is_visible('#todayView')); ctx.close()
    check('no page errors', not errs, errs); b.close()
print(f'{sum(R)}/{len(R)} checks'); raise SystemExit(0 if all(R) else 1)
