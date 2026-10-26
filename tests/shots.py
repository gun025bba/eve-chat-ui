from playwright.sync_api import sync_playwright
import json
with sync_playwright() as p:
    b=p.chromium.launch()
    for scheme in ['dark','light']:
        ctx=b.new_context(viewport={'width':393,'height':852},device_scale_factor=3,is_mobile=True,has_touch=True,color_scheme=scheme)
        pg=ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.add_init_script("localStorage.setItem('llmchat.settings', JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit',system:'',showThink:false,noThink:false}))")
        pg.goto('http://127.0.0.1:8765/ui/'); pg.wait_for_timeout(700)
        pg.screenshot(path=f'shots/empty-{scheme}.png')
        pg.fill('#input','파이썬으로 비교 연산 예시 보여줘'); pg.click('#sendBtn'); pg.wait_for_timeout(1300)
        pg.click('details.think summary'); pg.wait_for_timeout(400)
        pg.screenshot(path=f'shots/chat-{scheme}.png')
        pg.click('#menuBtn'); pg.wait_for_timeout(500); pg.screenshot(path=f'shots/drawer-{scheme}.png')
        pg.click('#openSettings'); pg.wait_for_timeout(700); pg.screenshot(path=f'shots/settings-{scheme}.png')
        print(scheme,'errors:',errs); ctx.close()
    b.close()
