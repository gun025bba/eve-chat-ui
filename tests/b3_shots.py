# 1.10.0 B3 현황 띠 §13 screenshots → review-shots/1.10.0/b3/ (390px @2x dark+light; 320px strip; sheets; memoryView; chips).
# Not part of the suite (writes files; needs a running mock: EVE_PORT=<port> python b3_shots.py). Chromium with the iPhone 14 profile (WebKit cannot start on this box: missing system libs).
import os
from playwright.sync_api import sync_playwright
from b3_common import *
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'review-shots', '1.10.0', 'b3'); os.makedirs(OUT, exist_ok=True)
EVS = [ev('팀 스탠드업', 9, 30, 30, '업무'), ev('치과 예약', 10, 0, 60, '개인'), ev('점심 · 지수', 12, 30, 90, '개인'), ev('디자인 리뷰', 15, 0, 60, '업무'), ev('저녁 약속', 23, 0, 30, '개인'), ev('가족 모임', 0, 0, all_day=True, cal='가족')]
def full():
    reset(); rich(); memory(12); seed_act(act(1, title='치과 예약 · 내일 10시', exp=60 * 24 * 3, created=isoz(-90)), title='치과 예약')
    seed_act(act(2, title='장보기 알림 · 저녁 6시', verb='remind', exp=5, created=isoz(-30)), title='장보기'); brief_thread(EVS)
with sync_playwright() as p:
    dev = dict(p.devices['iPhone 14']); dev['device_scale_factor'] = 2; b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        def mk(w=390):
            d = dict(dev); d['viewport'] = {'width': w, 'height': 844}; d['screen'] = {'width': w, 'height': 844}
            ctx = b.new_context(**d, color_scheme=scheme); ctx.add_init_script("Object.defineProperty(navigator,'standalone',{get:()=>true})")
            ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "}"); return ctx
        def land(w=390, wait=2200):
            ctx = mk(w); pg = ctx.new_page(); pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(wait); return ctx, pg
        def shot(pg, name): pg.screenshot(path=f'{OUT}/{name}-{scheme}.png')
        # strip states
        full(); ctx, pg = land(); shot(pg, '01-strip-3cells'); ctx.close()
        full(); ctx, pg = land(320); shot(pg, '10-strip-320px'); ctx.close()
        reset(); rich(); memory(12); seed_act(act(1, title='치과 예약', exp=60 * 24 * 3)); ctx, pg = land(); shot(pg, '02-strip-schedule-hidden'); ctx.close()
        full(); memory(12, enabled=False); ctx, pg = land(); shot(pg, '03-strip-memory-hidden'); ctx.close()
        reset(); rich(); memory(0); brief_thread(EVS); ctx, pg = land(); shot(pg, '04-strip-pending0-memory0'); ctx.close()
        full(); put('/pro/set', {'actFail': 500, 'memListFail': 500}); ctx, pg = land(); shot(pg, '05-strip-error-dash'); ctx.close(); put('/pro/set', {'actFail': None, 'memListFail': None})
        # sheets
        full(); ctx, pg = land(); pg.locator('.stc[data-k=pend]').click(); pg.wait_for_timeout(800); shot(pg, '06-sheet-pending'); pg.keyboard.press('Escape'); pg.wait_for_timeout(500)
        pg.locator('.stc[data-k=sch]').click(); pg.wait_for_timeout(800); shot(pg, '07-sheet-schedule'); pg.keyboard.press('Escape'); pg.wait_for_timeout(500)
        pg.locator('.stc[data-k=mem]').click(); pg.wait_for_function("!document.getElementById('memoryView').hidden", timeout=8000); pg.wait_for_timeout(600); pg.evaluate("document.getElementById('memOpen').scrollIntoView({block: 'start'})"); pg.wait_for_timeout(800); shot(pg, '08-memory-cell-memoryView'); ctx.close()
        # Today pending card below the strip
        full(); ctx, pg = land(); pg.evaluate("(() => { const e = document.querySelector('#todayList .ev.wt, #todayList .pend'); if (e) e.scrollIntoView({block: 'center'}) })()"); pg.wait_for_timeout(500); shot(pg, '09-today-strip-and-pending-card'); ctx.close()
        # memory chips in a conversation (B1 chips, now tied to the same memory rule)
        full()
        ctx, pg = land(); open_thread(pg, '아침 브리핑'); pg.wait_for_timeout(800); shot(pg, '11-thread-briefing'); ctx.close()
print('done', sorted(os.listdir(OUT)))
