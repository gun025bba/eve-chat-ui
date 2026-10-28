# 1.10.0 B2 하루 (DIRECTION-B-SPEC §1 §4 §9): Today — timeline items, empty (new day), skeleton, error, stagger, settings subtitle, start a conversation
import re
from playwright.sync_api import sync_playwright
from b2_common import *
R = []; errs = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
def cls(pg, sel='#todayList > li'): return pg.evaluate(f"[...document.querySelectorAll('{sel}')].map(l=>l.className)")
def newpg(b, scheme='dark', **kw):
    ctx = new_ctx(b, scheme=scheme, **kw); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); return ctx, pg
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---- 1) lots of data
    reset(); ids = rich(); ids.update(older())
    ctx, pg = newpg(b); goto_today(pg)
    check('root is Today: route today, hash #/, title 오늘', rt(pg) == 'today' and pg.text_content('#todayTitle') == '오늘' and pg.evaluate('location.hash') in ('#/', ''))
    dl = pg.text_content('#todayDate'); check('date line "M월 D일 X요일"', re.fullmatch(r'\d+월 \d+일 [월화수목금토일]요일', dl or '') and dl == f'{kst_now().month}월 {kst_now().day}일 {wd_of(0)}요일', dl)
    c = cls(pg)
    check('3 선톡 items (briefing, watch, quiet-hours digest)', sum(' pro' in ' ' + x for x in c) == 3, c)
    check('latest 5 of 7 conversations + one "기록에서 더 보기 · 오늘 대화 2개" row (deviation: latest-5)', sum('conv' in x.split() for x in c) == 5 and sum('more' in x.split() for x in c) == 1 and '2개' in pg.text_content('#todayList .ev.more'), c)
    check('이어서 = yesterday\'s thread, time column "어제"', pg.locator('#todayList .ev.cont').count() == 1 and '발표 자료 준비' in pg.text_content('#todayList .ev.cont') and pg.text_content('#todayList .ev.cont time.tm') == '어제')
    check('지금 item is last, with aria-label "HH:mm 지금"', c[-1].startswith('rail-now') and re.fullmatch(r'\d\d:\d\d 지금', pg.get_attribute('#todayList .rail-now', 'aria-label') or ''))
    order = [x.split()[1] if x.startswith('ev') else 'now' for x in c]
    check('order: more → events by time → 이어서 → 지금', order[0] == 'more' and order[-2] == 'cont' and order[-1] == 'now', order)
    tms = pg.evaluate("[...document.querySelectorAll('#todayList .ev.e time.tm, #todayList .ev.me time.tm')].map(t=>t.textContent)")
    check('event times ascend', tms == sorted(tms) and len(tms) == 8, tms)
    who = pg.evaluate("[...document.querySelectorAll('#todayList .ev.pro .who-n')].map(w=>w.textContent)")
    check('선톡 labels: Eve · <job> / Eve · 조용한 시간 동안 요약 / Eve가 먼저 보냄 fallback', 'Eve · 아침 브리핑' in who and 'Eve · 가격 알림' in who and 'Eve · 조용한 시간 동안 요약' in who, who)
    check('unread 선톡 carries data-unread (briefing only)', pg.locator('#todayList .ev.pro[data-unread]').count() == 1 and '아침 브리핑' in pg.text_content('#todayList .ev.pro[data-unread]'))
    check('conv items show the user name 나 and the thread title as the body', pg.locator('#todayList .ev.conv').first.locator('.who-n').text_content() == '나' and pg.locator('#todayList .ev.conv .tx').first.text_content() != '')
    check('each interactive item is one 44px+ button covering the row', pg.evaluate("[...document.querySelectorAll('#todayList .ev-hit')].every(b=>b.getBoundingClientRect().height>=44)"))
    # navigation from each kind of item
    pg.locator('#todayList .ev.conv').first.locator('.ev-hit').click(); pg.wait_for_timeout(900)
    check('conversation item → chat; hash #/t/<id>; back label "오늘"', rt(pg) == 'chat' and pg.evaluate('location.hash').startswith('#/t/') and pg.text_content('#backLbl') == '오늘')
    pg.click('#backBtn'); pg.wait_for_timeout(700); check('back → Today', rt(pg) == 'today' and pg.evaluate('location.hash') in ('#/', ''))
    pg.locator('#todayList .ev.pro').first.locator('.ev-hit').click(); pg.wait_for_timeout(900)
    check('선톡 item → its thread', rt(pg) == 'chat' and pg.locator('.msg.assistant').count() >= 1); pg.click('#backBtn'); pg.wait_for_timeout(700)
    pg.locator('#todayList .ev.cont .ev-hit').click(); pg.wait_for_timeout(900)
    check('이어서 → that thread', rt(pg) == 'chat' and '발표 자료 준비' in pg.text_content('#title')); pg.click('#backBtn'); pg.wait_for_timeout(700)
    pg.locator('#todayList .ev.more .ev-hit').click(); pg.wait_for_timeout(700)
    check('기록에서 더 보기 → log', rt(pg) == 'list' and pg.evaluate('location.hash') == '#/log'); ctx.close()
    # ---- 2) new day: nothing today, yesterday exists → 이어서 + 지금 only
    reset(); older()
    ctx, pg = newpg(b); goto_today(pg); c = cls(pg)
    check('새 하루: only 이어서 + 지금', [x.split()[0] for x in c] == ['ev', 'rail-now'] and 'cont' in c[0], c)
    check('새 하루: 지금 hint line', '아래에 한 줄로 남기면' in pg.text_content('#todayList .rail-now'))
    ctx.close()
    # ---- 3) nothing at all
    reset(); ctx, pg = newpg(b); goto_today(pg); c = cls(pg)
    check('empty account: just the 지금 item, no 이어서, no logo, no error', c == ['rail-now'] or [x.split()[0] for x in c] == ['rail-now'], c); ctx.close()
    # ---- 4) skeleton while the first load is in flight
    reset(); rich(); put('/delay/1800?GET%20/v1/threads')
    ctx, pg = newpg(b); pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(900)
    check('skeleton: 2 placeholder items (aria-hidden) while loading; no 지금 mixed with stale data', pg.locator('#todayList .skel-ev').count() == 2 and pg.evaluate("[...document.querySelectorAll('#todayList .skel-ev')].every(l=>l.getAttribute('aria-hidden')==='true')"))
    pg.wait_for_timeout(5600); check('skeleton replaced by the real items', pg.locator('#todayList .skel-ev').count() == 0 and pg.locator('#todayList .ev.pro').count() == 3)
    put('/delay/clear'); ctx.close()
    # ---- 5) load error → message + retry
    reset(); rich(); put('/fail/500?GET%20/v1/threads')
    ctx, pg = newpg(b); goto_today(pg, wait=1800)
    check('error: "불러오지 못했어요" + 다시 시도 (no raw error text)', pg.locator('#todayList .t-err').count() == 1 and '불러오지 못했어요' in pg.text_content('#todayList .t-err') and pg.is_visible('#todayRetry'))
    put('/fail/clear'); pg.click('#todayRetry'); pg.wait_for_timeout(1500)
    check('retry → items appear', pg.locator('#todayList .t-err').count() == 0 and pg.locator('#todayList .ev.pro').count() == 3); ctx.close()
    # ---- 6) first-visit stagger: transform/opacity only, once per session, never with reduced motion
    reset(); rich()
    ctx, pg = newpg(b); pg.goto(B + '/ui/#/'); pg.wait_for_timeout(900)   # the stagger is once per session: look before any reload
    n1 = pg.locator('#todayList .stg').count(); d = pg.evaluate("[...document.querySelectorAll('#todayList .stg')].map(l=>l.style.animationDelay)")
    sw = pg.evaluate("!document.getElementById('todayStrip').hidden")   # B3: the 현황 띠 is slot 0 of the stagger (§B2 "띠 → 이벤트"), so the events start one slot later when it is shown
    k = 1 if sw else 0
    check('first visit: ≤5 items staggered 40ms apart (after the strip, when it is shown)', 1 <= n1 <= 5 and d[:3] == [f'{(k + i) * 40}ms' for i in range(3)], [n1, d, sw])
    pg.reload(); pg.wait_for_timeout(900); check('same session again: no stagger', pg.locator('#todayList .stg').count() == 0); ctx.close()
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, reduced_motion='reduce'); pg = ctx.new_page(); pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1200)
    check('reduced motion: no stagger', pg.locator('#todayList .stg').count() == 0); ctx.close()
    css = open('../styles.css').read()
    check('stagger/skeleton keyframes animate transform/opacity only (no layout props)', not re.search(r'@keyframes (tIn|tPulse)\{[^}]*\b(left|top|height|width|margin)[^}]*\}', css))
    # ---- 7) settings top shows 로컬 · 비공개 (moved out of the chat header)
    reset(); rich(); ctx, pg = newpg(b); goto_today(pg); pg.click('#openSettings'); pg.wait_for_timeout(700)
    check('settings top: 로컬 · 비공개 with a lock', pg.is_visible('#sPriv') and '로컬 · 비공개' in pg.text_content('#sPriv') and pg.locator('#sPriv svg').count() == 1)
    pg.click('#cancelSettings'); pg.wait_for_timeout(400); ctx.close()
    # ---- 8) start a conversation from Today (composer lives on Today)
    reset(); rich(); ctx, pg = newpg(b); goto_today(pg)
    check('Today composer: placeholder 지금 일을 남겨요, send hidden while empty', pg.get_attribute('#tInput', 'placeholder') == '지금 일을 남겨요' and pg.evaluate("getComputedStyle(document.getElementById('tSend')).opacity") == '0')
    n0 = pg.locator('#todayList .ev.conv').count()
    pg.fill('#tInput', '오늘 할 일 정리해줘'); pg.wait_for_timeout(250); check('send appears once there is text', pg.evaluate("getComputedStyle(document.getElementById('tSend')).opacity") == '1')
    pg.click('#tSend'); pg.wait_for_timeout(2600)
    check('send → chat route, hash #/t/, the message is the first turn, composer on Today cleared', rt(pg) == 'chat' and pg.evaluate('location.hash').startswith('#/t/') and '오늘 할 일 정리해줘' in pg.text_content('#messages') and pg.input_value('#tInput') == '')
    pg.click('#backBtn'); pg.wait_for_timeout(900)
    check('back → Today shows the new conversation as the newest 나 item', rt(pg) == 'today' and '오늘 할 일 정리해줘' in pg.text_content('#todayList'))
    pg.locator('#tPlus').click(); pg.wait_for_timeout(300); check('Today + menu has 웹 검색', pg.is_visible('#tMenu') and '웹 검색' in pg.text_content('#tMenu'))
    pg.keyboard.press('Escape'); ctx.close()
    # ---- 9) forbidden elements (§1/§13): centered logo, "무엇을 도와드릴까요?", suggestion cards — nowhere
    reset(); rich(); older(); ctx, pg = newpg(b); goto_today(pg)
    SEL = '.suggest,.suggestions,.suggestion,.sugg,.chip-suggest,.empty-logo,.hero-logo,.welcome,#emptyState .logo,.empty-state .logo,.starter,.starters'
    seen = {}
    for name, h in [('today', '#/'), ('log', '#/log'), ('archive', '#/archive')]:
        goto_today(pg, h); seen[name] = pg.evaluate("[document.body.innerText.includes('무엇을 도와드릴까요'), document.querySelectorAll(arguments[0]).length]".replace('arguments[0]', repr(SEL)))
    pg.evaluate('__app.newChat()'); pg.wait_for_timeout(600); seen['new-chat'] = pg.evaluate(f"[document.body.innerText.includes('무엇을 도와드릴까요'), document.querySelectorAll({SEL!r}).length]")
    check('forbidden elements absent in Today / 기록 / 보관함 / empty conversation', all(v == [False, 0] for v in seen.values()), seen)
    src = ''.join(open('../' + f).read() for f in ('index.html', 'app.js', 'today.js'))
    check('forbidden strings absent from index.html / app.js / today.js', '무엇을 도와드릴까요' not in src and not re.search(r'class="[^"]*(suggest|hero-logo|empty-logo)', src))
    ctx.close()
    check('no page errors', not errs, errs); b.close()
print(f'{sum(R)}/{len(R)} checks'); raise SystemExit(0 if all(R) else 1)
