# 1.11.0 icon F screenshots → review-shots/1.11.0/icon-f/ (390px @2x, dark + light). Not part of the suite (writes files; needs a running mock: EVE_PORT=<port> python icon_f_shots.py).
import os
from playwright.sync_api import sync_playwright
from b2_common import *
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'review-shots', '1.11.0', 'icon-f'); os.makedirs(OUT, exist_ok=True)
with sync_playwright() as p:
    dev = dict(p.devices['iPhone 14']); dev['device_scale_factor'] = 2; b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        def mk():
            d = dict(dev); d['viewport'] = {'width': 390, 'height': 844}; d['screen'] = {'width': 390, 'height': 844}
            ctx = b.new_context(**d, color_scheme=scheme); ctx.add_init_script("Object.defineProperty(navigator,'standalone',{get:()=>true})")
            ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "}"); pin_clock(ctx); return ctx
        def shot(pg, name): pg.screenshot(path=f'{OUT}/{name}-{scheme}.png')
        # 01 empty Today: the 88px hero, hero mid-rise (02)
        reset(); ctx = mk(); pg = ctx.new_page()
        pg.add_init_script("document.addEventListener('animationstart',e=>{if(e.animationName==='avRise'&&window.__pauseRise){e.target.getAnimations().forEach(a=>{a.pause();a.currentTime=260})}},true)")
        pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(2500); shot(pg, '01-empty-today'); ctx.close()
        reset(); ctx = mk(); pg = ctx.new_page(); pg.add_init_script("document.addEventListener('DOMContentLoaded',()=>{const st=document.createElement('style');st.textContent='.hero.enter .eve-mark{animation-delay:-230ms!important;animation-play-state:paused!important}.hero.enter .eyes{animation-play-state:paused!important}';document.head.appendChild(st)})")
        pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(700); shot(pg, '02-empty-today-hero-rising'); ctx.close()
        # 03 Today with Eve avatars (3 선톡 + conversations)
        reset(); rich(); ctx = mk(); pg = ctx.new_page(); pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(2500); shot(pg, '03-today-avatars'); ctx.close()
        # 04 chat timeline with avatars
        reset(); seed('아이콘 F 대화', [{'role': 'user', 'content': '내일 치과 몇 시였지?', 'created_at': at(7, 41)}, {'role': 'assistant', 'content': '내일 오후 3시예요. 한 시간 전에 알려드릴게요.', 'created_at': at(7, 42)},
                                        {'role': 'user', 'content': '고마워', 'created_at': at(8, 5)}, {'role': 'assistant', 'content': '별말씀을요. 일정 하나 더 추가할까요?', 'created_at': at(8, 6)}])
        ctx = mk(); pg = ctx.new_page(); open_thread(pg, '아이콘 F 대화'); pg.wait_for_timeout(500); shot(pg, '04-chat-avatars'); ctx.close()
        # 05/06 streaming: eyes open, eyes closed (the 4s cycle paused at 3.9s); 07 the avatar mid-rise on a new answer
        for name, d in (('05-streaming-eyes-open', '0s'), ('06-streaming-blink', '-3.88s')):
            reset(); ctx = mk(); pg = ctx.new_page(); pg.goto(B + '/ui/'); pg.wait_for_timeout(800); pg.evaluate("location.hash='#/c/new'"); pg.wait_for_timeout(300)
            if pg.is_visible('#tInput'): pg.evaluate("__app.newChat()"); pg.wait_for_timeout(400)
            pg.add_style_tag(content='.ev.e.streaming .av .eyes{animation-delay:' + d + '!important;animation-play-state:paused!important}')
            pg.fill('#input', 'slow 응답'); pg.click('#sendBtn'); pg.wait_for_timeout(1200); shot(pg, name); ctx.close()
        reset(); ctx = mk(); pg = ctx.new_page(); pg.goto(B + '/ui/'); pg.wait_for_timeout(800); pg.evaluate("location.hash='#/c/new'"); pg.wait_for_timeout(300)
        if pg.is_visible('#tInput'): pg.evaluate("__app.newChat()"); pg.wait_for_timeout(400)
        pg.add_style_tag(content='.ev.enter .av .eve-mark{animation-delay:-230ms!important;animation-play-state:paused!important}')
        pg.fill('#input', 'slow 응답'); pg.click('#sendBtn'); pg.wait_for_timeout(250); shot(pg, '07-new-answer-avatar-rising'); ctx.close()
        # 08 settings top (40px mark), 09 connection notice (72px mark)
        reset(); ctx = mk(); pg = ctx.new_page(); pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(1500); pg.click('#openSettings'); pg.wait_for_timeout(1000); shot(pg, '08-settings-top')
        pg.keyboard.press('Escape'); pg.wait_for_timeout(500)
        pg.evaluate("{const n=document.getElementById('authNotice');n.hidden=false;requestAnimationFrame(()=>n.classList.add('in'))}"); pg.wait_for_timeout(700); shot(pg, '09-connection-notice'); ctx.close()
    b.close()
print('shots in', OUT)
