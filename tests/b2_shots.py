# 1.10.0 B2 하루 §13 screenshots → review-shots/1.10.0/b2/ (390px @2x dark+light; 375px Today/Log; push mid-frame; light contrast).
# Not part of the suite (writes files; needs a running mock: EVE_PORT=<port> python b2_shots.py). Chromium with the iPhone 14 profile (WebKit cannot start on this box: missing system libs).
import json, os
from playwright.sync_api import sync_playwright
from b2_common import *
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'review-shots', '1.10.0', 'b2'); os.makedirs(OUT, exist_ok=True)
with sync_playwright() as p:
    dev = dict(p.devices['iPhone 14']); dev['device_scale_factor'] = 2; b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        def mk(w=390):
            d = dict(dev); d['viewport'] = {'width': w, 'height': 844}; d['screen'] = {'width': w, 'height': 844}
            ctx = b.new_context(**d, color_scheme=scheme); ctx.add_init_script("Object.defineProperty(navigator,'standalone',{get:()=>true})")
            ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "}"); return ctx
        def shot(pg, name): pg.screenshot(path=f'{OUT}/{name}-{scheme}.png')
        def land(pg, h='#/', wait=2200): pg.goto(B + '/ui/' + h); pg.reload(); pg.wait_for_timeout(wait)
        # --- Today: lots of data
        reset(); rich(); older()
        ctx = mk(); pg = ctx.new_page(); land(pg); shot(pg, '01-today-data')
        # --- push mid-frame: Today → conversation, animations paused at 50%
        pg.locator('#todayList .ev.conv .ev-hit').last.click(); pg.wait_for_timeout(30)
        n = pg.evaluate("(()=>{const a=document.getAnimations();a.forEach(x=>{try{x.pause();x.currentTime=(x.effect.getComputedTiming().duration||0)*.5}catch(e){}});return a.length})()"); pg.wait_for_timeout(120); shot(pg, '07-push-midframe'); print(scheme, 'paused animations', n)
        ctx.close()
        # --- Log: week strip + 3 days + 보관함 row; searching
        ctx = mk(); pg = ctx.new_page(); land(pg, '#/log'); shot(pg, '04-log-week-days-archive')
        pg.click('#logSearch'); pg.wait_for_timeout(300); pg.fill('#search', '정리'); pg.wait_for_timeout(1100); shot(pg, '05-log-searching'); ctx.close()
        # --- 375px Today + Log
        ctx = mk(375); pg = ctx.new_page(); land(pg); shot(pg, '08-375-today'); land(pg, '#/log'); shot(pg, '08-375-log'); ctx.close()
        # --- new day (only 이어서 + 지금) and truly empty log
        reset(); older()
        ctx = mk(); pg = ctx.new_page(); land(pg); shot(pg, '02-today-new-day'); ctx.close()
        reset(); ctx = mk(); pg = ctx.new_page(); land(pg, '#/log'); shot(pg, '06-log-empty'); ctx.close()
        # --- skeleton
        reset(); rich(); put('/delay/6000?GET /v1/threads'); ctx = mk(); pg = ctx.new_page(); pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(1000); shot(pg, '03-today-skeleton')
        pg.goto(B + '/ui/#/log'); pg.reload(); pg.wait_for_timeout(1000); shot(pg, '03b-log-skeleton'); ctx.close(); put('/delay/clear')
    # --- light contrast: Today rich, light, with the numbers
    reset(); rich(); older(); d = dict(dev); d['viewport'] = {'width': 390, 'height': 844}
    ctx = b.new_context(**d, color_scheme='light'); ctx.add_init_script("Object.defineProperty(navigator,'standalone',{get:()=>true})"); ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "}")
    pg = ctx.new_page(); pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(2200); pg.screenshot(path=f'{OUT}/09-contrast-light.png'); ctx.close(); b.close()
print('done', sorted(os.listdir(OUT)))
