# 1.10.0 B2 하루 (DIRECTION-B-SPEC §4-4 §6): Today "확인 대기" card — oldest pending, 곧 만료 (≤10 min), 검토하기 / 나중에, fade-out, endpoint failure hides it
import re, time
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright
from b2_common import *
R = []; errs = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
def isoz(mins=0, secs=0): return (datetime.now(timezone.utc) + timedelta(minutes=mins, seconds=secs)).strftime('%Y-%m-%dT%H:%M:%SZ')
def act(n, title=None, verb='add', exp=60 * 24, created=None, tool='calendar_add_event', display=None, scopes=None, **kw):
    pv = {'verb': verb}
    if title: pv['title'] = title
    if display: pv['display'] = display
    return dict(ACT, action_id='01JPEND%019d' % n, tool=tool, summary=kw.pop('summary', '일정 추가'), scopes=scopes or ['calendar.write'], payload_view=pv, expires_at=isoz(exp),
                created_at=created or isoz(-60 + n), **kw)
def newpg(b, scheme='dark', **kw):
    ctx = new_ctx(b, scheme=scheme, **kw); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); return ctx, pg
def seed(*acts, **kw):
    return put('/pro/seed', dict(title='치과 예약', user=['내일 치과 일정 추가해 줘'], proactive=['치과 예약 일정을 추가할까요?'], job_name='아침 브리핑', restore=list(acts), **kw))
pro = lambda: put('/__pro')
def card(pg): return pg.locator('#todayList .ev.wt')
def cur(pg): return pg.evaluate("location.hash")
def refresh(pg):   # what coming back to the app does
    pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(500)

