# Screenshot of chat header in emulated iPhone standalone (display-mode standalone + safe-area top)
import sys
from playwright.sync_api import sync_playwright
out = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch()
    c = b.new_context(viewport={'width':393,'height':852}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme='dark')
    c.add_init_script("localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit'}))")
    c.add_init_script("Object.defineProperty(navigator,'standalone',{get:()=>true})")
    pg = c.new_page()
    cdp = c.new_cdp_session(pg)
    cdp.send('Emulation.setEmulatedMedia', {'features':[{'name':'display-mode','value':'standalone'}]})
    pg.goto('http://127.0.0.1:8765/ui/'); pg.wait_for_timeout(1200)
    pg.add_style_tag(content=':root{--sat:47px}') 
    pg.evaluate("document.documentElement.style.setProperty('--fake','1')")
    pg.screenshot(path=out, clip={'x':0,'y':0,'width':393,'height':140})
    b.close()
