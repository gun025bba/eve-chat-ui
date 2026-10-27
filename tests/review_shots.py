# 390px review screenshots for the designer: python review_shots.py <outdir>
import os, sys
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765'); out = sys.argv[1]; os.makedirs(out, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme); pg = ctx.new_page()
        pg.add_init_script("localStorage.setItem('eve.mem.introSeen','1')")
        pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1200); pg.screenshot(path=f'{out}/list-{scheme}.png')
        pg.click('#newChat'); pg.wait_for_timeout(900); pg.screenshot(path=f'{out}/empty-{scheme}.png')
        pg.fill('#input', '이번 주 서울 날씨 정리해 줘'); pg.wait_for_timeout(200); pg.screenshot(path=f'{out}/composer-input-{scheme}.png')
        pg.click('#sendBtn'); pg.wait_for_timeout(3000); pg.screenshot(path=f'{out}/chat-{scheme}.png')
        extra = os.environ.get('SHOT_EXTRA')
        if extra: exec(open(extra).read())
        ctx.close()
    b.close()