with sync_playwright() as p:
    b = p.chromium.launch()
    # ---- 1) one pending: anatomy
    reset(); rich(); seed(act(1, title='치과 예약 · 내일 10시', exp=60 * 24 * 3))
    ctx, pg = newpg(b); goto_today(pg)
    check('one .ev.wt card in the Today rail', card(pg).count() == 1 and card(pg).locator('.pend').count() == 1, (card(pg).count(), pg.evaluate("document.querySelector('#todayList').innerText")))
    check('time column "대기", who "확인해 주세요" in --pend', card(pg).locator('.tm').text_content() == '대기' and '확인해 주세요' in card(pg).locator('.who').text_content()
          and pg.evaluate("(()=>{const w=document.querySelector('#todayList .ev.wt .who'),d=document.createElement('i');d.style.color='var(--pend)';document.body.appendChild(d);const ok=getComputedStyle(w).color===getComputedStyle(d).color;d.remove();return ok})()"))
    check('dot is a hollow --pend ring', pg.evaluate("getComputedStyle(document.querySelector('#todayList .ev.wt .dot')).boxShadow").count('rgb') >= 2)
    check('title = payload_view.title; verb chip = payload_view.verb → "추가"', card(pg).locator('.pd-t').text_content() == '치과 예약 · 내일 10시' and card(pg).locator('.pd-v').text_content() == '추가')
    check('no display line for a non-reminder action; no 곧 만료', card(pg).locator('.pd-w').count() == 0 and card(pg).locator('.pd-x').count() == 0)
    check('exactly [검토하기] [나중에] — no approve button, no token ever fetched', card(pg).locator('button').all_text_contents() == ['검토하기', '나중에'] and not any('approve' in x['p'] or 'reissue' in x['p'] for x in pro().get('bodies', [])))
    check('card order: after 이어서/선톡, before nothing else of its kind; rail intact (one .dot per item)', pg.evaluate("[...document.querySelectorAll('#todayList > li')].every(l=>l.querySelector('.dot'))"))
    check('buttons 44px+ tap area and 32px visible', pg.evaluate("[...document.querySelectorAll('#todayList .pend button')].every(b=>{const r=b.getBoundingClientRect(),a=getComputedStyle(b,'::before');return Math.round(r.height)===32&&r.height+Math.abs(parseFloat(a.top))*2>=44})"))
    check('no horizontal overflow at 390', pg.evaluate("document.documentElement.scrollWidth<=innerWidth"))
    ctx.close()

    # ---- 2) title fallbacks, display for a reminder, very long text
    reset(); rich()
    seed(act(2, title=None, summary='할 일 추가', tool='proactive.propose_followup', verb='add', display='10월 29일 (목) 오전 9:00', scopes=['reminders.write']))
    ctx, pg = newpg(b); goto_today(pg)
    check('no payload_view.title → summary', card(pg).locator('.pd-t').text_content() == '할 일 추가')
    check('proactive follow-up → second line = payload_view.display', card(pg).locator('.pd-w').text_content() == '10월 29일 (목) 오전 9:00')
    ctx.close()
    reset(); rich(); seed(act(3, title=None, summary=''))
    ctx, pg = newpg(b); goto_today(pg)
    check('no title, no summary → "확인이 필요한 일"', card(pg).locator('.pd-t').text_content() == '확인이 필요한 일')
    ctx.close()
    reset(); rich(); L = '아주아주 긴 제목의 일정 추가 요청입니다 ' * 6
    seed(act(4, title=L, display=L, verb='send', scopes=['mail.send']))
    ctx, pg = newpg(b, w=320); goto_today(pg)
    check('long title/display: one line each with ellipsis, no overflow at 320; verb "보내기"', pg.evaluate("document.documentElement.scrollWidth<=innerWidth") and card(pg).locator('.pd-v').text_content() == '보내기'
          and pg.evaluate("(()=>{const t=document.querySelector('.pd-t');return t.scrollWidth>t.clientWidth&&t.getBoundingClientRect().height<=21})()"))
    ctx.close()

    # ---- 3) oldest first + 곧 만료 threshold
    reset(); rich(); seed(act(11, title='가장 나중', created=isoz(-5)), act(10, title='가장 오래됨', created=isoz(-50)), act(12, title='중간', created=isoz(-20)))
    ctx, pg = newpg(b); goto_today(pg)
    check('only ONE card, the oldest by created_at', card(pg).count() == 1 and card(pg).locator('.pd-t').text_content() == '가장 오래됨')
    ctx.close()
    for mins, want, nm in ((5, True, '5 min left'), (9.5, True, '9.5 min left'), (10.5, False, '10.5 min left'), (60 * 3, False, '3 h left')):
        reset(); rich(); seed(act(20, title='만료 확인', exp=mins))
        ctx, pg = newpg(b); goto_today(pg)
        check(f'곧 만료 {"shown" if want else "hidden"} with {nm}', (card(pg).locator('.pd-x').count() == 1) == want)
        if want: check('곧 만료 is 13px in --pend and read out in the row label', pg.evaluate("(()=>{const x=document.querySelector('.pd-x'),d=document.createElement('i');d.style.color='var(--pend)';document.body.appendChild(d);const ok=getComputedStyle(x).fontSize==='13px'&&getComputedStyle(x).color===getComputedStyle(d).color;d.remove();return ok})()") and '곧 만료' in card(pg).get_attribute('aria-label') if False else pg.evaluate("document.querySelector('#todayList .ev.wt').getAttribute('aria-label').includes('곧 만료')") and pg.evaluate("getComputedStyle(document.querySelector('.pd-x')).fontSize")=='13px')
        ctx.close()
    # label turns on while the screen is open (the 10-min line is crossed)
    reset(); rich(); seed(act(21, title='곧 넘는다', exp=10.05))
    ctx, pg = newpg(b); goto_today(pg)
    check('11-min-ish label starts hidden', card(pg).locator('.pd-x').count() == 0)
    pg.wait_for_timeout(4000); pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(1200)
    check('…and 곧 만료 appears without a reload once ≤ 10 min', card(pg).locator('.pd-x').count() == 1, pg.evaluate("document.querySelector('#todayList').innerText"))
    ctx.close()

    # ---- 4) 나중에: hidden for today in this session, next one appears
    reset(); rich(); seed(act(31, title='첫째', created=isoz(-50)), act(32, title='둘째', created=isoz(-40)))
    ctx, pg = newpg(b); goto_today(pg)
    pg.locator('#todayList .pend .pd-later').click(); pg.wait_for_timeout(700)
    check('[나중에] → next oldest takes its place (first one gone)', card(pg).count() == 1 and card(pg).locator('.pd-t').text_content() == '둘째')
    check('no network write for 나중에 (nothing on the server changes)', not [x for x in pro().get('bodies', []) if x['m'] != 'GET'])
    pg.locator('#todayList .pend .pd-later').click(); pg.wait_for_timeout(700)
    check('both put off → no card, no empty slot', card(pg).count() == 0)
    pg.reload(); pg.wait_for_timeout(1500)
    check('stays hidden after a reload in the same session', card(pg).count() == 0)
    pg.evaluate("sessionStorage.setItem('eve.b2.snooze', JSON.stringify({day:'2000-01-01', ids:['01JPEND0000000000000000031','01JPEND0000000000000000032']}))"); pg.reload(); pg.wait_for_timeout(1500)
    check('a "나중에" from another day no longer hides it', card(pg).count() == 1)
    ctx.close()
    ctx, pg = newpg(b); goto_today(pg)
    check('a new session (new browser context) shows it again', card(pg).count() == 1 and card(pg).locator('.pd-t').text_content() == '첫째')
    # ---- 5) 검토하기: opens the thread at the message
    reset(); rich(); seed(act(41, title='치과', _mi=0)); ctx.close()
    ctx, pg = newpg(b); goto_today(pg)
    pg.locator('#todayList .pend .pd-go').click(); pg.wait_for_timeout(1500)
    check('[검토하기] → thread route #/t/<id>', rt(pg) == 'chat' and cur(pg).startswith('#/t/'), (rt(pg), cur(pg)))
    check('the action\'s confirm card is shown in the thread (approval stays there)', pg.locator('#messages .confirm-card').count() >= 1)
    gap = pg.evaluate("(()=>{const m=document.querySelector('#messages .msg[data-mid]'),n=document.querySelector('#chatView .navbar,.navbar');return [m.dataset.mid, Math.round(m.getBoundingClientRect().top-n.getBoundingClientRect().bottom)]})()")
    check('message_id given → that message sits at the top of the thread, just under the nav (0–40px)', 0 <= gap[1] <= 40, gap)
    pg.go_back(); pg.wait_for_timeout(900)
    check('back → Today with the card still there', rt(pg) == 'today' and card(pg).count() == 1)
    ctx.close()
    # ---- 6) handled elsewhere → fades out (180ms), no leftover slot
    reset(); rich(); seed(act(51, title='곧 사라짐'))
    ctx, pg = newpg(b); goto_today(pg)
    put('/pro/set', dict(statusOf={'01JPEND0000000000000000051': 'approved'}))
    pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(300)
    st = pg.evaluate("(()=>{const e=document.querySelector('#todayList .ev.wt');return e?[e.classList.contains('leaving'),getComputedStyle(e).transitionProperty,getComputedStyle(e).transitionDuration]:null})()")
    check('on a poll that no longer lists it: .leaving, opacity-only 180ms transition', st is None or (st[0] and st[1] == 'opacity' and st[2] == '0.18s'), st)
    pg.wait_for_timeout(600)
    check('then removed from the rail', card(pg).count() == 0)
    # new pending shows up on return to the app
    put('/pro/set', dict(statusOf={})); seed(act(52, title='새로 생김'))
    refresh(pg); pg.wait_for_timeout(500)
    check('a new pending request shows when coming back to the app', card(pg).count() == 1 and card(pg).locator('.pd-t').text_content() == '새로 생김')
    ctx.close()
    # ---- 7) endpoint missing / failing → nothing drawn, no error UI
    reset(); rich(); seed(act(61, title='안 보임')); put('/pro/supported/off')
    ctx, pg = newpg(b); goto_today(pg)
    check('endpoint 404 → no card, Today otherwise fine (no error row)', card(pg).count() == 0 and pg.locator('#todayList .t-err').count() == 0 and pg.locator('#todayList .ev').count() >= 3)
    ctx.close()
    reset(); rich(); seed(act(62, title='안 보임'))
    ctx, pg = newpg(b); goto_today(pg)
    check('(control) the same seed with the endpoint on shows it', card(pg).count() == 1)
    put('/fail/GET%20/v1/actions?500') if False else None
    ctx.close()
    # ---- 8) empty day with a pending request, light theme, reduced motion
    reset(); put('/pro/seed', dict(title='치과', user=['x'], proactive=[], restore=[act(71, title='치과 예약')]))
    ctx, pg = newpg(b, scheme='light'); goto_today(pg)
    check('light theme: card renders, contrast of 곧 만료/--pend is covered by b2_contrast', card(pg).count() == 1)
    ctx.close()
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, reduced_motion='reduce'); pg = ctx.new_page(); reset(); rich(); seed(act(72, title='모션 줄이기')); goto_today(pg)
    check('reduced motion: card shown, no animation on it', card(pg).count() == 1 and pg.evaluate("getComputedStyle(document.querySelector('#todayList .ev.wt .pend')).animationName") == 'none')
    ctx.close()
    b.close()
check('no page errors', not errs, errs)
print(f'TOTAL {sum(R)}/{len(R)}'); raise SystemExit(0 if all(R) else 1)
